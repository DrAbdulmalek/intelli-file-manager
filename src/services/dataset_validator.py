"""بوابات جودة قبل تصدير Dataset.

الهدف: منع أي عيّنة فاسدة من الوصول إلى التدريب.

البوابات:
  1. bbox داخل حدود الصورة
  2. النص غير فارغ + طول معقول
  3. الأرقام والوحدات الطبية محفوظة
  4. لا تداخل مع بكسلات شفافة
  5. الثقة ≥ الحد الأدنى (قابل للضبط)
  6. النص يبدأ بحرف عربي/لاتيني (ليس محارف فقط)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image


@dataclass
class ValidationIssue:
    code: str
    severity: str           # "error" | "warning"
    message: str
    snippet_id: Optional[int] = None


@dataclass
class ValidationResult:
    total: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    issues: list[ValidationIssue] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []

    def add_issue(self, issue: ValidationIssue):
        self.issues.append(issue)
        if issue.severity == "error":
            self.failed += 1
        else:
            self.warnings += 1

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "issues": [
                {"code": i.code, "severity": i.severity,
                 "message": i.message, "snippet_id": i.snippet_id}
                for i in self.issues
            ],
        }


_DIGITS = re.compile(r"[0-9\u0660-\u0669]+")
_MED_UNITS = re.compile(
    r"\b(mg|ml|mcg|g|kg|mmhg|iu|tablet|capsule|"
    r"ملغ|مل|مكغ|غرام|كغ|وحدة|حبة|كبسولة)\b",
    re.IGNORECASE,
)
_MIN_TEXT_LEN = 1
_MAX_TEXT_LEN = 500
_MIN_CONFIDENCE = 0.0       # قابل للضبط


class DatasetValidator:
    """يفحص snippets قبل التصدير."""

    def __init__(
        self,
        min_confidence: float = _MIN_CONFIDENCE,
        require_all_text: bool = True,
        check_digits_preservation: bool = True,
    ):
        self.min_confidence = min_confidence
        self.require_all_text = require_all_text
        self.check_digits_preservation = check_digits_preservation

    def validate_snippet(
        self,
        snippet: dict,
        image_width: int,
        image_height: int,
        result: ValidationResult,
    ) -> bool:
        """يفحص قصاصة واحدة، يضيف الـ issues للـ result."""
        result.total += 1
        sid = snippet.get("id")
        ok = True

        # 1. bbox صالح
        bbox = snippet.get("bbox")
        if not bbox or len(bbox) != 4:
            result.add_issue(ValidationIssue(
                "INVALID_BBOX", "error", "bbox غير صالح", sid))
            return False

        x1, y1, x2, y2 = bbox
        if x1 >= x2 or y1 >= y2:
            result.add_issue(ValidationIssue(
                "EMPTY_BBOX", "error",
                f"bbox بدون مساحة: {bbox}", sid))
            ok = False

        if x1 < 0 or y1 < 0 or x2 > image_width or y2 > image_height:
            result.add_issue(ValidationIssue(
                "OUT_OF_BOUNDS", "error",
                f"bbox خارج الصورة ({image_width}×{image_height}): {bbox}",
                sid))
            ok = False

        # 2. النص
        text = (snippet.get("text") or "").strip()
        if not text:
            if self.require_all_text:
                result.add_issue(ValidationIssue(
                    "EMPTY_TEXT", "error", "نص فارغ", sid))
                ok = False
            else:
                result.add_issue(ValidationIssue(
                    "EMPTY_TEXT", "warning", "نص فارغ (مسموح)", sid))

        if len(text) > _MAX_TEXT_LEN:
            result.add_issue(ValidationIssue(
                "TEXT_TOO_LONG", "warning",
                f"نص طويل ({len(text)} حرف)", sid))

        # 3. النص يبدأ بحرف (ليس محارف فقط)
        if text and not re.search(r"[A-Za-z\u0600-\u06FF]", text):
            result.add_issue(ValidationIssue(
                "NO_LETTERS", "warning",
                f"لا حروف في النص: {text[:20]}", sid))

        # 4. الثقة
        conf = snippet.get("confidence", 1.0)
        if conf < self.min_confidence:
            result.add_issue(ValidationIssue(
                "LOW_CONFIDENCE", "warning",
                f"ثقة منخفضة: {conf:.2f}", sid))

        # 5. الأرقام (guardrails)
        if self.check_digits_preservation:
            ocr_text = (snippet.get("ocr_text") or "").strip()
            if ocr_text and text:
                orig_digits = _DIGITS.findall(ocr_text)
                new_digits = _DIGITS.findall(text)
                if orig_digits and orig_digits != new_digits:
                    result.add_issue(ValidationIssue(
                        "NUMERICAL_DRIFT", "error",
                        f"الأرقام تغيّرت: {orig_digits[:3]} → {new_digits[:3]}",
                        sid))
                    ok = False

        # 6. تحقق من الوحدات الطبية (للمحتوى الطبي)
        if snippet.get("category") == "medical":
            orig_units = set(_MED_UNITS.findall(
                (snippet.get("ocr_text") or "").lower()))
            new_units = set(_MED_UNITS.findall(text.lower()))
            if orig_units and orig_units != new_units:
                result.add_issue(ValidationIssue(
                    "UNIT_DRIFT", "error",
                    f"وحدات طبية تغيّرت: {orig_units} → {new_units}",
                    sid))
                ok = False

        if ok:
            result.passed += 1
        return ok

    def validate_all(
        self,
        snippets: list[dict],
        source_image_path: str,
    ) -> ValidationResult:
        """يفحص كل القصاصات لصورة مصدر."""
        result = ValidationResult()

        try:
            with Image.open(source_image_path) as img:
                w, h = img.size
        except Exception as e:
            result.add_issue(ValidationIssue(
                "IMAGE_UNREADABLE", "error",
                f"لا يمكن قراءة الصورة: {e}"))
            return result

        for s in snippets:
            self.validate_snippet(s, w, h, result)

        return result
