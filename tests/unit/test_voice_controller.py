"""اختبارات وحدة VoiceController - وحدة التحكم الصوتي

يغطي هذا الملف الاختبارات التالية:
  - تحليل أمر التصنيف
  - تحليل أمر البحث
  - تحليل أمر الحذف
  - تحليل أمر غير معروف (يجب أن يُرجع إجراء محادثة)
"""
from unittest.mock import MagicMock, patch

import pytest

from src.core.voice_controller import VoiceController


class TestVoiceControllerInit:
    """اختبار تهيئة وحدة التحكم الصوتي"""

    def test_init_default_language(self):
        """يتحقق من أن اللغة الافتراضية هي العربية السعودية"""
        vc = VoiceController()
        assert vc.language == "ar-SA"

    def test_init_custom_language(self):
        """يتحقق من إمكانية ضبط لغة مخصصة"""
        vc = VoiceController(language="en-US")
        assert vc.language == "en-US"

    def test_init_no_recognizer_without_speech_recognition(self):
        """يتحقق من أن المحلل يظل None إذا لم تكن المكتبة متاحة"""
        with patch.dict("sys.modules", {"speech_recognition": None}):
            vc = VoiceController()
            assert vc._recognizer is None

    def test_init_no_tts_without_pyttsx3(self):
        """يتحقق من أن محرك النطق يظل None إذا لم تكن المكتبة متاحة"""
        with patch.dict("sys.modules", {"pyttsx3": None}):
            vc = VoiceController()
            assert vc._tts_engine is None


class TestParseCommandClassify:
    """اختبار تحليل أوامر التصنيف الصوتية"""

    def test_parse_command_classify_simple(self):
        """يتحقق من تحليل أمر 'صنف' بسيط"""
        vc = VoiceController()
        result = vc.parse_command("صنف")

        assert result["action"] == "classify"
        assert result["target"] == "all"
        assert result.get("params") is None

    def test_parse_command_classify_with_tashkeel(self):
        """يتحقق من تحليل أمر 'صنّف' (مع التشكيل)"""
        vc = VoiceController()
        result = vc.parse_command("صنّف")

        assert result["action"] == "classify"
        assert result["target"] == "all"

    def test_parse_command_classify_with_params(self):
        """يتحقق من تحليل أمر تصنيف مع معاملات"""
        vc = VoiceController()
        result = vc.parse_command("صنف المجلد الرئيسي")

        assert result["action"] == "classify"
        assert result["params"] == "المجلد الرئيسي"


class TestParseCommandSearch:
    """اختبار تحليل أوامر البحث الصوتية"""

    def test_parse_command_search_simple(self):
        """يتحقق من تحليل أمر 'ابحث' بسيط"""
        vc = VoiceController()
        result = vc.parse_command("ابحث")

        assert result["action"] == "search"
        assert result["target"] == "query"

    def test_parse_command_search_with_query(self):
        """يتحقق من تحليل أمر بحث مع نص البحث"""
        vc = VoiceController()
        result = vc.parse_command("ابحث تقارير المبيعات")

        assert result["action"] == "search"
        assert result["params"] == "تقارير المبيعات"

    def test_parse_command_search_long_query(self):
        """يتحقق من تحليل أمر بحث بنص طويل"""
        vc = VoiceController()
        result = vc.parse_command("ابحث عن ملفات المشروع السنوي")

        assert result["action"] == "search"
        assert result["params"] == "عن ملفات المشروع السنوي"


class TestParseCommandDelete:
    """اختبار تحليل أوامر الحذف الصوتية"""

    def test_parse_command_delete_simple(self):
        """يتحقق من تحليل أمر 'احذف' بسيط"""
        vc = VoiceController()
        result = vc.parse_command("احذف")

        assert result["action"] == "delete"
        assert result["target"] == "selected"

    def test_parse_command_delete_with_params(self):
        """يتحقق من تحليل أمر حذف مع معاملات"""
        vc = VoiceController()
        result = vc.parse_command("احذف الملفات القديمة")

        assert result["action"] == "delete"
        assert result["params"] == "الملفات القديمة"


