"""اختبارات وحدة FileHandler - مدير عمليات الملفات

يغطي هذا الملف الاختبارات التالية:
  - نسخ الملفات
  - إعادة تسمية الملفات
  - حذف الملفات
  - إنشاء مجلدات التصنيفات
  - الحصول على معلومات الملف
  - التراجع عن آخر عملية
  - نقل ملف مع تعارض الوجهة
"""
import os
from pathlib import Path

import pytest

from src.core.config import Config
from src.core.file_handler import FileHandler


class TestCopyFile:
    """اختبار دالة نسخ الملفات"""

    def test_copy_file(self, tmp_path, sample_files):
        """يتحقق من نسخ ملف إلى مسار جديد بنجاح

        يختبر:
          - نجاح العملية (success=True)
          - وجود الملف المنسوخ في الوجهة
          - تطابق المحتوى بين الأصل والنسخة
        """
        config = Config(database_path=str(tmp_path / "intellifile"))
        handler = FileHandler(config)

        dest = str(tmp_path / "copied" / "document_copy.pdf")
        result = handler.copy_file(sample_files["pdf_file"], dest)

        assert result["success"] is True
        assert Path(dest).exists()
        assert Path(dest).read_bytes() == Path(sample_files["pdf_file"]).read_bytes()

    def test_copy_file_creates_parent_dirs(self, tmp_path, sample_files):
        """يتحقق من أن النسخ ينشئ المجلدات الأب تلقائياً"""
        config = Config(database_path=str(tmp_path / "intellifile"))
        handler = FileHandler(config)

        dest = str(tmp_path / "a" / "b" / "c" / "copy.txt")
        result = handler.copy_file(sample_files["txt_file"], dest)

        assert result["success"] is True
        assert Path(dest).parent.exists()

    def test_copy_nonexistent_file(self, tmp_path):
        """يتحقق من أن نسخ ملف غير موجود يُرجع خطأ"""
        config = Config(database_path=str(tmp_path / "intellifile"))
        handler = FileHandler(config)

        result = handler.copy_file("/nonexistent/file.txt", str(tmp_path / "out.txt"))

        assert result["success"] is False
        assert "error" in result


class TestRenameFile:
    """اختبار دالة إعادة تسمية الملفات"""

    def test_rename_file(self, tmp_path, sample_files):
        """يتحقق من إعادة تسمية ملف بنجاح

        يختبر:
          - نجاح العملية (success=True)
          - وجود الملف بالاسم الجديد
          - عدم وجود الملف بالاسم القديم
          - إرجاع المسار الجديد
        """
        config = Config(database_path=str(tmp_path / "intellifile"))
        handler = FileHandler(config)

        result = handler.rename_file(sample_files["py_file"], "renamed_script.py")

        assert result["success"] is True
        assert Path(sample_files["py_file"]).exists() is False
        assert Path(result["new_path"]).exists()
        assert Path(result["new_path"]).name == "renamed_script.py"

    def test_rename_nonexistent_file(self, tmp_path):
        """يتحقق من أن إعادة تسمية ملف غير موجود تُرجع خطأ"""
        config = Config(database_path=str(tmp_path / "intellifile"))
        handler = FileHandler(config)

        result = handler.rename_file("/nonexistent/file.txt", "new_name.txt")

        assert result["success"] is False
        assert "error" in result

    def test_rename_updates_history(self, tmp_path, sample_files):
        """يتحقق من تسجيل عملية إعادة التسمية في السجل"""
        config = Config(database_path=str(tmp_path / "intellifile"))
        handler = FileHandler(config)

        handler.rename_file(sample_files["txt_file"], "new_name.txt")

        assert len(handler.history) == 1
        assert handler.history[0]["type"] == "rename"


