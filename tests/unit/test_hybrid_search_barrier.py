# -*- coding: utf-8 -*-
"""حاجز الحساسية في الفهرسة الهجينة (hybrid_search) — إغلاق جولة DeepSeek 12.

الثغرة: `_extract_text` كانت تقرأ المحتوى مباشرة (read_text + pdfplumber)
بلا `is_sensitive_path` — بينما rag_engine:278 وsemantic_search:64 محجوبتان.
العقد: ملفات المرضى لا تُقرأ ولا تُفهرس إطلاقاً (PR #63).
"""
from pathlib import Path

from src.core.hybrid_search import HybridSearchEngine


def _engine_no_model() -> HybridSearchEngine:
    """مثيل بلا تحميل النموذج — الاختبار يستهدف _extract_text فقط."""
    return HybridSearchEngine.__new__(HybridSearchEngine)


def test_sensitive_medical_file_never_extracted(tmp_path):
    engine = _engine_no_model()
    dcm = tmp_path / "patients" / "scan.dcm"
    dcm.parent.mkdir()
    dcm.write_bytes(b"\x00" * 200)

    assert engine._extract_text(str(dcm)) == ""
    assert dcm.read_bytes() == b"\x00" * 200  # الملف نفسه لم يُمَس


def test_plain_file_still_extracted(tmp_path):
    engine = _engine_no_model()
    plain = tmp_path / "notes" / "todo.txt"
    plain.parent.mkdir()
    plain.write_text("محتوى عادي قابل للفهرسة", encoding="utf-8")

    assert "قابل للفهرسة" in engine._extract_text(str(plain))


def test_sensitive_report_by_extension_blocked(tmp_path):
    """امتداد تقرير طبي (بدون مؤشر مسار) محجوب أيضاً."""
    engine = _engine_no_model()
    report = tmp_path / "lab_report.pdf"
    report.write_bytes(b"%PDF-1.4 fake")

    assert engine._extract_text(str(report)) == ""


def test_indexing_loop_skips_sensitive_files(tmp_path):
    """حلقة الفهرسة الكاملة: الحساس لا يدخل الفهرس، العادي يدخل."""
    engine = _engine_no_model()
    (tmp_path / "patients").mkdir()
    (tmp_path / "patients" / "x.txt").write_text("بيانات مريض", encoding="utf-8")
    (tmp_path / "public.txt").write_text("محتوى عام", encoding="utf-8")

    blocked = engine._extract_text(str(tmp_path / "patients" / "x.txt"))
    allowed = engine._extract_text(str(tmp_path / "public.txt"))

    assert blocked == "" and "محتوى عام" in allowed
