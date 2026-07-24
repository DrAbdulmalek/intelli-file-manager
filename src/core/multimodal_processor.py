"""معالج متعدد الوسائط - صور وصوت وفيديو

هذه الوحدة توفّر ميزات AI على الوسائط (وصف الصور، نسخ الصوت) فوق
الميتاداتا الأساسية المستخرَجة عبر metadata_extractor الموحّد (PR-03).

تغير PR-03:
  - استخراج الأبعاد/الصيغة/EXIF للصور أصبح يُوكَّل إلى extract_image_metadata
  - استخراج معلومات الفيديو (ffprobe) أصبح يُوكَّل إلى extract_av_metadata
  - استخراج النص من PDF/DOCX/XLSX/PPTX يُوكَّل إلى FileInventory._extract_content
  - AI/OCR/Transcription لا تزال هنا (خارج نطاق PR-03)
"""
import logging
from pathlib import Path

from .metadata_extractor import extract_image_metadata, extract_av_metadata

logger = logging.getLogger(__name__)


class MultimodalProcessor:
    """معالج ملفات متعددة الوسائط"""

    def __init__(self, model: str = None):
        self._model = model  # None = سيستخدم Config.ai_model
        self._ocr_available = False
        self._check_ocr()

    def _check_ocr(self):
        """التحقق من تثبيت OCR"""
        try:
            import pytesseract  # noqa: F401
            self._ocr_available = True
        except ImportError:
            logger.info("Tesseract OCR غير مثبت")

    def process_image(self, filepath: str) -> dict:
        """تحليل صورة ووصف محتواها

        الميتاداتا الأساسية (width/height/format/mode/exif) تُستخرَج عبر
        extract_image_metadata الموحّد (PR-03). وصف AI يُضاف إن توفّر ollama.
        """
        path = Path(filepath)
        result = {"path": str(path), "type": "image"}

        # الميتاداتا الأساسية موكَّلة إلى metadata_extractor
        basic = extract_image_metadata(filepath)
        # دمج المفاتيح غير الخطأ في النتيجة
        for key, value in basic.items():
            if key != "error":
                result[key] = value
        if "error" in basic and not any(k in result for k in ("width", "height")):
            # فقط نُسجّل الخطأ لو لم نحصل على أي ميتاداتا
            result["error"] = basic["error"]

        # OCR
        if self._ocr_available:
            try:
                import pytesseract
                text = pytesseract.image_to_string(filepath, lang="ara+eng")
                result["extracted_text"] = text.strip()
                result["ocr_success"] = True
            except Exception as e:
                result["ocr_success"] = False
                result["ocr_error"] = str(e)

        # وصف AI
        try:
            import ollama
            from ..core.config import Config
            config = Config()
            model_name = self._model or config.ai_model
            client = ollama.Client(host=config.ollama_url)
            # لنسخ الصورة إلى base64
            import base64
            with open(filepath, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            response = client.chat(model_name, messages=[
                {"role": "user", "content": "صِف هذه الصورة باختصار بالعربية: ",
                 "images": [img_b64]}
            ])
            result["ai_description"] = response["message"]["content"]
        except Exception:
            pass

        return result

    def process_audio(self, filepath: str) -> dict:
        """تحليل ملف صوتي واستخراج النص"""
        path = Path(filepath)
        result = {"path": str(path), "type": "audio"}

        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(filepath) as source:
                audio_data = recognizer.record(source, duration=120)
            text = recognizer.recognize_google(audio_data, language="ar-SA")
            result["transcript"] = text
            result["success"] = True
        except ImportError:
            result["error"] = "SpeechRecognition غير مثبت"
        except Exception as e:
            result["error"] = str(e)
            result["success"] = False

        return result

    def process_video(self, filepath: str) -> dict:
        """تحليل فيديو واستخراج معلومات

        الميتاداتا (المدة، الترميز، الأبعاد، معدل البت) تُستخرَج عبر
        extract_av_metadata الموحّد (PR-03) الذي يستخدم ffprobe.
        """
        path = Path(filepath)
        result = {"path": str(path), "type": "video", "name": path.name}

        av_info = extract_av_metadata(filepath)
        # دمج المفاتيح غير الخطأ في النتيجة
        for key, value in av_info.items():
            if key == "error":
                result["probe_error"] = value
            else:
                result[key] = value

        return result

    def extract_text_from_pdf(self, filepath: str) -> str:
        """استخراج نص من PDF — يُوكَّل إلى FileInventory (PR-03 توحيد)"""
        from .file_inventory import _extract_pdf_text
        return _extract_pdf_text(Path(filepath))

    def extract_text_from_docx(self, filepath: str) -> str:
        """استخراج نص من DOCX — يُوكَّل إلى FileInventory (PR-03 توحيد)"""
        from .file_inventory import _extract_docx_text
        return _extract_docx_text(Path(filepath))

    def extract_text_from_xlsx(self, filepath: str) -> str:
        """استخراج نص من XLSX — يُوكَّل إلى FileInventory (PR-03 توحيد)"""
        from .file_inventory import _extract_xlsx_text
        return _extract_xlsx_text(Path(filepath))

    def extract_text_from_pptx(self, filepath: str) -> str:
        """استخراج نص من PPTX — يُوكَّل إلى FileInventory (PR-03 توحيد)"""
        from .file_inventory import _extract_pptx_text
        return _extract_pptx_text(Path(filepath))
