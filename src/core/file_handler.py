"""مدير الملفات - نقل ونسخ وحذف وإعادة تسمية"""
import os
import shutil
import time
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from .config import Config
from .path_policy import iter_files

logger = logging.getLogger(__name__)

# سياسة النسخ الاحتياطي (مراجعة كيمي — المرحلة 1):
# ما فوق BACKUP_MAX_SIZE لا يُنسخ احتياطياً (نعتمد سلة المحذوفات)،
# والنسخ الأقدم من BACKUP_MAX_AGE_DAYS يُحذف تلقائياً لمنع امتلاء القرص.
BACKUP_MAX_SIZE = 100 * 1024 * 1024  # 100MB
BACKUP_MAX_AGE_DAYS = 7


class FileHandler:
    """مدير عمليات الملفات مع دعم التراجع"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self._action_history: List[dict] = []
        self._backup_dir = Path(self.config.database_path) / "backups"

    def move_file(self, src: str, dest_category: str, base_dir: str) -> dict:
        """نقل ملف إلى مجلد التصنيف"""
        src_path = Path(src)
        dest_dir = Path(base_dir) / dest_category
        dest_path = dest_dir / src_path.name

        # تجنب الكتابة فوق ملف موجود
        if dest_path.exists():
            stem = src_path.stem
            suffix = src_path.suffix
            counter = 1
            while dest_path.exists():
                dest_path = dest_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        # نسخ احتياطي
        backup_path = self._backup_file(src_path)
        dest_dir.mkdir(parents=True, exist_ok=True)

        try:
            shutil.move(str(src_path), str(dest_path))
            self._record_action("move", str(src_path), str(dest_path), backup_path)
            logger.info(f"تم نقل: {src_path.name} -> {dest_category}/")
            return {"success": True, "dest": str(dest_path)}
        except Exception as e:
            logger.error(f"خطأ في نقل {src}: {e}")
            return {"success": False, "error": str(e)}

    def copy_file(self, src: str, dest: str) -> dict:
        """نسخ ملف"""
        try:
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            logger.info(f"تم نسخ: {src} -> {dest}")
            return {"success": True}
        except Exception as e:
            logger.error(f"خطأ في نسخ {src}: {e}")
            return {"success": False, "error": str(e)}

    def delete_file(self, filepath: str, use_trash: bool = True) -> dict:
        """حذف ملف (نقل إلى سلة المحذوفات أو حذف نهائي)"""
        file_path = Path(filepath)
        if not file_path.exists():
            return {"success": False, "error": "الملف غير موجود"}

        backup_path = self._backup_file(file_path)

        try:
            if use_trash:
                trash_path = self._send_to_trash(file_path)
                self._record_action("delete", str(file_path), str(trash_path), backup_path)
            else:
                file_path.unlink()
                self._record_action("delete_permanent", str(file_path), None, backup_path)
            logger.info(f"تم حذف: {filepath}")
            return {"success": True}
        except Exception as e:
            logger.error(f"خطأ في حذف {filepath}: {e}")
            return {"success": False, "error": str(e)}

    def rename_file(self, filepath: str, new_name: str) -> dict:
        """إعادة تسمية ملف"""
        file_path = Path(filepath)
        if not file_path.exists():
            return {"success": False, "error": "الملف غير موجود"}

        # Security: الاسم يجب أن يكون اسماً بسيطاً — منع الهروب من المجلد
        # عبر مسارات مثل "../../evil" (مراجعة كيمي — ثغرة حرجة).
        # ملاحظة: نرفض "\\" حتى على لينكس لأنها فاصل مسارات على Windows،
        # ولا مبرر لوجودها في اسم ملف أصلاً.
        if not new_name or not new_name.strip():
            return {"success": False, "error": "اسم غير صالح — الاسم فارغ"}
        if (
            Path(new_name).name != new_name
            or os.sep in new_name
            or "/" in new_name
            or "\\" in new_name
            or (os.altsep and os.altsep in new_name)
        ):
            return {"success": False, "error": "اسم غير صالح — لا يجوز أن يحوي مساراً"}

        new_path = file_path.parent / new_name
        if new_path.exists():
            return {"success": False, "error": "يوجد ملف بنفس الاسم"}

        backup_path = self._backup_file(file_path)

        try:
            file_path.rename(new_path)
            self._record_action("rename", str(file_path), str(new_path), backup_path)
            logger.info(f"تم إعادة تسمية: {file_path.name} -> {new_name}")
            return {"success": True, "new_path": str(new_path)}
        except Exception as e:
            logger.error(f"خطأ في إعادة تسمية {filepath}: {e}")
            return {"success": False, "error": str(e)}

    def undo_last_action(self) -> dict:
        """التراجع عن آخر عملية"""
        if not self._action_history:
            return {"success": False, "error": "لا توجد عمليات للتراجع عنها"}

        action = self._action_history[-1]
        try:
            if action["type"] == "move":
                shutil.move(action["dest"], action["src"])
            elif action["type"] == "delete":
                backup = action.get("backup")
                if backup and Path(backup).exists():
                    shutil.copy2(backup, action["src"])
            elif action["type"] == "rename":
                Path(action["dest"]).rename(action["src"])
            elif action["type"] == "delete_permanent":
                backup = action.get("backup")
                if backup and Path(backup).exists():
                    shutil.copy2(backup, action["src"])

            self._action_history.pop()
            logger.info(f"تم التراجع عن: {action['type']}")
            return {"success": True}
        except Exception as e:
            logger.error(f"خطأ في التراجع: {e}")
            return {"success": False, "error": str(e)}

    def create_category_folders(self, base_dir: str) -> List[str]:
        """إنشاء مجلدات التصنيفات"""
        created = []
        for cat in self.config.categories:
            cat_dir = Path(base_dir) / cat
            if not cat_dir.exists():
                cat_dir.mkdir(parents=True, exist_ok=True)
                created.append(str(cat_dir))
                logger.info(f"تم إنشاء مجلد: {cat}")
        return created

    def get_file_info(self, filepath: str) -> dict:
        """معلومات الملف التفصيلية"""
        path = Path(filepath)
        if not path.exists():
            return {"error": "الملف غير موجود"}
        stat = path.stat()
        return {
            "name": path.name,
            "path": str(path),
            "extension": path.suffix,
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "is_dir": path.is_dir(),
            "is_file": path.is_file(),
        }

    def scan_directory(self, directory: str, recursive: bool = True) -> list:
        """مسح مجلد وإرجاع قائمة معلومات الملفات

        المعاملات:
            directory: مسار المجلد المراد مسحه
            recursive: هل يتم المسح بشكل متكرر في المجلدات الفرعية

        العائد:
            قائمة قواميس تحتوي معلومات كل ملف (name, path, type, size, ...)
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            logger.warning(f"المجلد غير موجود: {directory}")
            return []

        results = []
        for item in iter_files(dir_path, recursive=recursive):
            try:
                info = self.get_file_info(str(item))
                info["type"] = item.suffix.lstrip(".").lower() or "بدون_امتداد"
                results.append(info)
            except Exception as e:
                logger.debug(f"خطأ في مسح {item}: {e}")

        logger.info(f"تم مسح {len(results)} ملف في {directory}")
        return results

    def _backup_file(self, filepath: Path) -> Optional[str]:
        """نسخ ملف احتياطي — مع حد حجم (ما فوق BACKUP_MAX_SIZE يُتخطى)"""
        try:
            if filepath.stat().st_size > BACKUP_MAX_SIZE:
                logger.info(
                    f"تخطي النسخ الاحتياطي (الحجم يتجاوز {BACKUP_MAX_SIZE // (1024 * 1024)}MB): {filepath.name}"
                )
                return None
            self._backup_dir.mkdir(parents=True, exist_ok=True)
            backup = self._backup_dir / filepath.name
            if backup.exists():
                backup = self._backup_dir / f"{filepath.stem}_{datetime.now().timestamp()}{filepath.suffix}"
            shutil.copy2(str(filepath), str(backup))
            self._cleanup_old_backups()
            return str(backup)
        except Exception as e:
            logger.warning(f"لم يتم النسخ الاحتياطي: {e}")
            return None

    def _cleanup_old_backups(self, max_age_days: int = BACKUP_MAX_AGE_DAYS) -> int:
        """حذف النسخ الاحتياطية الأقدم من max_age_days — سياسة احتفاظ تمنع امتلاء القرص"""
        cutoff = time.time() - max_age_days * 86400
        removed = 0
        try:
            for f in self._backup_dir.glob("*"):
                try:
                    if f.is_file() and f.stat().st_mtime < cutoff:
                        f.unlink(missing_ok=True)
                        removed += 1
                except OSError:
                    continue
        except Exception as e:
            logger.debug(f"تنظيف النسخ الاحتياطية: {e}")
        if removed:
            logger.info(f"تم حذف {removed} نسخة احتياطية أقدم من {max_age_days} يوماً")
        return removed

    @staticmethod
    def _send_to_trash(file_path: Path) -> str:
        """نقل إلى سلة المحذوفات عبر send2trash (XDG/Windows/macOS)،
        مع الاحتفاظ بمسار XDG اليدوي على لينكس كخطة بديلة إن لم تتوفر المكتبة."""
        try:
            from send2trash import send2trash
            send2trash(str(file_path))
            return f"trash://{file_path.name}"
        except ImportError:
            trash_dir = Path.home() / ".local/share/Trash/files"
            trash_dir.mkdir(parents=True, exist_ok=True)
            trash_name = f"{file_path.name}_{datetime.now().timestamp()}"
            trash_path = trash_dir / trash_name
            shutil.move(str(file_path), str(trash_path))
            return str(trash_path)

    def _record_action(self, action_type: str, src: str, dest: str, backup: str):
        """تسجيل عملية للتراجع"""
        self._action_history.append({
            "type": action_type,
            "src": src,
            "dest": dest,
            "backup": backup,
            "timestamp": datetime.now().isoformat(),
        })

    @property
    def history(self) -> List[dict]:
        return list(self._action_history)
