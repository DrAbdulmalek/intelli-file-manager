# -*- coding: utf-8 -*-
"""تصنيف المحتوى — البوابة الإلزامية: الحاجز الحساس أولاً، ثم Magika، ثم OCR.

هذه الوحدة تعتمد على **محتوى** الملف (بايتات/نص/صور) بدلاً من
الاسم أو الامتداد وحده، مع بقاء حاجز الحساسية (`sensitive_barrier`) بوابة
إلزامية لا يمكن تجاوزها:

    block_if_sensitive(path, operation="تصنيف المحتوى")
        → يرفع SensitiveFileBlockedError لأي ملف طبي/حساس
        → لا يُقرأ بايت واحد من الملف قبل اجتياز البوابة

بعد البوابة فقط:
  1. Magika (تعرّف على نوع المحتوى من البايتات، لا الامتداد).
  2. heuristics دلالية للصور (أبعاد + alpha + تباين) لتمييز
     Screenshot / Diagram / Photo / Medical-Scan-like.
  3. OCR (tesseract) لاستخراج إشارات نصية — اختيارية (opt-in) لأنها
     تقرأ البكسلات، وتُطبَّق فقط بعد اجتياز البوابة.

المبادئ:
  - لا تُفتح الملفات الحساسة إطلاقاً (fail-closed).
  - لا استنتاج من الاسم أو الامتداد عند العمل على المحتوى.
  - OCR اختيارية (ocr=False افتراضياً) — مكلفة وبطيئة على القرص الخارجي.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Union

from .sensitive_barrier import (
    SensitiveFileBlockedError,
    block_if_sensitive,
    classify_sensitivity,
    external_send_allowed,
)

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

# الحد الأقصى لحجم الصورة التي تُفحص دلالياً (20 ميغابايت) — تجنّب ابتلاع الذاكرة
_MAX_IMAGE_BYTES = 20 * 1024 * 1024

_IMAGE_GROUPS = frozenset({"image", "images"})


@dataclass
class ContentResult:
    """نتيجة تصنيف محتوى ملف واحد."""

    path: str
    blocked: bool = False
    block_reason: str = ""
    sensitivity: str = ""
    content_label: str = ""
    content_group: str = ""
    mime_type: str = ""
    magika_score: float = 0.0
    semantic: str = ""
    ocr_text: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _image_semantics(path: Path) -> str:
    """تصنيف دلالي للصورة من خصائصها البنيوية (لا من اسمها).

    يميّز بين لقطة شاشة (أبعاد شاشة، حواف حادة)، رسم بياني (عدد ألوان محدود)،
    صورة فوتوغرافية (تباين لوني غني)، وصورة أحادية اللون (نمط scans).
    تُحسب الخصائص على نسخة مصغّرة فقط لتجنّب ابتلاع الذاكرة.
    """
    try:
        from PIL import Image
    except ImportError:
        return "unknown"

    try:
        size = path.stat().st_size
        if size > _MAX_IMAGE_BYTES:
            return "skipped_too_large"
        with Image.open(path) as img:
            width, height = img.size
            mode = img.mode
            colours = img.convert("RGB").resize((64, 64)).getcolors(maxcolors=64 * 64)
    except (OSError, ValueError):
        return "unknown"

    # لقطة شاشة: أبعاد شاشة شائعة (16:9 أو 16:10) بدقة عالية
    if width >= 1280 and height >= 720 and abs(width / height - 16 / 9) < 0.05:
        return "screenshot"

    # صورة أحادية اللون (أبيض/أسود أو رمادي) — نمط المستندات الممسوحة
    if mode in ("1", "L", "LA", "P"):
        return "document_scan_like"

    # عدد محدود جداً من الألوان على صورة صغيرة → رسم/مخطط/رسم بياني
    if colours is not None and len(colours) <= 16:
        return "diagram_or_chart"

    return "photo"


def _ocr_text(path: Path, *, languages: str = "ara+eng") -> str:
    """يستخرج نصاً من الصورة عبر tesseract (يُستدعى بعد اجتياز البوابة فقط)."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""
    try:
        with Image.open(path) as img:
            return pytesseract.image_to_string(img, lang=languages) or ""
    except (OSError, ValueError):
        return ""


def classify_content(
    file_path: PathLike,
    *,
    magika,
    ocr: bool = False,
    ocr_languages: str = "ara+eng",
) -> ContentResult:
    """يصنّف محتوى الملف. **البوابة أولاً** — لا بايت يُقرأ قبل اجتيازها.

    Args:
        file_path: مسار الملف.
        magika: كائن Magika مُهيّأ (يُمرَّر لتجنّب إعادة التهيئة لكل ملف).
        ocr: تفعيل OCR للصور (افتراضياً False — مكلف).
        ocr_languages: لغات tesseract.

    Returns:
        ContentResult. عند الرفض: blocked=True ولا تُقرأ أي بيانات.
    """
    path = Path(file_path)
    result = ContentResult(path=str(path))

    # ── البوابة الإلزامية (fail-closed) ──────────────────────────────────
    sens = classify_sensitivity(path)
    if sens["is_sensitive"]:
        result.blocked = True
        result.block_reason = sens["reason"]
        result.sensitivity = "sensitive"
        logger.info(f"محظور (حاجز الحساسية) — لم يُقرأ أي بايت: {path}")
        return result
    result.sensitivity = "non_sensitive"

    if not path.is_file():
        result.error = "ليس ملفاً عادياً"
        return result

    # ── Magika: نوع المحتوى من البايتات ─────────────────────────────────
    try:
        identified = magika.identify_path(str(path))
        output = identified.output
        result.content_label = getattr(output, "label", "") or ""
        result.content_group = getattr(output, "group", "") or ""
        result.mime_type = getattr(output, "mime_type", "") or ""
        result.magika_score = float(getattr(identified, "score", 0.0) or 0.0)
    except Exception as exc:  # Magika قد تفشل على ملفات تالفة
        result.error = f"magika:{type(exc).__name__}"

    # ── دلالة الصور + OCR (اختياري) ─────────────────────────────────────
    if result.content_group in _IMAGE_GROUPS:
        result.semantic = _image_semantics(path)
        if ocr:
            result.ocr_text = _ocr_text(path, languages=ocr_languages)[:2000]

    return result


def classify_content_batch(
    paths,
    *,
    magika,
    ocr: bool = False,
    progress: bool = False,
) -> list:
    """يصنّف batch من الملفات ويرجع قائمة ContentResult."""
    out: list = []
    for index, raw in enumerate(paths, start=1):
        out.append(classify_content(raw, magika=magika, ocr=ocr))
        if progress and index % 200 == 0:
            logger.info(f"تم تصنيف {index} ملفاً")
    return out


def summarize(results: list) -> dict:
    """يلخّص نتائج التصنيف: توزيع المجموعات/الأنواع وحالات الحجب."""
    summary = {
        "total": len(results),
        "blocked": 0,
        "errors": 0,
        "by_group": {},
        "by_label": {},
        "by_semantic": {},
    }
    for item in results:
        if item.blocked:
            summary["blocked"] += 1
            continue
        if item.error:
            summary["errors"] += 1
        for key, field_name in (
            ("by_group", "content_group"),
            ("by_label", "content_label"),
            ("by_semantic", "semantic"),
        ):
            value = getattr(item, field_name, "")
            if value:
                summary[key][value] = summary[key].get(value, 0) + 1
    return summary
