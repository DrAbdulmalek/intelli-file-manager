"""اختبارات وحدة لمحوّل OCR المركزي (ocr_service) — بلا ثنائيات حقيقية.

يغطي: عقد المفاتيح القديم، ترتيب المحركات والتراجع، الفشل الرشيق،
التراجع لـ pytesseract المباشر بلا ocr-core، القصّ، flag المعالجة اللاحقة،
ومسارا تحسين الصورة (ocr-core / PIL).
"""
import os
import shutil
import sys

import pytest

from src.core import ocr_service


class _FakeResult:
    def __init__(self, text="", engine="fake", confidence=0.0, error=None):
        self.text = text
        self.engine = engine
        self.confidence = confidence
        self.error = error


class _FakeEngine:
    def __init__(self, name, result=None, exc=None, avail=True):
        self.name = name
        self._result = result
        self._exc = exc
        self._avail = avail

    def available(self):
        return self._avail

    def process_image(self, path):
        if self._exc:
            raise self._exc
        return self._result


@pytest.fixture(autouse=True)
def _reset_caches():
    ocr_service.reset_caches()
    yield
    ocr_service.reset_caches()


def _use_engines(monkeypatch, engines):
    monkeypatch.setattr(ocr_service, "_get_engines", lambda: engines)


def _png(tmp_path, name="x.png"):
    Image = pytest.importorskip("PIL.Image")
    p = tmp_path / name
    Image.new("RGB", (40, 20), "white").save(p)
    return str(p)


def test_contract_with_first_available_engine(monkeypatch, tmp_path):
    img = _png(tmp_path)
    _use_engines(monkeypatch, [_FakeEngine("fake", _FakeResult(text=" نص عربي ", engine="fake", confidence=0.87))])
    res = ocr_service.ocr_image(img)
    assert res["ocr_success"] is True
    assert res["extracted_text"] == "نص عربي"
    assert res["ocr_engine"] == "fake"
    assert res["ocr_confidence"] == 0.87


def test_fallthrough_on_error_then_success(monkeypatch, tmp_path):
    img = _png(tmp_path)
    _use_engines(monkeypatch, [
        _FakeEngine("paddle", exc=RuntimeError("boom")),
        _FakeEngine("tesseract", _FakeResult(text="hello", engine="tesseract", confidence=0.5)),
    ])
    res = ocr_service.ocr_image(img)
    assert res["ocr_success"] is True and res["ocr_engine"] == "tesseract"
    assert res["paddle_error"] == "boom"


def test_unavailable_engine_is_skipped(monkeypatch, tmp_path):
    img = _png(tmp_path)
    _use_engines(monkeypatch, [
        _FakeEngine("paddle", _FakeResult(text="nope"), avail=False),
        _FakeEngine("tesseract", _FakeResult(text="ok", engine="tesseract")),
    ])
    assert ocr_service.ocr_image(img)["ocr_engine"] == "tesseract"


def test_all_engines_fail_no_raise(monkeypatch, tmp_path):
    img = _png(tmp_path)
    _use_engines(monkeypatch, [
        _FakeEngine("paddle", exc=RuntimeError("a")),
        _FakeEngine("tesseract", _FakeResult(text="", error="empty")),
    ])
    res = ocr_service.ocr_image(img)
    assert res["ocr_success"] is False and res["extracted_text"] == ""


def test_legacy_fallback_without_ocr_core(monkeypatch):
    monkeypatch.setattr(ocr_service, "_get_engines", lambda: [])
    monkeypatch.setitem(sys.modules, "pytesseract", None)  # ImportError عند الاستيراد
    res = ocr_service.ocr_image("whatever.png")
    assert res["ocr_success"] is False and res["extracted_text"] == ""


def test_max_chars_truncation(monkeypatch, tmp_path):
    img = _png(tmp_path)
    _use_engines(monkeypatch, [_FakeEngine("fake", _FakeResult(text="abcdefghij", engine="fake"))])
    assert ocr_service.ocr_image(img, max_chars=4)["extracted_text"] == "abcd"


def test_postprocess_flag_adds_info(monkeypatch, tmp_path):
    img = _png(tmp_path)
    _use_engines(monkeypatch, [_FakeEngine("fake", _FakeResult(text="المحتويات", engine="fake"))])
    res = ocr_service.ocr_image(img, postprocess=True)
    info = res.get("ocr_postprocess")
    assert info is not None
    assert ("corrections_applied" in info) or ("corrections_error" in info)


def test_enhance_image_pil_fallback(monkeypatch, tmp_path):
    img = _png(tmp_path)
    monkeypatch.setattr(ocr_service, "_core_enhance", lambda p: None)
    out = ocr_service.enhance_image(img)
    try:
        assert out is not None and os.path.exists(out)
    finally:
        if out:
            os.unlink(out)


def test_core_enhance_live_when_preprocess_extra(tmp_path):
    pytest.importorskip("cv2")
    pytest.importorskip("ocr_core.preprocess.enhance")
    img = _png(tmp_path)
    out = ocr_service._core_enhance(img)
    try:
        assert out is None or os.path.exists(out)
        if out:
            assert os.path.getsize(out) > 0
    finally:
        if out:
            os.unlink(out)


def test_real_image_without_binaries_is_graceful(tmp_path):
    """بلا ثنائيات (حالة CI): فشل واضح بلا استثناءات."""
    img = _png(tmp_path)
    res = ocr_service.ocr_image(img)
    assert "extracted_text" in res and "ocr_success" in res
    if not shutil.which("tesseract"):
        assert res["ocr_success"] is False
