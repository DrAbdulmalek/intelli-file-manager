"""اختبارات content_analyzer — التحليل العميق للمحتوى (نص/صور/صوت) وإصلاح has_tag

مبادئ مُختبرة:
  - الحاجز أولاً: الملف الحساس لا يُفتح محتواه إطلاقاً (سلوك skip_sensitive).
  - استخراج النص: عربي/إنجليزي، PDF (pypdf/fitz)، docx، استنباط نوع المستند.
  - الصور: أبعاد، EXIF كاميرا، كشف لقطة شاشة، ألوان سائدة، رمادي.
  - الصوت: مدة عبر mutagen (بلا ffprobe)، تمييز تسجيل/موسيقى.
  - شروط القواعد: has_tag (eq/exists — إصلاح المفتاح الميت _tag_to_check)
    و extra بمفتاح فرعي.
"""
import contextlib
import sys

import pytest

from src.core.content_analyzer import (
    analyze_file,
    enrich_record,
    extract_text,
)
from src.core.rule_schemas import Condition, Rule


# ─── النصوص والمستندات ─────────────────────────────────────────────────────

def test_arabic_text_lang(tmp_path):
    p = tmp_path / "ملاحظات.txt"
    p.write_text("هذا ملف تجربة باللغة العربية لملاحظات المشروع اليومية", encoding="utf-8")
    extra, tags, result = analyze_file(str(p), "txt", p.stat().st_size)
    assert result == "text"
    assert extra.get("content_lang") == "ar"
    assert "deep:ar" in tags


def test_doc_type_invoice(tmp_path):
    p = tmp_path / "bill.txt"
    p.write_text("فاتورة رقم 12 — المبلغ الإجمالي 500 ريال شامل الضريبة", encoding="utf-8")
    extra, tags, _ = analyze_file(str(p), "txt", p.stat().st_size)
    assert extra.get("doc_type") == "فاتورة"
    assert "doc:فاتورة" in tags


def test_pdf_extraction(tmp_path):
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Invoice total amount 250")
    p = tmp_path / "x.pdf"
    doc.save(str(p))
    doc.close()
    text = extract_text(p, "pdf")
    assert "Invoice" in text


def test_docx_doc_type(tmp_path):
    docx = pytest.importorskip("docx")
    from docx import Document
    d = Document()
    d.add_paragraph("عقد إيجار بين الطرف الأول والطرف الثاني")
    p = tmp_path / "c.docx"
    d.save(str(p))
    extra, tags, _ = analyze_file(str(p), "docx", p.stat().st_size)
    assert extra.get("doc_type") == "عقد"
    assert "doc:عقد" in tags


# ─── الصور ─────────────────────────────────────────────────────────────────

def test_screenshot_detection(tmp_path):
    from PIL import Image
    p = tmp_path / "Screenshot_2026-01-01.png"
    Image.new("RGB", (1920, 1080), (30, 30, 30)).save(p)
    extra, tags, result = analyze_file(str(p), "png", p.stat().st_size)
    assert result == "image"
    assert extra["width"] == 1920 and extra["height"] == 1080
    assert extra["image_kind"] == "screenshot"
    assert "screenshot" in tags
    assert extra["is_grayscale"] is True


def test_camera_photo_exif(tmp_path):
    from PIL import Image
    p = tmp_path / "IMG_0001.jpg"
    img = Image.new("RGB", (400, 300), (120, 40, 200))
    ex = Image.Exif()
    ex[271] = "Canon"   # Make
    ex[272] = "EOS R6"  # Model
    img.save(p, exif=ex.tobytes())
    extra, tags, _ = analyze_file(str(p), "jpg", p.stat().st_size)
    assert extra["image_kind"] == "camera_photo"
    assert extra["exif"]["make"] == "Canon"
    assert "camera-photo" in tags


def test_dominant_colors(tmp_path):
    from PIL import Image
    p = tmp_path / "solid.png"
    Image.new("RGB", (64, 64), (255, 0, 0)).save(p)
    extra, _, _ = analyze_file(str(p), "png", p.stat().st_size)
    assert extra["dominant_colors"] == ["#ff0000"]


# ─── الصوت ─────────────────────────────────────────────────────────────────

def test_audio_wav_duration(tmp_path):
    import wave
    p = tmp_path / "rec.wav"
    with contextlib.closing(wave.open(str(p), "w")) as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 8000)  # ثانية واحدة
    extra, _, result = analyze_file(str(p), "wav", p.stat().st_size)
    assert result == "audio"
    assert extra["duration_seconds"] >= 0.9
    assert extra["audio_kind"] in ("voice_recording", "unknown")


