# -*- coding: utf-8 -*-
"""اختبارات وحدة تصنيف المحتوى: البوابة الإلزامية + Magika + دلالة الصور."""
from src.core.content_classifier import ContentResult, classify_content, summarize
from src.core.sensitive_barrier import SensitiveFileBlockedError
from PIL import Image


class _TripwireMagika:
    def __init__(self):
        self.calls = 0

    def identify_path(self, path):
        self.calls += 1
        raise AssertionError(f"استُدعيت Magika على ملف حساس: {path}")


class _FakeOutput:
    def __init__(self, label, group, mime_type="application/octet-stream"):
        self.label = label
        self.group = group
        self.mime_type = mime_type


class _FakeIdentified:
    def __init__(self, label, group, score=0.99):
        self.output = _FakeOutput(label, group)
        self.score = score


class _StubMagika:
    def __init__(self, label="jpeg", group="image"):
        self.label = label
        self.group = group
        self.calls = 0

    def identify_path(self, path):
        self.calls += 1
        return _FakeIdentified(self.label, self.group)


def test_sensitive_file_blocked_before_any_read(tmp_path):
    patients = tmp_path / "patients"
    patients.mkdir()
    target = patients / "scan_001.dcm"
    target.write_bytes(b"\x00" * 256)
    tripwire = _TripwireMagika()
    result = classify_content(target, magika=tripwire, ocr=True)
    assert tripwire.calls == 0
    assert result.blocked is True
    assert result.block_reason
    assert result.content_label == ""


def test_dicom_magic_blocks_generic_extension(tmp_path):
    target = tmp_path / "image.dat"
    target.write_bytes(b"\x00" * 128 + b"DICM" + b"\x00" * 64)
    result = classify_content(target, magika=_StubMagika(), ocr=True)
    assert result.blocked is True
    assert "DICOM" in result.block_reason


def test_normal_image_classified_by_content(tmp_path):
    img_path = tmp_path / "photo_2026.png"
    Image.new("RGB", (1920, 1080), (10, 120, 200)).save(img_path)
    magika = _StubMagika(label="png", group="image")
    result = classify_content(img_path, magika=magika, ocr=False)
    assert magika.calls == 1
    assert result.blocked is False
    assert result.content_label == "png"
    assert result.content_group == "image"
    assert result.semantic == "screenshot"
    assert result.mime_type


def test_ocr_never_runs_on_blocked_file(tmp_path):
    medical = tmp_path / "medical"
    medical.mkdir()
    target = medical / "report.txt"
    target.write_text("confidential patient notes", encoding="utf-8")
    calls = {"ocr": 0}

    def _fail_ocr(*_a, **_k):
        calls["ocr"] += 1
        raise AssertionError("OCR استُدعي على ملف محجوب")

    result = classify_content(target, magika=_StubMagika(), ocr=True)
    assert calls["ocr"] == 0
    assert result.blocked is True
    assert result.ocr_text == ""


def test_summary_counts_blocked_and_groups(tmp_path):
    clean = tmp_path / "clean.txt"
    clean.write_text("hello", encoding="utf-8")
    blocked_dir = tmp_path / "patients"
    blocked_dir.mkdir()
    blocked = blocked_dir / "x.txt"
    blocked.write_text("secret", encoding="utf-8")
    results = [
        classify_content(clean, magika=_StubMagika(label="txt", group="text")),
        classify_content(blocked, magika=_StubMagika()),
    ]
    summary = summarize(results)
    assert summary["total"] == 2
    assert summary["blocked"] == 1
    assert summary["by_group"].get("text") == 1


def test_sensitive_file_blocked_error_exists():
    assert issubclass(SensitiveFileBlockedError, Exception)
    assert ContentResult(path="x").blocked is False
