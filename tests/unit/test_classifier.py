"""اختبارات وحدة SmartFileClassifier - المصنف الذكي للملفات

يغطي هذا الملف الاختبارات التالية:
  - تصنيف ملف حسب امتداده
  - تصنيف ملف غير موجود
  - تصنيف دفعي لمجلد
  - إحصائيات التصنيف
  - تصنيف بالمحتوى بدون magika
"""
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.core.config import Config
from src.core.classifier import SmartFileClassifier


class TestClassifyFileByExtension:
    """اختبار تصنيف الملفات بناءً على امتدادها"""

    def test_classify_file_by_extension_pdf(self, sample_files):
        """يتحقق من تصنيف ملف PDF تحت 'مستندات'

        يختبر:
          - أن التصنيف صحيح
          - أن الامتداد صحيح
          - أن الثقة >= 75% (تصنيف بالقاعدة)
          - أن result لا يحتوي على خطأ
        """
        config = Config()
        classifier = SmartFileClassifier(config)
        # التأكد من عدم استخدام magika للاختبار القائم على القواعد
        classifier._magika = None
        result = classifier.classify_file(sample_files["pdf_file"])

        assert "error" not in result
        assert result["category"] == "مستندات"
        assert result["extension"] == ".pdf"
        assert result["confidence"] >= 85.0
        assert result["name"] == "document.pdf"
        assert result["size"] > 0

    def test_classify_file_by_extension_txt(self, sample_files):
        """يتحقق من تصنيف ملف نصي تحت 'مستندات'"""
        config = Config()
        classifier = SmartFileClassifier(config)
        result = classifier.classify_file(sample_files["txt_file"])

        assert result["category"] == "مستندات"
        assert result["extension"] == ".txt"

    def test_classify_file_by_extension_py(self, sample_files):
        """يتحقق من تصنيف ملف Python تحت 'برمجة'"""
        config = Config()
        classifier = SmartFileClassifier(config)
        result = classifier.classify_file(sample_files["py_file"])

        assert result["category"] == "برمجة"
        assert result["extension"] == ".py"

    def test_classify_file_by_extension_jpg(self, sample_files):
        """يتحقق من تصنيف صورة JPEG تحت 'صور'"""
        config = Config()
        classifier = SmartFileClassifier(config)
        result = classifier.classify_file(sample_files["jpg_file"])

        assert result["category"] == "صور"
        assert result["extension"] == ".jpg"

    def test_classify_file_by_extension_zip(self, sample_files):
        """يتحقق من تصنيف أرشيف ZIP تحت 'أرشيفات'"""
        config = Config()
        classifier = SmartFileClassifier(config)
        result = classifier.classify_file(sample_files["zip_file"])

        assert result["category"] == "أرشيفات"
        assert result["extension"] == ".zip"

    def test_classify_file_unknown_extension(self, sample_files):
        """يتحقق من أن الامتداد غير المعروف يُصنّف تحت 'أخرى'"""
        config = Config()
        classifier = SmartFileClassifier(config)
        result = classifier.classify_file(sample_files["unknown_file"])

        assert result["category"] == "أخرى"
        assert result["confidence"] >= 85.0

    def test_classify_file_empty_file(self, sample_files):
        """يتحقق من تصنيف ملف فارغ بشكل صحيح"""
        config = Config()
        classifier = SmartFileClassifier(config)
        result = classifier.classify_file(sample_files["empty_file"])

        assert "error" not in result
        assert result["size"] == 0
        assert result["category"] == "مستندات"  # .txt -> مستندات


class TestClassifyNonexistentFile:
    """اختبار تصنيف ملف غير موجود"""

    def test_classify_nonexistent_file_returns_error(self):
        """يتحقق من أن تصنيف ملف غير موجود يُرجع قاموساً يحتوي خطأ

        يجب أن يحتوي على:
          - مفتاح 'error'
          - رسالة توضح أن الملف غير موجود
        """
        config = Config()
        classifier = SmartFileClassifier(config)
        result = classifier.classify_file("/tmp/does_not_exist_file_12345.xyz")

        assert "error" in result
        assert "غير موجود" in result["error"]

    def test_classify_nonexistent_file_no_crash(self):
        """يتحقق من أن تصنيف مسار غير صالح لا يُسبب استثناء"""
        config = Config()
        classifier = SmartFileClassifier(config)
        classifier._magika = None

        # مسار غير موجود فعلاً (لا يجب أن يحل للمجلد الحالي)
        result = classifier.classify_file("/nonexistent/path/__/file.xyz999")
        assert "error" in result


