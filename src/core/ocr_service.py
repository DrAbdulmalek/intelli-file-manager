"""خدمة OCR المركزية — مدعومة من مكتبة ocr-core المشتركة.

Single source of truth for OCR in IntelliFile:
  - المحركات من ``ocr_core.engines``: PaddleEngine (الأفضل للعربية عند توفر
    extra ``[paddle]``) ثم TesseractEngine كاحتياطي — بترتيب fallback موحد.
  - إن لم تكن ocr-core مثبتة: تراجع رشيق إلى مسار pytesseract المباشر
    (سلوك ما قبل المركزية) فلا ينكسر أي تثبيت قائم.
  - معالجة لاحقة اختيارية (معطلة افتراضيًا حفاظًا على السلوك): تصحيحات
    ocr-core الطبية العربية + تطبيع — مع إبقاء النص الخام كما هو
    (النص المطبَّع يُعاد في مفتاح منفصل ``normalized_text``).

عقد النتيجة (dict) محفوظ حرفيًا لكل المستهلكين القائمين:
  {extracted_text, ocr_engine, ocr_success, [ocr_confidence], [*_error]}
ملاحظة: ocr_confidence = 0.0 تعني "غير معروفة" وفق سياسة ocr-core
(لا تُخترع درجات ثقة أبدًا).
"""
from __future__ import annotations

import logging
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

_engines_cache: Optional[list] = None


def ocr_core_available() -> bool:
    try:
        import ocr_core  # noqa: F401
        return True
    except ImportError:
        return False


def _build_engines() -> list:
    """محركات ocr-core بترتيب التفضيل: Paddle (عربي) ثم Tesseract."""
    engines: list = []
    try:
        from ocr_core.engines.paddle import PaddleEngine
        engines.append(PaddleEngine(lang="ar"))
    except Exception as exc:  # ImportError أو غياب paddleocr
        logger.debug("PaddleEngine غير متاح: %s", exc)
    try:
        from ocr_core.engines.tesseract import TesseractEngine
        engines.append(TesseractEngine(lang="ara+eng"))
    except Exception as exc:
        logger.debug("TesseractEngine غير متاح: %s", exc)
    return engines


def _get_engines() -> list:
    global _engines_cache
    if _engines_cache is None:
        _engines_cache = _build_engines() if ocr_core_available() else []
    return _engines_cache


def reset_caches() -> None:
    """للاختبارات: تصفير كاش المحركات."""
    global _engines_cache
    _engines_cache = None


def paddle_available() -> bool:
    return any(getattr(e, "name", "") == "paddle" and e.available() for e in _get_engines())


def tesseract_available() -> bool:
    return any(getattr(e, "name", "") == "tesseract" and e.available() for e in _get_engines())


def _legacy_pytesseract(filepath: str) -> dict:
    """مسار ما قبل المركزية — يبقى فقط للتثبيتات بلا ocr-core."""
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(filepath)
        text = pytesseract.image_to_string(img, lang="ara+eng")
        if text.strip():
            return {
                "extracted_text": text.strip(),
                "ocr_engine": "tesseract(legacy)",
                "ocr_success": True,
            }
    except ImportError:
        logger.info("Tesseract OCR غير مثبت")
    except Exception as exc:
        return {"ocr_success": False, "extracted_text": "", "ocr_error": str(exc)}
    return {"ocr_success": False, "extracted_text": ""}


def _postprocess_text(text: str) -> tuple:
    """تصحيحات ocr-core العربية + تطبيع (للمطابقة/الفهرسة، بلا تدمير للعرض)."""
    info: dict = {}
    corrected = text
    try:
        from ocr_core.postprocess.corrections_ar import ArabicMedicalCorrections
        corrected, n = ArabicMedicalCorrections().apply(text)
        info["corrections_applied"] = n
    except Exception as exc:
        logger.debug("تصحيحات ocr-core غير متاحة: %s", exc)
        info["corrections_error"] = str(exc)
    try:
        from ocr_core.postprocess.normalization import arabic_normalize
        info["normalized_text"] = arabic_normalize(corrected)
    except Exception as exc:
        logger.debug("تطبيع ocr-core غير متاح: %s", exc)
        info["normalize_error"] = str(exc)
    return corrected, info


