"""تجميع الكلمات في سطور — RTL-aware.

المشكلة الحرجة:
  عند تصدير كلمات عربية مرتبة، الترتيب "الأبجدي حسب x_min" يعطي
  نصًا مقلوبًا. العربية تُقرأ من اليمين لليسار، لذا نرتب بحسب
  x_max (الحافة اليمنى) تنازليًا.

الحل:
  - رتّب الكلمات داخل كل سطر بحسب x2 (الحافة اليمنى) تنازليًا
  - ادمج النصوص بمسافة واحدة
  - احفظ إحداثيات الكلمات الفردية للتدريب على مستوى الكلمة
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Optional


# ---------- نموذج السطر ----------
@dataclass
class WordAnnotation:
    """كلمة واحدة مع موقعها ونصها — للتدريب على مستوى الكلمة."""
    bbox: list[int]              # [x1, y1, x2, y2]
    text: str
    confidence: float
    word_index: int              # داخل السطر (0 = أول كلمة في القراءة)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LineAnnotation:
    """سطر كامل — النص المُجمَّع + الكلمات المُفردة."""
    line_index: int
    bbox: list[int]              # حدود السطر الكامل
    text: str                    # النص المُدمج (الترتيب الصحيح)
    words: list[WordAnnotation] = field(default_factory=list)
    avg_confidence: float = 0.0
    direction: str = "rtl"       # rtl أو ltr أو mixed

    @property
    def word_count(self) -> int:
        return len(self.words)

    def to_dict(self) -> dict:
        return {
            "line_index": self.line_index,
            "bbox": self.bbox,
            "text": self.text,
            "words": [w.to_dict() for w in self.words],
            "avg_confidence": round(self.avg_confidence, 3),
            "direction": self.direction,
        }


# ---------- أدوات bidi ----------
_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_DIGIT_RE = re.compile(r"[0-9\u0660-\u0669]")

# محارف التحكم في الاتجاه — تُحذف عند الحفظ
_BIDI_MARKS = re.compile(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]")


def detect_direction(text: str) -> str:
    """يحدد اتجاه النص الأساسي."""
    ar = len(_ARABIC_RE.findall(text))
    la = len(_LATIN_RE.findall(text))
    if ar == 0 and la == 0:
        return "neutral"
    if ar > 0 and la > 0:
        # العربية تغلب إذا كانت الأكثرية
        return "rtl" if ar >= la else "ltr"
    return "rtl" if ar > 0 else "ltr"


def clean_text(text: str) -> str:
    """تنظيف بسيط — لا يُغيّر الإملاء، فقط whitespace و bidi marks."""
    # احذف bidi marks (تُضاف بصريًا ولا قيمة لها في البيانات المنطقية)
    text = _BIDI_MARKS.sub("", text)
    # وحّد المسافات
    text = re.sub(r"\s+", " ", text)
    # NFKC — توحيد Unicode (يفيد في الأرقام والأشكال المتوافقة)
    text = unicodedata.normalize("NFKC", text)
    return text.strip()


# ---------- المُجمِّع الرئيسي ----------
class LineAggregator:
    """يجمع كلمات من snippets إلى سطور مرتّبة."""

    def __init__(
        self,
        line_tolerance: int = 15,      # ± بكسل لاعتبار الكلمتين في نفس السطر
        min_line_words: int = 1,       # الحد الأدنى لكلمات السطر
        preserve_word_boxes: bool = True,
    ):
        self.line_tolerance = line_tolerance
        self.min_line_words = min_line_words
        self.preserve_word_boxes = preserve_word_boxes

    def aggregate(
        self,
        snippets: list[dict],
        reading_direction: str = "rtl",
    ) -> list[LineAnnotation]:
        """
        Args:
            snippets: قائمة dicts فيها: bbox، text، confidence، source، إلخ.
            reading_direction: "rtl" (عربي) أو "ltr" (إنجليزي).

        Returns:
            قائمة LineAnnotation، مرتّبة من أعلى الصفحة إلى أسفلها.
        """
        if not snippets:
            return []

        # 1. استبعد ما لا نص له
        labeled = [s for s in snippets if (s.get("text") or "").strip()]
        if not labeled:
            return []

        # 2. جمّع في مجموعات أفقية (سطور)
        lines_groups = self._group_by_y(labeled)

        # 3. رتّب الكلمات داخل كل سطر حسب الاتجاه
        annotations: list[LineAnnotation] = []
        for line_idx, group in enumerate(lines_groups):
            # RTL: رتّب بحسب x2 تنازليًا
            if reading_direction == "rtl":
                group.sort(key=lambda s: (-s["bbox"][2], s["bbox"][1]))
            else:
                group.sort(key=lambda s: (s["bbox"][0], s["bbox"][1]))

            # ابنِ الكلمات
            words: list[WordAnnotation] = []
            for w_idx, s in enumerate(group):
                text = clean_text(s.get("text", ""))
                if not text:
                    continue
                words.append(WordAnnotation(
                    bbox=list(s["bbox"]),
                    text=text,
                    confidence=float(s.get("confidence", 1.0)),
                    word_index=w_idx,
                ))

            if len(words) < self.min_line_words:
                continue

            # ادمج النصوص
            line_text = " ".join(w.text for w in words)

            # حدود السطر الكامل
            all_x1 = [w.bbox[0] for w in words]
            all_y1 = [w.bbox[1] for w in words]
            all_x2 = [w.bbox[2] for w in words]
            all_y2 = [w.bbox[3] for w in words]
            line_bbox = [
                min(all_x1), min(all_y1),
                max(all_x2), max(all_y2),
            ]

            avg_conf = sum(w.confidence for w in words) / len(words)

            annotations.append(LineAnnotation(
                line_index=line_idx,
                bbox=line_bbox,
                text=line_text,
                words=words if self.preserve_word_boxes else [],
                avg_confidence=avg_conf,
                direction=detect_direction(line_text),
            ))

        # 4. أعد ترتيب السطور من الأعلى للأسفل
        annotations.sort(key=lambda a: a.bbox[1])
        # أعد ترقيم
        for i, a in enumerate(annotations):
            a.line_index = i

        return annotations

    def _group_by_y(self, snippets: list[dict]) -> list[list[dict]]:
        """يجمع الكلمات في مجموعات أفقية بحسب تقارب y."""
        sorted_snips = sorted(snippets, key=lambda s: (s["bbox"][1], s["bbox"][0]))

        groups: list[list[dict]] = []
        for s in sorted_snips:
            y_center = (s["bbox"][1] + s["bbox"][3]) / 2
            placed = False

            for group in groups:
                # احسب مركز y للمجموعة الحالية
                group_y = sum((g["bbox"][1] + g["bbox"][3]) / 2 for g in group) / len(group)
                if abs(y_center - group_y) <= self.line_tolerance:
                    group.append(s)
                    placed = True
                    break

            if not placed:
                groups.append([s])

        return groups


# ---------- واجهة مساعدة ----------
def aggregate_to_text(
    snippets: list[dict],
    reading_direction: str = "rtl",
) -> str:
    """اختصار: snippets → نص كامل (سطر لكل مجموعة)."""
    agg = LineAggregator()
    lines = agg.aggregate(snippets, reading_direction)
    return "\n".join(line.text for line in lines)


def aggregate_to_structured(
    snippets: list[dict],
    reading_direction: str = "rtl",
) -> dict:
    """snippets → dict كامل مع السطور والكلمات (للتصدير)."""
    agg = LineAggregator()
    lines = agg.aggregate(snippets, reading_direction)

    return {
        "text": "\n".join(line.text for line in lines),
        "lines": [line.to_dict() for line in lines],
        "line_count": len(lines),
        "word_count": sum(line.word_count for line in lines),
        "avg_confidence": (
            sum(line.avg_confidence for line in lines) / len(lines)
            if lines else 0.0
        ),
    }
