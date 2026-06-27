"""اختبارات وحدة Config - إعدادات التطبيق الرئيسية

يغطي هذا الملف الاختبارات التالية:
  - القيم الافتراضية للإعدادات
  - تصنيف الامتدادات المعروفة وغير المعروفة
  - إضافة تصنيفات مخصصة
  - حفظ وتحميل الإعدادات
  - تحميل ملف غير موجود
  - اكتمال خريطة الامتدادات
"""
import json
from pathlib import Path

import pytest

from src.core.config import Config, CATEGORIES, EXTENSION_MAP


class TestDefaultConfigValues:
    """اختبار القيم الافتراضية للإعدادات"""

    def test_default_categories_match_global(self):
        """يتحقق من أن التصنيفات الافتراضية تتطابق مع القائمة العامة"""
        config = Config()
        assert config.categories == list(CATEGORIES)

    def test_default_extension_map_match_global(self):
        """يتحقق من أن خريطة الامتدادات الافتراضية تتطابق مع القاموس العام"""
        config = Config()
        assert config.extension_map == dict(EXTENSION_MAP)

    def test_default_ai_model(self):
        """يتحقق من أن النموذج الافتراضي هو llama3.2"""
        config = Config()
        assert config.ai_model == "llama3.2"

    def test_default_ollama_url(self):
        """يتحقق من أن رابط Ollama الافتراضي هو localhost:11434"""
        config = Config()
        assert config.ollama_url == "http://localhost:11434"

    def test_default_language(self):
        """يتحقق من أن اللغة الافتراضية هي العربية"""
        config = Config()
        assert config.language == "ar"

    def test_default_dark_mode(self):
        """يتحقق من أن الوضع الداكن مُفعّل افتراضياً"""
        config = Config()
        assert config.dark_mode is True

    def test_default_auto_classify(self):
        """يتحقق من أن التصنيف التلقائي مُفعّل افتراضياً"""
        config = Config()
        assert config.auto_classify is True

    def test_default_duplicate_detection(self):
        """يتحقق من أن كشف المكررات مُفعّل افتراضياً"""
        config = Config()
        assert config.duplicate_detection is True

    def test_default_file_protection(self):
        """يتحقق من أن حماية الملفات مُفعّلة افتراضياً"""
        config = Config()
        assert config.file_protection is True

    def test_default_voice_disabled(self):
        """يتحقق من أن التحكم الصوتي معطّل افتراضياً"""
        config = Config()
        assert config.voice_enabled is False

    def test_default_watch_directories_empty(self):
        """يتحقق من أن قائمة المراقبة فارغة افتراضياً"""
        config = Config()
        assert config.watch_directories == []

    def test_default_custom_categories_empty(self):
        """يتحقق من أن التصنيفات المخصصة فارغة افتراضياً"""
        config = Config()
        assert config.custom_categories == []

    def test_default_database_path(self):
        """يتحقق من أن مسار قاعدة البيانات الافتراضي يحتوي .intellifile"""
        config = Config()
        assert ".intellifile" in config.database_path