def ocr_image(filepath: str, postprocess: bool = False,
              max_chars: Optional[int] = None) -> dict:
    """OCR لصورة واحدة عبر المحركات المركزية؛ يحفظ عقد المفاتيح القديم."""
    result: dict = {}
    engines = _get_engines()

    if not engines:
        result = _legacy_pytesseract(str(filepath))
    else:
        errors: dict = {}
        for engine in engines:
            ename = getattr(engine, "name", "engine")
            try:
                if not engine.available():
                    continue
                res = engine.process_image(str(filepath))
                if res.error is None and res.text.strip():
                    text = res.text.strip()
                    result = {
                        "extracted_text": text[:max_chars] if max_chars else text,
                        "ocr_engine": res.engine or ename,
                        "ocr_success": True,
                        "ocr_confidence": res.confidence,  # 0.0 = غير معروفة
                    }
                    result.update(errors)  # التشخيصات لا تُفقد عند النجاح
                    break
                if res.error:
                    errors[f"{ename}_error"] = res.error
            except Exception as exc:
                errors[f"{ename}_error"] = str(exc)
        if "extracted_text" not in result:
            result.update(errors)
            result.update({"ocr_success": False, "extracted_text": ""})

    if postprocess and result.get("extracted_text"):
        corrected, info = _postprocess_text(result["extracted_text"])
        result["extracted_text"] = corrected[:max_chars] if max_chars else corrected
        if max_chars and "normalized_text" in info:
            info["normalized_text"] = info["normalized_text"][:max_chars]
        result["ocr_postprocess"] = info
    return result


def _core_enhance(filepath: str) -> Optional[str]:
    """خط تحسين ocr-core الحقيقي (enhance_for_ocr: ndarray→ndarray).

    يقرأ الصورة بـ cv2، يمرر خط التحسين الموثق (denoise/contrast/sharpen +
    تقدير DPI)، ويكتب النتيجة png مؤقتًا. None عند غياب extra [preprocess].
    """
    try:
        import cv2
        from ocr_core.preprocess.enhance import enhance_for_ocr
    except Exception as exc:
        logger.debug("ocr-core preprocess غير متاح: %s", exc)
        return None
    try:
        img = cv2.imread(str(filepath))
        if img is None:
            return None
        out = enhance_for_ocr(img)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            cv2.imwrite(tmp.name, out)
            return tmp.name
    except Exception as exc:
        logger.debug("فشل تحسين ocr-core: %s", exc)
        return None


def enhance_image(filepath: str) -> Optional[str]:
    """تحسين مسبق للصورة قبل OCR.

    يفضل ocr-core preprocess (إن توفر)، وإلا أساسيات PIL (السلوك السابق
    حرفيًا: contrast 1.5 / sharpness 2.0 / median 3). يعيد مسار صورة
    مؤقتة (ينظفه المستدعي) أو None عند الفشل.
    """
    try:
        out = _core_enhance(filepath)
        if out:
            return out
    except Exception as exc:
        logger.debug("ocr-core preprocess غير متاح (%s) — تراجع PIL", exc)
    try:
        from PIL import Image, ImageEnhance, ImageFilter
        img = Image.open(filepath)
        if img.mode != "L":
            img = img.convert("L")
        img = ImageEnhance.Contrast(img).enhance(1.5)
        img = ImageEnhance.Sharpness(img).enhance(2.0)
        img = img.filter(ImageFilter.MedianFilter(size=3))
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img.save(tmp.name)
            return tmp.name
    except Exception as exc:
        logger.debug("خطأ في تحسين الصورة: %s", exc)
        return None