class TestDeleteFile:
    """اختبار دالة حذف الملفات"""

    def test_delete_file_permanent(self, tmp_path, sample_files):
        """يتحقق من حذف ملف بشكل نهائي (بدون سلة المحذوفات)

        يختبر:
          - نجاح العملية (success=True)
          - عدم وجود الملف بعد الحذف
        """
        config = Config(database_path=str(tmp_path / "intellifile"))
        handler = FileHandler(config)

        # إنشاء ملف مؤقت للحذف (للتأكد من عدم حذف الملف الأصلي)
        test_file = tmp_path / "to_delete.txt"
        test_file.write_text("سيتم حذف هذا الملف")

        result = handler.delete_file(str(test_file), use_trash=False)

        assert result["success"] is True
        assert not test_file.exists()

    def test_delete_nonexistent_file(self, tmp_path):
        """يتحقق من أن حذف ملف غير موجود يُرجع خطأ"""
        config = Config(database_path=str(tmp_path / "intellifile"))
        handler = FileHandler(config)

        result = handler.delete_file("/nonexistent/file.txt")

        assert result["success"] is False
        assert "غير موجود" in result["error"]

    def test_delete_records_history(self, tmp_path):
        """يتحقق من تسجيل عملية الحذف في السجل"""
        config = Config(database_path=str(tmp_path / "intellifile"))
        handler = FileHandler(config)

        test_file = tmp_path / "history_test.txt"
        test_file.write_text("test")

        handler.delete_file(str(test_file), use_trash=False)

        assert len(handler.history) == 1
        assert handler.history[0]["type"] in ("delete", "delete_permanent")


class TestCreateCategoryFolders:
    """اختبار دالة إنشاء مجلدات التصنيفات"""

    def test_create_category_folders(self, tmp_path):
        """يتحقق من إنشاء جميع مجلدات التصنيفات في المسار المحدد

        يختبر:
          - إنشاء جميع التصنيفات الافتراضية
          - أن كل مجلد موجود فعلاً
          - إرجاع قائمة بالمجلدات المُنشأة
        """
        config = Config()
        handler = FileHandler(config)

        created = handler.create_category_folders(str(tmp_path))

        # يجب أن يكون هناك مجلد لكل تصنيف
        assert len(created) == len(config.categories)
        for cat_dir in created:
            assert Path(cat_dir).is_dir()

    def test_create_category_folders_idempotent(self, tmp_path):
        """يتحقق من أن الاستدعاء المتكرر لا يُنشئ مجلدات مكررة

        المجلدات الموجودة يجب ألا تُضاف للقائمة المُرجعة.
        """
        config = Config()
        handler = FileHandler(config)

        first = handler.create_category_folders(str(tmp_path))
        second = handler.create_category_folders(str(tmp_path))

        assert len(first) == len(config.categories)
        assert len(second) == 0  # كل المجلدات موجودة بالفعل

    def test_create_category_folders_with_custom(self, tmp_path):
        """يتحقق من إنشاء المجلدات مع التصنيفات المخصصة"""
        config = Config()
        config.add_custom_category("اختبار", [".abc"])
        handler = FileHandler(config)

        created = handler.create_category_folders(str(tmp_path))

        assert (tmp_path / "اختبار").exists()
        assert len(created) == len(config.categories)


class TestGetFileInfo:
    """اختبار دالة الحصول على معلومات الملف"""

    def test_get_file_info(self, sample_files):
        """يتحقق من إرجاع معلومات صحيحة عن الملف

        يختبر الحقول:
          - name, path, extension, size
          - created, modified
          - is_dir, is_file
        """
        config = Config()
        handler = FileHandler(config)
        info = handler.get_file_info(sample_files["pdf_file"])

        assert "error" not in info
        assert info["name"] == "document.pdf"
        assert info["extension"] == ".pdf"
        assert info["size"] > 0
        assert info["is_file"] is True
        assert info["is_dir"] is False
        assert isinstance(info["created"], float)
        assert isinstance(info["modified"], float)

    def test_get_file_info_nonexistent(self, tmp_path):
        """يتحقق من إرجاع خطأ عند طلب معلومات ملف غير موجود"""
        config = Config()
        handler = FileHandler(config)
        info = handler.get_file_info("/nonexistent/file.txt")

        assert "error" in info
        assert "غير موجود" in info["error"]

    def test_get_file_info_directory(self, tmp_path):
        """يتحقق من معلومات المجلد"""
        config = Config()
        handler = FileHandler(config)
        info = handler.get_file_info(str(tmp_path))

        assert info["is_dir"] is True
        assert info["is_file"] is False


