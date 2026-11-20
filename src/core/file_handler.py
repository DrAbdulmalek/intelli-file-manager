"""مدير الملفات - نقل ونسخ وحذف وإعادة تسمية"""
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from .config import Config
from .safe_mover import SafeMover

logger = logging.getLogger(__name__)


class FileHandler:
    """مدير عمليات الملفات مع دعم التراجع — جميع العمليات تمر عبر SafeMover"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self._action_history: List[dict] = []
        self._backup_dir = Path(self.config.database_path) / "backups"
        self._safe_mover = None  # SafeMover إلزامي لجميع العمليات (لا مسارات تخطي)

    @property
    def safe_mover(self):
        """يُرجع SafeMover مشترك (يُنشأ عند الطلب)"""
        if self._safe_mover is None:
            from .safe_mover import SafeMover
            self._safe_mover = SafeMover(verify_checksum=True, move_sidecar=True)
        return self._safe_mover

    def move_file(self, src: str, dest_category: str, base_dir: str) -> dict:
        """نقل ملف إلى مجلد التصنيف عبر SafeMover (إجباري)"""
        src_path = Path(src)
        dest_dir = Path(base_dir) / dest_category
        dest_path = dest_dir / src_path.name

        # ضمان وجود مجلد الوجهة
        dest_dir.mkdir(parents=True, exist_ok=True)

        try:
            result = self.safe_mover.move(str(src_path), str(dest_path))
            if not result.success:
                logger.error(f"فشل نقل {src}: {result.error}")
                return {"success": False, "error": result.error or "safe_move failed"}
            self._record_action("move", str(src_path), result.final_path, None)
            logger.info(f"تم نقل: {src_path.name} -> {dest_category}/")
            return {"success": True, "dest": result.final_path}
        except Exception as e:
            logger.error(f"خطأ في نقل {src}: {e}")
            return {"success": False, "error": str(e)}

    def copy_file(self, src: str, dest: str) -> dict:
        """نسخ ملف عبر SafeMover (إجباري)"""
        try:
            result = self.safe_mover.copy(src, dest)
            if not result.success:
                logger.error(f"فشل نسخ {src}: {result.error}")
                return {"success": False, "error": result.error or "safe_copy failed"}
            logger.info(f"تم نسخ: {src} -> {dest}")
            return {"success": True}
        except Exception as e:
            logger.error(f"خطأ في نسخ {src}: {e}")
            return {"success": False, "error": str(e)}

    def delete_file(self, filepath: str, use_trash: bool = True) -> dict:
        """حذف ملف (نقل إلى سلة المحذوفات فقط؛ الحذف النهائي محظور)

        per تعليمات المستخدم: ممنوع rm -r/-rf، الاستثناء rmdir للمجلد الفارغ فقط.
        """
        file_path = Path(filepath)
        if not file_path.exists():
            return {"success": False, "error": "الملف غير موجود"}

        try:
            if use_trash:
                trash_dir = Path.home() / ".local/share/Trash/files"
                trash_dir.mkdir(parents=True, exist_ok=True)
                trash_name = f"{file_path.name}_{datetime.now().timestamp()}"
                trash_path = trash_dir / trash_name
                result = self.safe_mover.move(str(file_path), str(trash_path))
                if not result.success:
                    return {"success": False, "error": result.error or "safe_move to trash failed"}
                self._record_action("delete", str(file_path), str(trash_path), None)
                logger.info(f"تم نقل إلى سلة المحذوفات: {filepath}")
                return {"success": True}
            else:
                # الحذف النهائي محظور per تعليمات المستخدم
                logger.warning(f"محاولة حذف نهائي محظورة: {filepath}")
                return {
                    "success": False,
                    "error": "الحذف النهائي محظور. استخدم use_trash=True أو rmdir للمجلد الفارغ فقط."
                }
        except Exception as e:
            logger.error(f"خطأ في حذف {filepath}: {e}")
            return {"success": False, "error": str(e)}

    def rename_file(self, filepath: str, new_name: str) -> dict:
        """إعادة تسمية ملف عبر SafeMover (إجباري)"""
        file_path = Path(filepath)
        if not file_path.exists():
            return {"success": False, "error": "الملف غير موجود"}

        new_path = file_path.parent / new_name

        try:
            result = self.safe_mover.move(str(file_path), str(new_path))
            if not result.success:
                logger.error(f"فشل إعادة تسمية {filepath}: {result.error}")
                return {"success": False, "error": result.error or "safe_move failed"}
            self._record_action("rename", str(file_path), result.final_path, None)
            logger.info(f"تم إعادة تسمية: {file_path.name} -> {new_name}")
            return {"success": True, "new_path": result.final_path}
        except Exception as e:
            logger.error(f"خطأ في إعادة تسمية {filepath}: {e}")
            return {"success": False, "error": str(e)}

    def undo_last_action(self) -> dict:
        """التراجع عن آخر عملية باستخدام SafeMover (لا استبدال صامت للملف الجديد)."""
        if not self._action_history:
            return {"success": False, "error": "لا توجد عمليات للتراجع عنها"}

        action = self._action_history[-1]
        try:
            if action["type"] == "move":
                result = self.safe_mover.move(action["dest"], action["src"])
                if not result.success:
                    logger.error(f"فشل التراجع عن نقل: {result.error}")
                    return {"success": False, "error": result.error}
            elif action["type"] == "delete":
                backup = action.get("backup")
                if backup and Path(backup).exists():
                    result = self.safe_mover.move(backup, action["src"])
                    if not result.success:
                        logger.error(f"فشل التراجع عن حذف: {result.error}")
                        return {"success": False, "error": result.error}
            elif action["type"] == "rename":
                result = self.safe_mover.move(action["dest"], action["src"])
                if not result.success:
                    logger.error(f"فشل التراجع عن إعادة تسمية: {result.error}")
                    return {"success": False, "error": result.error}
            elif action["type"] == "delete_permanent":
                backup = action.get("backup")
                if backup and Path(backup).exists():
                    result = self.safe_mover.move(backup, action["src"])
                    if not result.success:
                        logger.error(f"فشل التراجع عن حذف نهائي: {result.error}")
                        return {"success": False, "error": result.error}

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
        pattern = "**/*" if recursive else "*"

        for item in dir_path.glob(pattern):
            if not item.is_file() or item.name.startswith("."):
                continue
            try:
                info = self.get_file_info(str(item))
                info["type"] = item.suffix.lstrip(".").lower() or "بدون_امتداد"
                results.append(info)
            except Exception as e:
                logger.debug(f"خطأ في مسح {item}: {e}")

        logger.info(f"تم مسح {len(results)} ملف في {directory}")
        return results

    def _backup_file(self, filepath: Path) -> Optional[str]:
        """نسخ ملف احتياطي عبر SafeMover"""
        try:
            self._backup_dir.mkdir(parents=True, exist_ok=True)
            backup = self._backup_dir / filepath.name
            if backup.exists():
                backup = self._backup_dir / f"{filepath.stem}_{datetime.now().timestamp()}{filepath.suffix}"
            result = self.safe_mover.copy(str(filepath), str(backup))
            if not result.success:
                logger.warning(f"لم يتم النسخ الاحتياطي: {result.error}")
                return None
            return str(result.final_path)
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
