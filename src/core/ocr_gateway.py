"""بوابة OCR المركزية — نقطة الاستيراد التعاقدية الوحيدة للمستهلكين (F004).

عقد AGENTS.md: استهلاك OCR حصراً عبر بوابة مركزية واحدة؛ محركات OCR
(pytesseract / ocr_core.engines / paddleocr / easyocr / rapidocr / surya)
لا تُستورد مباشرة في أي ملف آخر داخل src/ — بوابة verify.sh الآلية
(``gate:ocr-imports-gateway``) تفرض ذلك، والاستيراد المسموح فقط داخل
التنفيذ ``src/core/ocr_service.py``.

الاستهلاك:
    from . import ocr_gateway
    ocr_gateway.ocr_image(path)   # ← عبر البوابة، لا من ocr_service مباشرة

هذه الوحدة وكيل ديناميكي (PEP 562 ``module __getattr__``) يعيد كل الواجهة
العامة من ocr_service عند كل وصول — أي رقعة (monkeypatch) على ocr_service
تصل عبر البوابة أيضًا، فلا تنكسر اختبارات الحاجز والتراجع الرشيق.
"""
from __future__ import annotations

from . import ocr_service

__all__ = [
    "any_engine_available",
    "enhance_image",
    "ocr_core_available",
    "ocr_image",
    "paddle_available",
    "pytesseract_available",
    "reset_caches",
    "tesseract_available",
]


def __getattr__(name: str):
    """وكيل ديناميكي إلى ocr_service — حل السمة عند كل وصول (PEP 562)."""
    if name in __all__:
        return getattr(ocr_service, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
