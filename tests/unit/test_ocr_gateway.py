"""اختبارات بوابة OCR التعاقدية (ocr_gateway) — F004.

تثبت: (1) البوابة وكيل ديناميكي للواجهة العامة لـocr_service؛
(2) الرقع على ocr_service تصل عبر البوابة (دورة حياة الاختبارات محفوظة)؛
(3) صفر استيراد مباشر لمحركات OCR في src/ خارج البوابة (مرآة بوابة verify.sh).
"""
import re
from pathlib import Path

from src.core import ocr_gateway, ocr_service

REPO_ROOT = Path(__file__).resolve().parents[2]

# نفس نمط بوابة verify.sh (gate:ocr-imports-gateway)
FORBIDDEN_ENGINE_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+"
    r"(pytesseract|paddleocr|easyocr|rapidocr|surya|ocr_core)(?:\s|\.)"
)


def test_gateway_reexports_public_api():
    for name in ocr_gateway.__all__:
        assert getattr(ocr_gateway, name) is getattr(ocr_service, name), name


def test_gateway_proxies_dynamically(monkeypatch):
    """رقعة على ocr_service يجب أن تصل عبر البوابة (حل السمة عند كل وصول)."""
    calls = []
    fake = {"ocr_success": False, "extracted_text": "", "ocr_engine": "patched"}

    def _fake_ocr(filepath, *args, **kwargs):
        calls.append(filepath)
        return dict(fake)

    monkeypatch.setattr(ocr_service, "ocr_image", _fake_ocr)
    assert ocr_gateway.ocr_image("whatever.png") == fake
    assert calls == ["whatever.png"]


def test_any_engine_availability_flags():
    assert isinstance(ocr_gateway.any_engine_available(), bool)
    assert isinstance(ocr_gateway.pytesseract_available(), bool)


def test_no_direct_engine_imports_outside_gateway():
    """مرآة بايثون لبوابة verify.sh — أي مخالف تُرفض هنا قبل الالتزام."""
    offenders = []
    for path in sorted((REPO_ROOT / "src").rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel == "src/core/ocr_service.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if FORBIDDEN_ENGINE_IMPORT_RE.match(line):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert offenders == []
