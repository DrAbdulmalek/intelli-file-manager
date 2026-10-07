"""اختبارات تجميع السطور."""
import pytest
from src.services.line_aggregator import (
    LineAggregator, aggregate_to_text, aggregate_to_structured,
    detect_direction, clean_text,
)


def make_snippet(x1, y1, x2, y2, text, conf=0.9):
    return {
        "bbox": [x1, y1, x2, y2],
        "text": text,
        "confidence": conf,
    }


# ---------- detect_direction ----------
def test_direction_arabic():
    assert detect_direction("السلام عليكم") == "rtl"


def test_direction_english():
    assert detect_direction("Hello world") == "ltr"


def test_direction_mixed_arabic_dominant():
    assert detect_direction("السلام Hello") == "rtl"


def test_direction_numbers_only():
    assert detect_direction("12345") == "neutral"


# ---------- clean_text ----------
def test_clean_text_removes_bidi():
    # يحتوي LRM (U+200E)
    assert clean_text("السلام\u200eعليكم") == "السلامعليكم"


def test_clean_text_normalizes_whitespace():
    assert clean_text("السلام   عليكم\n\nمرحبا") == "السلام عليكم مرحبا"


# ---------- aggregate ----------
def test_single_line_rtl():
    snippets = [
        make_snippet(300, 50, 380, 90, "عليكم"),
        make_snippet(200, 50, 280, 90, "السلام"),
        make_snippet(50, 50, 180, 90, "مرحبا"),
    ]
    result = aggregate_to_text(snippets, reading_direction="rtl")
    # RTL: الأول = الأيمن (عليكم) ← ... ← الأيسر (مرحبا)
    assert result == "عليكم السلام مرحبا"


def test_single_line_ltr():
    snippets = [
        make_snippet(50, 50, 100, 90, "Hello"),
        make_snippet(200, 50, 280, 90, "world"),
        make_snippet(300, 50, 380, 90, "again"),
    ]
    result = aggregate_to_text(snippets, reading_direction="ltr")
    assert result == "Hello world again"


def test_two_lines_rtl():
    # تصحيح تدقيق: الإحداثيات في النسخة الأصلية كانت معكوسة بالنسبة للنص
    # المتوقع — في RTL كلمة "السلام" (أول القراءة) يجب أن تكون يمين
    # "عليكم" (x أكبر)، وإلا فالناتج الصحيح هندسيًا هو "عليكم السلام".
    snippets = [
        # سطر 1 (y=50): السلام يمينًا (أول قراءة RTL) ثم عليكم يسارًا
        make_snippet(300, 50, 380, 90, "السلام"),
        make_snippet(200, 50, 280, 90, "عليكم"),
        # سطر 2 (y=200): مرحبا يمينًا ثم بكم يسارًا
        make_snippet(250, 200, 320, 240, "مرحبا"),
        make_snippet(100, 200, 200, 240, "بكم"),
    ]
    result = aggregate_to_text(snippets, reading_direction="rtl")
    assert result == "السلام عليكم\nمرحبا بكم"


def test_structured_output():
    snippets = [
        make_snippet(200, 50, 280, 90, "السلام"),
        make_snippet(50, 50, 180, 90, "عليكم"),
    ]
    result = aggregate_to_structured(snippets, reading_direction="rtl")
    assert result["text"] == "السلام عليكم"
    assert result["line_count"] == 1
    assert result["word_count"] == 2
    assert len(result["lines"]) == 1
    assert len(result["lines"][0]["words"]) == 2
    # أول كلمة = الأيمن
    assert result["lines"][0]["words"][0]["text"] == "السلام"


def test_empty_input():
    assert aggregate_to_text([], "rtl") == ""


def test_unlabeled_skipped():
    snippets = [
        make_snippet(200, 50, 280, 90, "السلام"),
        make_snippet(50, 50, 180, 90, ""),  # فارغ — يُستبعد
    ]
    result = aggregate_to_text(snippets, reading_direction="rtl")
    assert result == "السلام"


def test_line_tolerance():
    """كلمتان على ارتفاع مختلف قليلًا → نفس السطر."""
    snippets = [
        make_snippet(200, 50, 280, 90, "السلام"),
        make_snippet(50, 55, 180, 95, "عليكم"),  # +5 بكسل
    ]
    agg = LineAggregator(line_tolerance=15)
    lines = agg.aggregate(snippets, reading_direction="rtl")
    assert len(lines) == 1


def test_line_tolerance_exceeded():
    """الفرق كبير → سطران مختلفان."""
    snippets = [
        make_snippet(200, 50, 280, 90, "السلام"),
        make_snippet(50, 150, 180, 190, "عليكم"),  # +100 بكسل
    ]
    agg = LineAggregator(line_tolerance=15)
    lines = agg.aggregate(snippets, reading_direction="rtl")
    assert len(lines) == 2
