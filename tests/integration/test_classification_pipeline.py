"""اختبارات تكامل خط أنابيب التصنيف - classify → organize

يغطي هذا الملف الاختبارات التالية:
  - سير عمل التصنيف ثم التنظيم
  - التصنيف الدفعي مع الإحصائيات
"""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.core.config import Config
from src.core.classifier import SmartFileClassifier
from src.core.file_handler import FileHandler


class TestClassifyAndOrganizeWorkflow:
    """اختبار سير عمل التصنيف ثم التنظيم المتكامل

    يحاكي السيناريو الكامل:
      1. تصنيف الملفات في مجلد
      2. إنشاء مجلدات التصنيفات
      3. نقل كل ملف لمجلده المناسب
      4. التحقق من صحة النقل
    """

    def test_classify_and_organize_workflow(self, tmp_dir):
        """يتحقق من اكتمال سير عمل التصنيف والتنظيم

        السيناريو:
          - مجلد يحتوي ملفات متنوعة (.pdf, .py, .jpg, .txt, .zip)
          - المصنف يُصنّفها حسب الامتداد
          - المُنظِّم ينشئ المجلدات وينقل الملفات
          - التحقق من أن كل ملف في مكانه الصحيح
        """
        config = Config()
        classifier = SmartFileClassifier(config)
        handler = FileHandler(config)

        # الخطوة 1: تصنيف جميع الملفات
        results = classifier.batch_classify(str(tmp_dir))
        assert len(results) > 0

        # الخطوة 2: إنشاء مجلدات التصنيفات
        created_folders = handler.create_category_folders(str(tmp_dir))
        assert len(created_folders) > 0

        # الخطوة 3: نقل كل ملف لمجلده
        moved_files = []
        for result in results:
            move_result = handler.move_file(
                result["path"], result["category"], str(tmp_dir)
            )
            if move_result["success"]:
                moved_files.append(move_result)

        assert len(moved_files) > 0

        # الخطوة 4: التحقق من أن الملفات في المجلدات الصحيحة
        for move_result in moved_files:
            dest_path = Path(move_result["dest"])
            assert dest_path.exists(), f"الملف غير موجود: {dest_path}"
            # المجلد الأب يجب أن يكون اسم التصنيف
            parent_name = dest_path.parent.name
            assert parent_name in config.categories, (
                f"الملف {dest_path.name} في مجلد غير معروف: {parent_name}"
            )

    def test_classify_and_organize_with_custom_categories(self, tmp_path):
        """يتحقق من سير العمل مع تصنيفات مخصصة"""
        config = Config()
        config.add_custom_category("اختبارات", [".xyz123"])

        # إنشاء ملفات
        (tmp_path / "data.xyz123").write_bytes(b"custom data")
        (tmp_path / "report.pdf").write_bytes(b"%PDF fake")

        classifier = SmartFileClassifier(config)
        handler = FileHandler(config)

        results = classifier.batch_classify(str(tmp_path))
        handler.create_category_folders(str(tmp_path))

        for result in results:
            handler.move_file(result["path"], result["category"], str(tmp_path))

        # التحقق من وجود مجلد الاختبارات ووجود الملف بداخله
        test_dir = tmp_path / "اختبارات"
        assert test_dir.is_dir()
        xyz_files = list(test_dir.glob("*.xyz123"))
        assert len(xyz_files) == 1

    def test_classify_and_undo_organize(self, tmp_dir):
        """يتحقق من إمكانية التراجع بعد التنظيم

        بعد نقل الملفات والتراجع:
          - يجب أن تُنقل الملفات لأماكنها الأصلية (أو يُستعاد النسخ الاحتياطي)
        """
        config = Config(database_path=str(tmp_dir / "intellifile"))
        classifier = SmartFileClassifier(config)
        handler = FileHandler(config)

        # تصنيف ونقل ملف واحد فقط للتبسيط
        results = classifier.batch_classify(str(tmp_dir))
        if results:
            result = results[0]
            original_path = result["path"]

            handler.create_category_folders(str(tmp_dir))
            move_result = handler.move_file(
                original_path, result["category"], str(tmp_dir)
            )

            if move_result["success"]:
                # التراجع
                undo = handler.undo_last_action()
                assert undo["success"] is True


class TestBatchClassifyWithStats:
    """اختبار التصنيف الدفعي مع الإحصائيات"""

    def test_batch_classify_with_stats(self, tmp_dir):
        """يتحقق من أن التصنيف الدفعي يُنتج إحصائيات صحيحة

        يختبر:
          - أن مجموع الملفات المصنفة = مجموع الإحصائيات
          - أن كل تصنيف في الإحصائيات له عدد > 0
          - أن أسماء التصنيفات صحيحة
        """
        config = Config()
        classifier = SmartFileClassifier(config)

        # تصنيف دفعي
        results = classifier.batch_classify(str(tmp_dir))
        assert len(results) > 0

        # حساب الإحصائيات
        stats = classifier.get_stats(results)
        assert len(stats) > 0

        # التحقق من أن المجموع = عدد النتائج
        total_from_stats = sum(stats.values())
        assert total_from_stats == len(results)

        # التحقق من أن كل التصنيفات معروفة
        for category in stats:
            assert category in config.categories

    def test_batch_classify_stats_distribution(self, tmp_path):
        """يتحقق من توزيع الإحصائيات مع ملفات من أنواع محددة

        ينشئ 5 ملفات نصية و3 صور ويتحقق من التوزيع.
        """
        # إنشاء ملفات محددة
        for i in range(5):
            (tmp_path / f"doc{i}.txt").write_text(f"مستند {i}")
        for i in range(3):
            (tmp_path / f"img{i}.jpg").write_bytes(b"\xff\xd8 fake")

        config = Config()
        classifier = SmartFileClassifier(config)
        results = classifier.batch_classify(str(tmp_path))
        stats = classifier.get_stats(results)

        assert stats.get("مستندات", 0) == 5
        assert stats.get("صور", 0) == 3
        assert sum(stats.values()) == 8

    def test_batch_classify_single_type(self, tmp_path):
        """يتحقق من الإحصائيات مع ملفات من نوع واحد فقط"""
        for i in range(4):
            (tmp_path / f"code{i}.py").write_text(f"print({i})")

        config = Config()
        classifier = SmartFileClassifier(config)
        results = classifier.batch_classify(str(tmp_path))
        stats = classifier.get_stats(results)

        assert len(stats) == 1
        assert stats.get("برمجة", 0) == 4

    def test_batch_classify_large_directory(self, tmp_path):
        """يتحقق من أداء التصنيف الدفعي مع عدد كبير من الملفات"""
        # إنشاء 50 ملف من أنواع مختلفة
        extensions = [".txt", ".py", ".jpg", ".pdf", ".zip", ".mp3", ".csv"]
        for i in range(50):
            ext = extensions[i % len(extensions)]
            (tmp_path / f"file_{i:03d}{ext}").write_bytes(b"test data")

        config = Config()
        classifier = SmartFileClassifier(config)
        results = classifier.batch_classify(str(tmp_path))

        assert len(results) == 50

        stats = classifier.get_stats(results)
        assert sum(stats.values()) == 50