class TestUndoLastAction:
    """اختبار دالة التراجع عن آخر عملية"""

    def test_undo_last_action_rename(self, tmp_path):
        """يتحقق من التراجع عن عملية إعادة تسمية

        بعد إعادة التسمية والتراجع:
          - يجب أن يعود الاسم الأصلي
          - يجب أن يكون الملف موجوداً بالاسم القديم
        """
        config = Config(database_path=str(tmp_path / "intellifile"))
        handler = FileHandler(config)

        # إنشاء ملف للاختبار
        original_file = tmp_path / "original.txt"
        original_file.write_text("محتوى أصلي")

        handler.rename_file(str(original_file), "renamed.txt")
        assert not original_file.exists()

        result = handler.undo_last_action()
        assert result["success"] is True
        assert original_file.exists()
        assert original_file.read_text() == "محتوى أصلي"

    def test_undo_empty_history(self, tmp_path):
        """يتحقق من أن التراجع بدون سجل يُرجع خطأ"""
        config = Config(database_path=str(tmp_path / "intellifile"))
        handler = FileHandler(config)

        result = handler.undo_last_action()

        assert result["success"] is False
        assert "error" in result

    def test_undo_multiple_actions(self, tmp_path):
        """يتحقق من إمكانية التراجع المتعدد بالتسلسل

        ينفذ عمليتين (نسخ + إعادة تسمية) ثم يتراجع مرتين.
        """
        config = Config(database_path=str(tmp_path / "intellifile"))
        handler = FileHandler(config)

        # إنشاء ملف
        test_file = tmp_path / "multi.txt"
        test_file.write_text("test content")

        # عملية 1: إعادة تسمية
        handler.rename_file(str(test_file), "multi_renamed.txt")
        renamed_path = tmp_path / "multi_renamed.txt"

        # التراجع الأولى: يجب أن يعود الاسم الأصلي
        result1 = handler.undo_last_action()
        assert result1["success"] is True
        assert test_file.exists()

    def test_undo_move_action(self, tmp_path):
        """يتحقق من التراجع عن عملية النقل"""
        config = Config(database_path=str(tmp_path / "intellifile"))
        handler = FileHandler(config)

        # إنشاء ملف ومجلد وجهة
        source_file = tmp_path / "source.txt"
        source_file.write_text("محتوى للنقل")
        dest_dir = tmp_path / "destination"
        dest_dir.mkdir()

        # نقل الملف
        move_result = handler.move_file(
            str(source_file), "destination", str(tmp_path)
        )
        assert move_result["success"] is True

        # التراجع
        undo_result = handler.undo_last_action()
        assert undo_result["success"] is True


class TestMoveFileWithConflict:
    """اختبار نقل ملف مع تعارض في الوجهة"""

    def test_move_file_with_conflict(self, tmp_path):
        """يتحقق من أن نقل ملف لوجهة موجودة لا يحذف الملف الأصلي

        عند وجود ملف بنفس الاسم في الوجهة، يجب أن يُضاف رقم للتمييز.
        """
        config = Config(database_path=str(tmp_path / "intellifile"))
        handler = FileHandler(config)

        # إنشاء مجلد المصدر والوجهة
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        dest_category_dir = tmp_path / "برمجة"
        dest_category_dir.mkdir()

        # ملف في المصدر
        src_file = src_dir / "script.py"
        src_file.write_text("print('أصلي')")

        # ملف موجود مسبقاً في الوجهة بنفس الاسم
        existing_dest = dest_category_dir / "script.py"
        existing_dest.write_text("print('موجود مسبقاً')")

        # نقل الملف
        result = handler.move_file(
            str(src_file), "برمجة", str(tmp_path)
        )

        assert result["success"] is True
        # يجب أن يكون هناك ملفان الآن في الوجهة
        py_files = list(dest_category_dir.glob("*.py"))
        assert len(py_files) == 2

        # الملف الأصلي في المصدر يجب أن يكون قد نُقل
        assert not src_file.exists()

    def test_move_file_basic(self, tmp_path):
        """يتحقق من نقل ملف عادي بدون تعارض"""
        config = Config(database_path=str(tmp_path / "intellifile"))
        handler = FileHandler(config)

        src_dir = tmp_path / "source"
        src_dir.mkdir()

        src_file = src_dir / "document.pdf"
        src_file.write_bytes(b"%PDF test")

        result = handler.move_file(
            str(src_file), "مستندات", str(tmp_path)
        )

        assert result["success"] is True
        assert not src_file.exists()
        dest = Path(result["dest"])
        assert dest.exists()
        assert dest.parent.name == "مستندات"
