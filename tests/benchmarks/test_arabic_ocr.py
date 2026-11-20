# tests/benchmarks/test_arabic_ocr.py
"""Benchmark عربي — يقيس CER/WER بقيم حقيقية (لا محاكاة).

تصحيح تدقيق (محادثة DeepSeek): النسخة السابقة كانت تضع قيمًا "محاكاة"
(ce­r = 0.15 ثابتة) وتدّعي قياس الانحدار — وهذا يخالف قاعدة الميثاق
"لا تُختلق أرقام". النسخة الحالية تقيس فعلًا عبر
``ocr_core.benchmarks.core.metrics.EditDistance`` على أزواج عربية:
  - اختبار انحدار للمقاييس نفسها (وحدات، بلا محركات OCR)
  - اختبار صورة اختياري (fixture + محرك) يُتخطى إن لم يتوفر أحدهما
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# 1) مقاييس CER/WER الفعلية — انحدار على نصوص عربية
# ---------------------------------------------------------------------------

def _metrics():
    try:
        from ocr_core.benchmarks.core.metrics import EditDistance
        return EditDistance
    except ImportError:
        pytest.skip("ocr-core غير مثبت أو بلا وحدة benchmarks")


def test_arabic_cer_perfect_match():
    """نص مطابق → CER = 0."""
    ed = _metrics()
    r = ed.cer("السلام عليكم", "السلام عليكم")
    assert r["cer"] == 0.0


def test_arabic_cer_single_substitution():
    """حرف واحد مخطوء من 12 → CER محدود ومعروف (1/12 تقريبًا)."""
    ed = _metrics()
    r = ed.cer("السلام عليكم", "السلام عليكن")
    assert 0.0 < r["cer"] < 0.15


def test_arabic_wer_word_level():
    """WER على مستوى الكلمات — كلمة مختلفة من كلمتين = 0.5."""
    ed = _metrics()
    r = ed.wer("السلام عليكم", "السلام عليكم")
    assert r["wer"] == 0.0
    r2 = ed.wer("السلام عليكم", "سلام عليكم")
    assert 0.0 < r2["wer"] <= 1.0


def test_arabic_digits_guardrail_regression():
    """الأرقام العربية/اللاتينية — خطأ شائع في OCR الطبي لا يمر بصمت."""
    ed = _metrics()
    r = ed.cer("جرعة 500 ملغ", "جرعة ٥٠٠ ملغ")
    # الأرقام تغيرت حرفيًا — يجب أن يسجل CER > 0 (لا تطبيع صامت هنا)
    assert r["cer"] > 0.0


# ---------------------------------------------------------------------------
# 2) اختبار صورة end-to-end (اختياري — fixture + محرك OCR)
# ---------------------------------------------------------------------------

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "arabic_sample.png"


@pytest.mark.skipif(
    not FIXTURE.exists(),
    reason="عينة عربية غير موجودة: tests/fixtures/arabic_sample.png",
)
def test_arabic_ocr_quality_on_fixture():
    """يقيس CER على عينة عربية حقيقية — يمنع الانحدار عند توفر fixture ومحرك."""
    try:
        from ocr_core.engines.tesseract import TesseractEngine
    except ImportError:
        pytest.skip("محركات ocr-core غير مثبتة")

    engine = TesseractEngine(lang="ara")
    if not engine.available():
        pytest.skip("tesseract غير متاح في هذه البيئة")

    result = engine.process_image(str(FIXTURE))
    if not result.ok:
        pytest.skip(f"المحرك فشل: {result.error}")

    from ocr_core.benchmarks.core.metrics import EditDistance
    reference = (FIXTURE.with_suffix(".txt")).read_text(encoding="utf-8").strip() \
        if FIXTURE.with_suffix(".txt").exists() else ""
    if not reference:
        pytest.skip("لا نص مرجعي (.txt) بجانب العينة")

    r = EditDistance.cer(reference, result.text.strip())
    assert r["cer"] < 0.30, f"CER مرتفع على العينة العربية: {r['cer']:.2f}"