class TestGetCategory:
    """اختبار دالة get_category لتصنيف الامتدادات"""

    def test_get_category_known_extensions(self):
        """يتحقق من تصنيف مجموعة من الامتدادات المعروفة بشكل صحيح

        يختبر امتدادات من كل تصنيف رئيسي:
          مستندات، صور، فيديو، صوت، أرشيفات، برمجة، أنظمة، خطوط
        """
        config = Config()

        # مستندات
        assert config.get_category(".pdf") == "مستندات"
        assert config.get_category(".docx") == "مستندات"
        assert config.get_category(".txt") == "مستندات"
        assert config.get_category(".csv") == "مستندات"

        # صور
        assert config.get_category(".jpg") == "صور"
        assert config.get_category(".png") == "صور"
        assert config.get_category(".svg") == "صور"

        # فيديو
        assert config.get_category(".mp4") == "فيديو"
        assert config.get_category(".mkv") == "فيديو"

        # صوت
        assert config.get_category(".mp3") == "صوت"
        assert config.get_category(".wav") == "صوت"

        # أرشيفات
        assert config.get_category(".zip") == "أرشيفات"
        assert config.get_category(".tar.gz") == "أرشيفات"

        # برمجة
        assert config.get_category(".py") == "برمجة"
        assert config.get_category(".js") == "برمجة"
        assert config.get_category(".rs") == "برمجة"

        # أنظمة
        assert config.get_category(".exe") == "أنظمة"
        assert config.get_category(".dll") == "أنظمة"

        # خطوط
        assert config.get_category(".ttf") == "خطوط"
        assert config.get_category(".woff2") == "خطوط"

    def test_get_category_unknown_extensions(self):
        """يتحقق من أن الامتدادات غير المعروفة تُصنّف تحت 'أخرى'

        يشمل: امتدادات وهمية وامتدادات بأحرف كبيرة
        """
        config = Config()

        # امتدادات غير موجودة في الخريطة
        assert config.get_category(".xyz123") == "أخرى"
        assert config.get_category(".foobar") == "أخرى"
        assert config.get_category(".data") == "أخرى"

        # حالة الحروف الكبيرة يجب أن تُعالج
        assert config.get_category(".PDF") == "مستندات"
        assert config.get_category(".PY") == "برمجة"

        # بدون نقطة
        assert config.get_category("pdf") == "أخرى"

    def test_get_category_uppercase_handled(self):
        """يتحقق من أن get_category يتجاهل حالة الأحرف"""
        config = Config()
        assert config.get_category(".PDF") == "مستندات"
        assert config.get_category(".Jpg") == "صور"
        assert config.get_category(".MP3") == "صوت"
        assert config.get_category(".ZIP") == "أرشيفات"


class TestAddCustomCategory:
    """اختبار دالة add_custom_category"""

    def test_add_new_category_with_extensions(self):
        """يتحقق من إضافة تصنيف مخصص جديد مع امتداداته"""
        config = Config()

        config.add_custom_category("أبحاث", [".paper", ".thesis", ".research"])

        assert "أبحاث" in config.categories
        assert "أبحاث" in config.custom_categories
        assert config.get_category(".paper") == "أبحاث"
        assert config.get_category(".thesis") == "أبحاث"
        assert config.get_category(".research") == "أبحاث"

    def test_add_category_name_only(self):
        """يتحقق من إضافة تصنيف بدون تحديد امتدادات"""
        config = Config()

        config.add_custom_category("مخصص")

        assert "مخصص" in config.categories
        assert "مخصص" in config.custom_categories

    def test_add_duplicate_category_does_not_duplicate(self):
        """يتحقق من أن إضافة تصنيف موجود لا يُنشئ تكراراً في القائمة"""
        config = Config()
        initial_len = len(config.categories)

        config.add_custom_category("مستندات", [".paper"])

        # لا يوجد تكرار في القائمة
        assert len(config.categories) == initial_len
        assert config.categories.count("مستندات") == 1
        # لكن الامتداد يُضاف
        assert config.get_category(".paper") == "مستندات"

    def test_add_multiple_custom_categories(self):
        """يتحقق من إضافة عدة تصنيفات مخصصة متتالية"""
        config = Config()

        config.add_custom_category("أبحاث", [".paper"])
        config.add_custom_category("تصاميم", [".sketch", ".figma"])
        config.add_custom_category("بيانات", [".sql", ".db"])

        assert "أبحاث" in config.categories
        assert "تصاميم" in config.categories
        assert "بيانات" in config.categories
        assert len(config.custom_categories) == 3
        assert config.get_category(".figma") == "تصاميم"
        assert config.get_category(".db") == "بيانات"

    def test_extension_case_normalized(self):
        """يتحقق من أن الامتدادات المضافة تُحوَّل لحروف صغيرة"""
        config = Config()

        config.add_custom_category("اختبار", [".PDF", ".DOC", ".CSV"])

        assert config.get_category(".pdf") == "اختبار"
        assert config.get_category(".doc") == "اختبار"
        assert config.get_category(".csv") == "اختبار"


