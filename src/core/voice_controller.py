"""وحدة التحكم الصوتي - أوامر صوتية بالعربية"""
import logging
import threading
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class VoiceController:
    """التحكم الصوتي بالتطبيق"""

    def __init__(self, command_callback: Optional[Callable] = None,
                 language: str = "ar-SA"):
        self.command_callback = command_callback
        self.language = language
        self._recognizer = None
        self._tts_engine = None
        self._init_recognizer()
        self._init_tts()

    def _init_recognizer(self):
        """تهيئة محرك التعرف على الكلام"""
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold = 300
            self._recognizer.dynamic_energy_threshold = 400
            logger.info("تم تهيئة محرك التعرف على الكلام")
        except ImportError:
            logger.warning("SpeechRecognition غير مثبت")

    def _init_tts(self):
        """تهيئة محرك تحويل النص إلى كلام"""
        try:
            import pyttsx3
            self._tts_engine = pyttsx3.init()
            # تعيين سرعة التحدث
            self._tts_engine.setProperty('rate', 150)
            voices = self._tts_engine.getProperty('voices')
            # محاولة اختيار صوت عربي
            for voice in voices:
                if 'arabic' in voice.name.lower() or 'ar' in voice.id.lower():
                    self._tts_engine.setProperty('voice', voice.id)
                    break
            logger.info("تم تهيئة محرك تحويل النص إلى كلام")
        except ImportError:
            logger.warning("pyttsx3 غير مثبت")

    def listen(self, timeout: int = 10) -> str:
        """الاستماع للأوامر الصوتية"""
        if not self._recognizer:
            return "خطأ: محرك التعرف غير متاح"

        try:
            import speech_recognition as sr
            with sr.Microphone() as source:
                logger.info("جاري الاستماع...")
                audio = self._recognizer.listen(source, timeout=timeout,
                                                     phrase_time_limit=30)
            text = self._recognizer.recognize_google(audio, language=self.language)
            logger.info(f"تم التعرف: {text}")
            return text
        except Exception as e:
            logger.error(f"خطأ في الاستماع: {e}")
            return ""

    def speak(self, text: str):
        """نطق النص"""
        if not self._tts_engine:
            logger.warning("محرك النطق غير متاح")
            return

        def _speak():
            try:
                self._tts_engine.say(text)
                self._tts_engine.runAndWait()
            except Exception as e:
                logger.error(f"خطأ في النطق: {e}")

        thread = threading.Thread(target=_speak, daemon=True)
        thread.start()

    def parse_command(self, text: str) -> dict:
        """تحليل الأمر الصوتي"""
        text = text.strip().lower()

        commands_map = {
            "صنف": {"action": "classify", "target": "all"},
            "صنّف": {"action": "classify", "target": "all"},
            "افتح": {"action": "open", "target": "folder"},
            "ابحث": {"action": "search", "target": "query"},
            "احذف": {"action": "delete", "target": "selected"},
            "انقل": {"action": "move", "target": "selected"},
            "ملخص": {"action": "summarize", "target": "selected"},
            "لخّص": {"action": "summarize", "target": "selected"},
            "توقف": {"action": "stop"},
            "إلغاء": {"action": "undo"},
            "رجع": {"action": "undo"},
        }

        for keyword, command in commands_map.items():
            if keyword in text:
                # استخراج المعاملات
                params = text.replace(keyword, "").strip()
                command["params"] = params if params else None
                return command

        # أمر عام - تمريره للمساعد الذكي
        return {"action": "chat", "params": text}

    def start_listening_loop(self):
        """بدء حلقة الاستماع المستمرة"""
        logger.info("تم بدء حلقة الاستماع الصوتي")
        while True:
            try:
                text = self.listen()
                if text:
                    command = self.parse_command(text)
                    self.speak(f"تم تنفيذ: {command['action']}")
                    if self.command_callback:
                        self.command_callback(command)
            except KeyboardInterrupt:
                logger.info("تم إيقاف الاستماع")
                break