class TestBatchClassify:
    """اختبار التصنيف الدفعي لمجلد"""

    def test_batch_classify_directory(self, tmp_dir):
        """يتحقق من تصنيف جميع الملفات في المجلد بشكل صحيح

        يختبر:
          - أن عدد النتائج يساوي عدد الملفات (بما فيها المجلدات الفرعية)
          - أن كل نتيجة تحتوي الحقول المطلوبة
          - أن التصنيفات صحيحة لكل امتداد
        """
        config = Config()
        classifier = SmartFileClassifier(config)
        results = classifier.batch_classify(str(tmp_dir))

        # يجب أن يكون هناك نتائج (الملفات الرئيسية + المجلد الفرعي)
        assert len(results) >= 5

        # التحقق من أن كل نتيجة تحتوي الحقول المطلوبة
        required_fields = {"name", "path", "extension", "category", "confidence", "size"}
        for result in results:
            assert required_fields.issubset(result.keys())

        # التحقق من وجود تصنيفات مختلفة
        categories = {r["category"] for r in results}
        assert "مستندات" in categories  # .pdf, .txt, .csv
        assert "برمجة" in categories     # .py, .js

    def test_batch_classify_nonexistent_directory(self):
        """يتحقق من أن تصنيف مجلد غير موجود يُرجع قائمة فارغة"""
        config = Config()
        classifier = SmartFileClassifier(config)
        results = classifier.batch_classify("/tmp/nonexistent_dir_99999")

        assert results == []

    def test_batch_classify_empty_directory(self, tmp_path):
        """يتحقق من أن تصنيف مجلد فارغ يُرجع قائمة فارغة"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        config = Config()
        classifier = SmartFileClassifier(config)
        results = classifier.batch_classify(str(empty_dir))

        assert results == []

    def test_batch_classify_ignores_hidden_files(self, tmp_path):
        """يتحقق من أن الملفات المخفية (التي تبدأ بنقطة) لا تُصنَّف"""
        # إنشاء ملفات مخفية
        (tmp_path / ".hidden_file.txt").write_text("مخفي")
        (tmp_path / "visible_file.txt").write_text("ظاهر")

        config = Config()
        classifier = SmartFileClassifier(config)
        results = classifier.batch_classify(str(tmp_path))

        # يجب أن يوجد ملف واحد فقط
        assert len(results) == 1
        assert results[0]["name"] == "visible_file.txt"

    def test_batch_classify_includes_nested(self, tmp_dir):
        """يتحقق من أن التصنيف يشمل الملفات في المجلدات الفرعية"""
        config = Config()
        classifier = SmartFileClassifier(config)
        results = classifier.batch_classify(str(tmp_dir))

        # البحث عن الملفات المتداخلة
        names = {r["name"] for r in results}
        assert "document.docx" in names  # داخل مجلد_فرعي
        assert "song.mp3" in names       # داخل مجلد_فرعي


class TestGetStats:
    """اختبار دالة get_stats للإحصائيات"""

    def test_get_stats_empty_list(self):
        """يتحقق من أن قائمة فارغة تُرجع إحصائيات فارغة"""
        config = Config()
        classifier = SmartFileClassifier(config)
        stats = classifier.get_stats([])

        assert stats == {}

    def test_get_stats_single_category(self):
        """يتحقق من الإحصائيات مع ملفات من تصنيف واحد"""
        config = Config()
        classifier = SmartFileClassifier(config)

        results = [
            {"category": "مستندات"},
            {"category": "مستندات"},
            {"category": "مستندات"},
        ]
        stats = classifier.get_stats(results)

        assert stats == {"مستندات": 3}

    def test_get_stats_multiple_categories(self):
        """يتحقق من الإحصائيات مع تصنيفات متعددة"""
        config = Config()
        classifier = SmartFileClassifier(config)

        results = [
            {"category": "مستندات"},
            {"category": "مستندات"},
            {"category": "صور"},
            {"category": "برمجة"},
            {"category": "صور"},
            {"category": "برمجة"},
            {"category": "أخرى"},
        ]
        stats = classifier.get_stats(results)

        assert stats["مستندات"] == 2
        assert stats["صور"] == 2
        assert stats["برمجة"] == 2
        assert stats["أخرى"] == 1

    def test_get_stats_from_batch_classify(self, tmp_dir):
        """يتحقق من صحة الإحصائيات بعد تصنيف دفعي فعلي"""
        config = Config()
        classifier = SmartFileClassifier(config)
        results = classifier.batch_classify(str(tmp_dir))
        stats = classifier.get_stats(results)

        # المجموع يجب أن يساوي عدد النتائج
        total = sum(stats.values())
        assert total == len(results)

        # يجب أن يوجد تصنيف واحد على الأقل
        assert len(stats) > 0


class TestClassifyByContent:
    """اختبار تصنيف الملف بناءً على محتواه"""

    def test_classify_by_content_without_magika(self, sample_files):
        """يتحقق من أن classify_by_content يُرجع 'أخرى' بدون magika

        عندما لا تكون مكتبة magika متاحة، يجب أن يُرجع 'أخرى'
        """
        config = Config()
        classifier = SmartFileClassifier(config)

        # التأكد من أن magika غير متاح
        classifier._magika = None

        result = classifier.classify_by_content(sample_files["pdf_file"])
        assert result == "أخرى"

    def test_classify_by_content_with_magika_mock(self, sample_files):
        """يتحقق من أن classify_by_content يستخدم magika عند توفرها

        يُحاكي كائن magika يُرجع نوع 'pdf' ويختبر أن التصنيف صحيح.
        """
        config = Config()
        classifier = SmartFileClassifier(config)

        # محاكاة magika
        mock_magika = MagicMock()
        mock_result = MagicMock()
        mock_result.output = "pdf"
        mock_magika.identify_path.return_value = mock_result
        classifier._magika = mock_magika

        result = classifier.classify_by_content(sample_files["txt_file"])
        assert result == "مستندات"

    def test_classify_by_content_magika_error(self, sample_files):
        """يتحقق من أن classify_by_content يُرجع 'أخرى' عند خطأ magika

        عندما يطرح magika استثناء، يجب أن يُرجع 'أخرى' بدون انهيار.
        """
        config = Config()
        classifier = SmartFileClassifier(config)

        # محاكاة magika يطرح استثناء
        mock_magika = MagicMock()
        mock_magika.identify_path.side_effect = RuntimeError("خطأ في القراءة")
        classifier._magika = mock_magika

        result = classifier.classify_by_content(sample_files["pdf_file"])
        assert result == "أخرى"


class TestMagikaIntegration:
    """اختبار تكامل magika مع المصنف"""

    def test_magika_not_installed_gracefully(self):
        """يتحقق من أن المصنف يعمل بدون magika"""
        config = Config()

        # بدون mock - إذا لم يكن magika مثبتاً
        with patch.dict("sys.modules", {"magika": None}):
            classifier = SmartFileClassifier(config)
            assert classifier._magika is None

    def test_classify_file_with_magika_override(self, sample_files):
        """يتحقق من أن magika يُغيِّر التصنيف عند اختلافه عن الامتداد

        يُحاكي magika يعيد تصنيف ملف .unknown_ext على أنه مستند.
        """
        config = Config()
        classifier = SmartFileClassifier(config)

        # محاكاة magika يكتشف محتوى pdf
        mock_magika = MagicMock()
        mock_result = MagicMock()
        mock_result.output = "pdf"
        mock_magika.identify_path.return_value = mock_result
        classifier._magika = mock_magika

        result = classifier.classify_file(sample_files["unknown_file"])
        # يجب أن يتفوق تصنيف المحتوى (pdf -> مستندات) على الامتداد (أخرى)
        assert result["category"] == "مستندات"
        assert result["confidence"] == 95.0
        assert result["content_type"] == "pdf"