def test_audio_without_mutagen_still_classified_audio(tmp_path, monkeypatch):
    """بلا mutagen (requirements-deep غير مثبتة): صوت بحكم الامتداد، لا unsupported.

    تدهور رشيق موثق: النتيجة audio مع وسم صريح mutagen_missing، بلا ميتاداتا.
    """
    import wave
    p = tmp_path / "rec.wav"
    with contextlib.closing(wave.open(str(p), "w")) as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 8000)  # ثانية واحدة
    monkeypatch.setitem(sys.modules, "mutagen", None)  # import mutagen → ImportError
    extra, _, result = analyze_file(str(p), "wav", p.stat().st_size)
    assert result == "audio"
    assert extra.get("mutagen_missing") is True
    assert extra.get("audio_kind") == "unknown"
    assert "duration_seconds" not in extra


# ─── الحاجز: الملف الحساس لا يُقرأ محتواه إطلاقاً ──────────────────────────

def test_sensitive_file_not_read(tmp_path, monkeypatch):
    """منطق الوحدة: الحاجز أولاً — الملف المصنف حساساً لا يُفتح محتواه إطلاقاً.

    (سلوك الحاجز نفسه مغطى في test_sensitive_barrier*.py — هنا نثبت أن
    content_analyzer يحترم الحاجز قبل أي استخراج.)
    """
    from src.core import content_analyzer
    p = tmp_path / "whatever.txt"
    p.write_text("نص لا يجب أن يُقرأ", encoding="utf-8")
    monkeypatch.setattr(content_analyzer, "is_sensitive_path", lambda path: True)
    called = []

    def fake_extract(path, ext):
        called.append(path)
        return "SHOULD NOT BE READ"

    monkeypatch.setattr(content_analyzer, "extract_text", fake_extract)
    extra, tags, result = content_analyzer.analyze_file(str(p), "txt", p.stat().st_size)
    assert result == "skip_sensitive"
    assert extra == {}
    assert "sensitive-no-deep" in tags
    assert called == []  # الاستخراج لم يُستدعَ أصلاً


# ─── شروط القواعد: has_tag (إصلاح) و extra بمفتاح فرعي ─────────────────────

def test_rule_has_tag_eq():
    rule = Rule(
        name="t", priority=10, enabled=True,
        conditions=[Condition(field="has_tag", op="eq", value="screenshot")],
    )
    assert rule.matches_all_conditions({"tags": ["screenshot", "deep:ar"]}) is True
    assert rule.matches_all_conditions({"tags": ["camera-photo"]}) is False
    assert rule.matches_all_conditions({"tags": []}) is False


def test_rule_has_tag_exists():
    rule = Rule(
        name="t", priority=10, enabled=True,
        conditions=[Condition(field="has_tag", op="exists")],
    )
    assert rule.matches_all_conditions({"tags": ["x"]}) is True
    assert rule.matches_all_conditions({"tags": []}) is False


def test_rule_extra_key_condition():
    rule = Rule(
        name="t", priority=10, enabled=True,
        conditions=[Condition(field="extra", op="eq", value="screenshot", key="image_kind")],
    )
    assert rule.matches_all_conditions({"extra_metadata": {"image_kind": "screenshot"}}) is True
    rule2 = Rule(
        name="t2", priority=10, enabled=True,
        conditions=[Condition(field="extra", op="gt", value=1920, key="width")],
    )
    assert rule2.matches_all_conditions({"extra_metadata": {"width": 2560}}) is True
    assert rule2.matches_all_conditions({"extra_metadata": {"width": 1080}}) is False


# ─── الإثراء على سجل كامل ──────────────────────────────────────────────────

def test_enrich_record(tmp_path):
    from src.db.schemas import FileMetadata, FileRecord
    p = tmp_path / "n.txt"
    p.write_text("شهادة إتمام دورة تدريبية متخصصة", encoding="utf-8")
    md = FileMetadata(
        file_name=p.name, file_path=str(p), file_size=p.stat().st_size,
        extension="txt", category="مستندات",
    )
    rec = FileRecord.from_metadata(metadata=md, document_text="")
    result = enrich_record(rec)
    assert result == "text"
    assert rec.metadata.extra_metadata.get("doc_type") == "شهادة"
    assert "doc:شهادة" in rec.metadata.tags
    # الإثراء مرة ثانية لا يكرر الوسوم
    enrich_record(rec)
    assert rec.metadata.tags.count("doc:شهادة") == 1
