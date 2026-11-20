"""مدير الملفات - نقل ونسخ وحذف وإعادة تسمية

IFM-002/IFM-007: كل عمليات النقل والنسخ وإعادة التسمية تمر عبر SafeMover
(بوابة التنفيذ الوحيدة) مع تحقق SHA-256 وحل تضارب آمن. الحذف النهائي معطل
افتراضيًا ويحتاج confirm_permanent_delete=True صراحةً.
"""
import shutil
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from .config import Config
from .path_policy import iter_files
from .safe_mover import SafeMover

logger = logging.getLogger(__name__)


class FileHandler:
    """مدير عمليات الملفات مع دعم التراجع"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self._action_history: List[dict] = []
        self._backup_dir = Path(self.config.database_path) / "backups"
        self._mover = SafeMover(verify_checksum=True, move_sidecar=True)

    def move_file(self, src: str, dest_category: str, base_dir: str) -> dict:
        """نقل ملف إلى مجلد التصنيف — عبر SafeMover (IFM-002)"""
        src_path = Path(src)
        dest_dir = Path(base_dir) / dest_category
        dest_path = dest_dir / src_path.name

        # نسخ احتياطي
        backup_path = self._backup_file(src_path)

        try:
            result = self._mover.move(src_path, dest_path)
            if not result.success:
                logger.error(f"فشل نقل {src}: {result.error}")
                return {"success": False, "error": result.error}
            self._record_action("move", str(src_path), result.final_path, backup_path)
            logger.info(f"تم نقل: {src_path.name} -> {dest_category}/")
            return {"success": True, "dest": result.final_path}
        except Exception as e:
            logger.error(f"خطأ في نقل {src}: {e}")
            return {"success": False, "error": str(e)}

    def copy_file(self, src: str, dest: str) -> dict:
        """نسخ ملف — عبر SafeMover (IFM-002)"""
        try:
            result = self._mover.copy(src, dest)
            if not result.success:
                logger.error(f"فشل نسخ {src}: {result.error}")
                return {"success": False, "error": result.error}
            logger.info(f"تم نسخ: {src} -> {result.final_path}")
            return {"success": True}
        except Exception as e:
            logger.error(f"خطأ في نسخ {src}: {e}")
            return {"success": False, "error": str(e)}

    def delete_file(self, filepath: str, use_trash: bool = True,
                    confirm_permanent_delete: bool = False) -> dict:
        """حذف ملف (نقل إلى سلة المحذوفات أو حذف نهائي مؤكَّد)

        IFM-007: الحذف النهائي معطل افتراضيًا — يتطلب confirm_permanent_delete=True
        صراحةً مع use_trash=False، ويبقى النسخ الاحتياطي سابقًا للحذف.
        """
        file_path = Path(filepath)
        if not file_path.exists():
            return {"success": False, "error": "الملف غير موجود"}

        backup_path = self._backup_file(file_path)

        try:
            if use_trash:
                trash_dir = Path.home() / ".local/share/Trash/files"
                trash_dir.mkdir(parents=True, exist_ok=True)
                trash_name = f"{file_path.name}_{datetime.now().timestamp()}"
                trash_path = trash_dir / trash_name
                result = self._mover.move(file_path, trash_path)
                if not result.success:
                    logger.error(f"فشل نقل إلى السلة {filepath}: {result.error}")
                    return {"success": False, "error": result.error}
                self._record_action("delete", str(file_path), result.final_path, backup_path)
            elif confirm_permanent_delete:
                file_path.unlink()
                self._record_action("delete_permanent", str(file_path), None, backup_path)
            else:
                return {
                    "success": False,
                    "error": (
                        "الحذف النهائي محظور افتراضيًا (IFM-007) — مرر "
                        "confirm_permanent_delete=True صراحةً أو استخدم use_trash=True"
                    ),
                }
            logger.info(f"تم حذف: {filepath}")
            return {"success": True}
        except Exception as e:
            logger.error(f"خطأ في حذف {filepath}: {e}")
            return {"success": False, "error": str(e)}

    def rename_file(self, filepath: str, new_name: str) -> dict:
        """إعادة تسمية ملف — عبر SafeMover (IFM-002)؛ تضارب الاسم يأخذ لاحقة لا استبدال"""
        file_path = Path(filepath)
        if not file_path.exists():
            return {"success": False, "error": "الملف غير موجود"}

        new_path = file_path.parent / new_name
        backup_path = self._backup_file(file_path)

        try:
            result = self._mover.move(file_path, new_path)
            if not result.success:
                logger.error(f"فشل إعادة تسمية {filepath}: {result.error}")
                return {"success": False, "error": result.error}
            self._record_action("rename", str(file_path), result.final_path, backup_path)
            logger.info(f"تم إعادة تسمية: {file_path.name} -> {Path(result.final_path).name}")
            return {"success": True, "new_path": result.final_path}
        except Exception as e:
            logger.error(f"خطأ في إعادة تسمية {filepath}: {e}")
            return {"success": False, "error": str(e)}

    def undo_last_action(self) -> dict:
        """التراجع عن آخر عملية

        ملاحظة: هذا مسار الاسترداد وليس عملية تنظيم — يستخدم shutil/copy2
        عمداً لاستعادة الحالة السابقة، ولا يُعد تجاوزاً لباب SafeMover
        (الذي يحكم عمليات التنظيم فقط)."""
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
        """نسخ ملف احتياطي"""
        try:
            self._backup_dir.mkdir(parents=True, exist_ok=True)
            backup = self._backup_dir / filepath.name
            if backup.exists():
                backup = self._backup_dir / f"{filepath.stem}_{datetime.now().timestamp()}{filepath.suffix}"
            shutil.copy2(str(filepath), str(backup))
            return str(backup)
        except Exception as e:
            logger.warning(f"لم يتم النسخ الاحتياطي: {e}")
            return None

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