class TestSaveAndLoadConfig:
    """اختبار حفظ وتحميل الإعدادات من ملف JSON"""

    def test_save_and_load_config(self, tmp_path):
        """يتحقق من أن حفظ الإعدادات ثم تحميلها يُرجع نفس القيم

        يختبر:
          - حفظ إعدادات مُخصَّصة في ملف JSON
          - تحميلها والتحقق من تطابق جميع الحقول
        """
        config_path = tmp_path / "test_config.json"
        original = Config(
            ai_model="llama3",
            language="en",
            dark_mode=False,
            auto_classify=False,
        )
        original.add_custom_category("مخصص", [".abc"])

        # حفظ
        original.save(str(config_path))
        assert config_path.exists()

        # تحميل
        loaded = Config.load(str(config_path))

        assert loaded.ai_model == "llama3"
        assert loaded.language == "en"
        assert loaded.dark_mode is False
        assert loaded.auto_classify is False
        assert "مخصص" in loaded.categories
        assert loaded.get_category(".abc") == "مخصص"

    def test_save_creates_parent_directories(self, tmp_path):
        """يتحقق من أن الحفظ ينشئ المجلدات الأب إذا لم تكن موجودة"""
        deep_path = tmp_path / "a" / "b" / "c" / "config.json"
        config = Config()

        config.save(str(deep_path))

        assert deep_path.exists()
        assert deep_path.parent.exists()

    def test_saved_json_is_valid(self, tmp_path):
        """يتحقق من أن الملف المحفوظ هو JSON صالح ويحتوي جميع الحقول"""
        config_path = tmp_path / "config.json"
        config = Config()
        config.save(str(config_path))

        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        expected_fields = [
            "categories", "extension_map", "ai_model", "ollama_url",
            "database_path", "language", "dark_mode", "auto_classify",
            "duplicate_detection", "file_protection", "voice_enabled",
            "watch_directories", "custom_categories",
        ]
        for field in expected_fields:
            assert field in data, f"الحقل '{field}' مفقود من JSON"

    def test_config_load_nonexistent_file_returns_defaults(self, tmp_path):
        """يتحقق من أن تحميل ملف غير موجود يُرجع إعدادات افتراضية"""
        nonexistent = tmp_path / "does_not_exist" / "config.json"
        assert not nonexistent.exists()

        config = Config.load(str(nonexistent))

        # يجب أن تكون جميع القيم افتراضية
        defaults = Config()
        assert config.ai_model == defaults.ai_model
        assert config.language == defaults.language
        assert config.dark_mode == defaults.dark_mode
        assert config.categories == defaults.categories
        assert config.extension_map == defaults.extension_map

    def test_load_partial_config_merges_with_defaults(self, tmp_path):
        """يتحقق من أن تحميل ملف جزئي يدمجه مع القيم الافتراضية"""
        config_path = tmp_path / "partial.json"
        # كتابة ملف يحتوي حقلين فقط
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"ai_model": "phi3", "dark_mode": False}, f, ensure_ascii=False)

        config = Config.load(str(config_path))

        assert config.ai_model == "phi3"
        assert config.dark_mode is False
        # باقي الحقول من الافتراضي
        assert config.language == "ar"
        assert config.auto_classify is True
        assert config.categories == list(CATEGORIES)


class TestExtensionMapCompleteness:
    """اختبار اكتمال واتساق خريطة الامتدادات"""

    def test_extension_map_completeness(self):
        """يتحقق من أن جميع التصنيفات المعرَّفة في CATEGORIES
        لها امتدادات مقابلة في EXTENSION_MAP، ما عدا 'أخرى'"""
        config = Config()
        categories_with_extensions = set(config.extension_map.values())

        # 'أخرى' لا تحتاج امتدادات صريحة
        for cat in config.categories:
            if cat != "أخرى":
                assert cat in categories_with_extensions, (
                    f"التصنيف '{cat}' ليس له امتدادات في خريطة الامتدادات"
                )

    def test_all_extensions_have_leading_dot(self):
        """يتحقق من أن جميع المفاتيح في خريطة الامتدادات تبدأ بنقطة"""
        for ext in EXTENSION_MAP:
            assert ext.startswith("."), f"الامتداد '{ext}' لا يبدأ بنقطة"

    def test_no_empty_categories(self):
        """يتحقق من عدم وجود تصنيفات فارغة"""
        config = Config()
        assert all(len(cat.strip()) > 0 for cat in config.categories)

    def test_extension_map_values_are_valid_categories(self):
        """يتحقق من أن جميع قيم خريطة الامتدادات تشير لتصنيفات صالحة"""
        config = Config()
        valid = set(config.categories)
        for ext, cat in config.extension_map.items():
            assert cat in valid, (
                f"الامتداد '{ext}' يشير لتصنيف غير معروف '{cat}'"
            )