class TestParseCommandUnknown:
    """اختبار تحليل أوامر غير معروفة"""

    def test_parse_command_unknown_returns_chat(self):
        """يتحقق من أن الأمر غير المعروف يُرجع إجراء 'chat'

        أي نص لا يحتوي كلمة مفتاحية معروفة يجب أن يُمرر
        للمساعد الذكي كمحادثة.
        """
        vc = VoiceController()
        result = vc.parse_command("مرحباً كيف حالك")

        assert result["action"] == "chat"
        assert result["params"] == "مرحباً كيف حالك"

    def test_parse_command_unknown_arabic_text(self):
        """يتحقق من أن نص عربي عادي يُعامل كمحادثة"""
        vc = VoiceController()
        result = vc.parse_command("ما هو عدد الملفات الموجودة")

        assert result["action"] == "chat"

    def test_parse_command_unknown_english_text(self):
        """يتحقق من أن النص الإنجليزي يُعامل كمحادثة"""
        vc = VoiceController()
        result = vc.parse_command("hello world")

        assert result["action"] == "chat"
        assert result["params"] == "hello world"


class TestParseCommandOtherActions:
    """اختبار تحليل باقي الأوامر الصوتية"""

    def test_parse_command_open(self):
        """يتحقق من تحليل أمر 'افتح'"""
        vc = VoiceController()
        result = vc.parse_command("افتح المجلد")

        assert result["action"] == "open"
        assert result["target"] == "folder"

    def test_parse_command_move(self):
        """يتحقق من تحليل أمر 'انقل'"""
        vc = VoiceController()
        result = vc.parse_command("انقل")

        assert result["action"] == "move"
        assert result["target"] == "selected"

    def test_parse_command_summarize(self):
        """يتحقق من تحليل أمر 'ملخص'"""
        vc = VoiceController()
        result = vc.parse_command("ملخص")

        assert result["action"] == "summarize"
        assert result["target"] == "selected"

    def test_parse_command_summarize_tashkeel(self):
        """يتحقق من تحليل أمر 'لخّص' (مع التشكيل)"""
        vc = VoiceController()
        result = vc.parse_command("لخّص التقرير")

        assert result["action"] == "summarize"

    def test_parse_command_stop(self):
        """يتحقق من تحليل أمر 'توقف'"""
        vc = VoiceController()
        result = vc.parse_command("توقف")

        assert result["action"] == "stop"

    def test_parse_command_undo(self):
        """يتحقق من تحليل أمر 'إلغاء'"""
        vc = VoiceController()
        result = vc.parse_command("إلغاء")

        assert result["action"] == "undo"

    def test_parse_command_undo_alt(self):
        """يتحقق من تحليل أمر 'رجع' (بديل للإلغاء)"""
        vc = VoiceController()
        result = vc.parse_command("رجع")

        assert result["action"] == "undo"


class TestListen:
    """اختبار دالة الاستماع"""

    def test_listen_no_recognizer_returns_error(self):
        """يتحقق من أن الاستماع بدون محلل يُرجع رسالة خطأ"""
        vc = VoiceController()
        vc._recognizer = None

        result = vc.listen()

        assert "خطأ" in result

    def test_speak_no_engine_no_crash(self):
        """يتحقق من أن النطق بدون محرك لا يسبب انهيار"""
        vc = VoiceController()
        vc._tts_engine = None

        # يجب ألا يُطرح أي استثناء
        vc.speak("اختبار النطق")


class TestParseCommandCaseHandling:
    """اختبار معالجة حالة الأحرف في تحليل الأوامر"""

    def test_parse_command_case_insensitive(self):
        """يتحقق من أن التحليل يتعامل مع الأحرف الكبيرة"""
        vc = VoiceController()

        # النص العربي لا يوجد له حالة كبيرة/صغيرة، لكن نختبر النص المختلط
        result = vc.parse_command("صنّف Files")
        assert result["action"] == "classify"

    def test_parse_command_with_extra_spaces(self):
        """يتحقق من أن المسافات الزائدة لا تؤثر"""
        vc = VoiceController()

        result = vc.parse_command("  صنّف  ")
        assert result["action"] == "classify"
