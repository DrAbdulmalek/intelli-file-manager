# src/core/enhanced_multimodal.py
from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict, Any

# الخدمة المركزية الموحدة (بوابة OCR الوحيدة) — محركات ocr-core: Paddle ثم Tesseract
from . import ocr_service

logger = logging.getLogger(__name__)

# راية توافق خلفي (كانت تُصدَّر من هذه الوحدة سابقًا)
OCR_CORE_AVAILABLE = ocr_service.ocr_core_available()


class EnhancedMultimodalProcessor:
    """معالج متعدد الوسائط — طبقة رفيعة فوق الخدمة المركزية (ocr_service).

    تكييف ما بعد PR#47 (النزع إلى 62 سطرًا) مع بوابة ocr_service:
    - المحركات والتراجع الرشيق (Paddle → Tesseract → pytesseract المباشر)
      تُدار مركزيًا في ocr_service — لا تُنشأ محركات هنا.
    - عقد النتيجة محفوظ حرفيًا لكل المستهلكين:
      {path, type, success, extracted_text, confidence, engine_used,
       needs_review, [warning], [error]}
    - ocr_confidence = 0.0 تعني "غير معروفة" وفق سياسة ocr-core، وتُعامَل
      كثقة منخفضة (مراجعة يدوية) — لا تُخترع درجات ثقة أبدًا.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}
        # محفوظ للتوافق الخلفي: المحرك الفعلي يُدار داخل ocr_service
        self.ocr_engine = None

    def process_image(self, filepath: str | Path, fix_scan: bool = True) -> Dict[str, Any]:
        """OCR صورة عبر الخدمة المركزية.

        ملاحظة توافق: المعامل ``fix_scan`` محفوظ للتوافق مع عقد API القديم
        (/api/process/image)؛ التحسين المسبق أصبح داخل المحركات المركزية
        فلا يُنفَّذ منفصلًا هنا.
        """
        path = Path(filepath)
        result: Dict[str, Any] = {"path": str(path), "type": "image", "success": False}

        if not OCR_CORE_AVAILABLE:
            # بلا ocr-core يبقى التراجع الرشيق الداخلي لـ pytesseract فقط؛
            # إن غاب هو أيضًا فلا OCR إطلاقًا — رسالة صريحة كما في السابق.
            try:
                import pytesseract  # noqa: F401
            except ImportError:
                result["error"] = "محرك OCR غير متاح. يرجى تثبيت ocr-core."
                return result

        try:
            res = ocr_service.ocr_image(str(path))

            if not res.get("ocr_success"):
                result["extracted_text"] = res.get("extracted_text", "")
                result["error"] = res.get("ocr_error") or "فشل OCR — لا محرك متاح"
                for key in ("paddle_error", "tesseract_error"):
                    if key in res:
                        result[key] = res[key]
                return result

            confidence = float(res.get("ocr_confidence") or 0.0)
            result["extracted_text"] = res.get("extracted_text", "")
            result["confidence"] = confidence
            result["engine_used"] = res.get("ocr_engine", "unknown")
            result["success"] = True

            # حارس أمان: المراجعة اليدوية إذا كانت الثقة غير مقبولة
            if confidence > 0.75:
                result["needs_review"] = False
            else:
                result["needs_review"] = True
                result["warning"] = "ثقة الاستخراج منخفضة، يُنصح بالمراجعة اليدوية"

        except Exception as e:
            logger.error(f"فشل معالجة الملف {path.name}: {e}")
            result["error"] = str(e)

        return result

    # ------------------------------------------------------------------
    # الصوت/الفيديو/المستندات: كانت endpoints الـAPI تستدعيها على هذا
    # الصنف بينما لم تكن معرّفة هنا (AttributeError → 500). الآن تُوكَّل
    # إلى MultimodalProcessor الذي يطبق الحاجز الحساسي قبل أي قراءة.
    # ------------------------------------------------------------------

    def process_audio(self, filepath: str | Path) -> Dict[str, Any]:
        """تحليل ملف صوتي (نسخ نص) عبر MultimodalProcessor — الحاجز أولاً."""
        from .multimodal_processor import MultimodalProcessor
        return MultimodalProcessor().process_audio(str(filepath))

    def process_video(self, filepath: str | Path) -> Dict[str, Any]:
        """استخراج ميتاداتا فيديو عبر MultimodalProcessor — الحاجز أولاً."""
        from .multimodal_processor import MultimodalProcessor
        return MultimodalProcessor().process_video(str(filepath))

    def process_document(self, filepath: str | Path) -> Dict[str, Any]:
        """استخراج نص مستند (pdf/docx/xlsx/pptx/txt) — الحاجز أولاً.

        يستخدم FileInventory (الاستخراج الموحّد PR-03) بعد فحص الحاجز؛
        الملف الحساس لا يُفتح محتواه إطلاقاً.
        """
        from .file_inventory import FileInventory
        from .sensitive_barrier import block_if_sensitive

        path = Path(filepath)
        result: Dict[str, Any] = {"path": str(path), "type": "document"}

        # حاجز الحساسية قبل أي قراءة محتوى
        block_if_sensitive(str(path), operation="معالجة المستند")

        inventory = FileInventory(include_content=True, max_file_size=10 * 1024 * 1024)
        text = inventory._extract_content(path, path.suffix.lower())
        if text.strip():
            result["extracted_text"] = text
            result["success"] = True
        else:
            result["extracted_text"] = ""
            result["success"] = False
            result["error"] = "لم يُستخرج نص من المستند (نوع غير مدعوم أو محتوى فارغ)"
        return result

        return result
