"""الحاجز: أسرار بالاسم + منع قرّاء المحتوى غير المحميين (مراجعة 2026-11-21).

كل اختبار يتحقق من **عدم فتح الملف** فعليًا (تجسس على open) لا من قيمة الإرجاع وحدها.
"""
from __future__ import annotations

import builtins
import io
import os
import pathlib
import types

import pytest

from src.core.sensitive_barrier import (
    SensitiveFileBlockedError,
    classify_sensitivity,
    is_secret_file,
    is_sensitive_path,
)


@pytest.mark.parametrize("name", [
    ".env", ".env.local", ".env.production", "id_rsa", "id_ed25519", "id_ed25519_work",
    "server.pem", "client.p12", "vault.kdbx", ".netrc", "credentials.json", "authorized_keys",
    ".git-credentials", "wallet.dat", ".pypirc",
])
def test_secret_names_are_blocked_in_any_folder(name):
    assert is_secret_file(f"/home/u/projects/app/{name}")
    assert is_sensitive_path(f"/home/u/projects/app/{name}") is True


@pytest.mark.parametrize("name", [
    "tokenizer.py", "environment.txt", ".env.example", ".env.sample",
    "notes.txt", "keyboard_layout.pdf", "credentials_policy.md", "envelope.docx",
])
def test_lookalike_names_are_not_blocked(name):
    assert not is_secret_file(f"/home/u/docs/{name}")
    assert is_sensitive_path(f"/home/u/docs/{name}") is False


def test_classification_reason_mentions_secret():
    info = classify_sensitivity("/home/u/app/.env")
    assert info["is_sensitive"] is True and "أسرار" in info["reason"]


class _OpenSpy:
    """يسجّل كل فتح لمسارات مراقَبة عبر builtins.open/io.open/Path.open."""

    def __init__(self, monkeypatch, watched):
        self.watched = {os.fspath(p) for p in watched}
        self.hits: set[str] = set()
        real_open, real_path_open = builtins.open, pathlib.Path.open

        def note(p):
            try:
                if os.fspath(p) in self.watched:
                    self.hits.add(os.path.basename(os.fspath(p)))
            except TypeError:
                pass

        monkeypatch.setattr(builtins, "open", lambda f, *a, **k: (note(f), real_open(f, *a, **k))[1])
        monkeypatch.setattr(io, "open", builtins.open)
        monkeypatch.setattr(pathlib.Path, "open",
                            lambda self, *a, **k: (note(self), real_path_open(self, *a, **k))[1])


@pytest.fixture
def sensitive_files(tmp_path):
    d = tmp_path / "patients"
    d.mkdir()
    files = {}
    for name, data in (("report.txt", b"PATIENT-DATA"), ("scan_report.pdf", b"%PDF fake"),
                       ("notes.docx", b"PK fake"), ("IMG_0001.jpg", b"\xff\xd8\xff")):
        p = d / name
        p.write_bytes(data)
        files[name] = p
    env = tmp_path / "proj" / ".env"
    env.parent.mkdir()
    env.write_text("API_KEY=abc")
    files[".env"] = env
    return files


def test_ai_engine_never_opens_or_sends_sensitive_file(sensitive_files, monkeypatch):
    from src.core.ai_engine import AIEngine
    sent = []
    client = types.SimpleNamespace(chat=lambda *a, **k: sent.append(1) or {"message": {"content": "x"}})
    eng = AIEngine()
    eng._get_ollama = lambda: client
    spy = _OpenSpy(monkeypatch, sensitive_files.values())
    for key in ("report.txt", ".env"):
        with pytest.raises(SensitiveFileBlockedError):
            eng.summarize_file(str(sensitive_files[key]))
        with pytest.raises(SensitiveFileBlockedError):
            eng.extract_keywords(str(sensitive_files[key]))
    assert not spy.hits and not sent


def test_multimodal_extractors_block_before_any_read(sensitive_files, monkeypatch):
    import src.core.file_inventory as inv
    from src.core.multimodal_processor import MultimodalProcessor

    def boom(*_a, **_k):
        raise AssertionError("المستخرج الأدنى استُدعي لملف حساس")

    for fn in ("_extract_pdf_text", "_extract_docx_text", "_extract_xlsx_text", "_extract_pptx_text"):
        monkeypatch.setattr(inv, fn, boom)
    mp = MultimodalProcessor()
    spy = _OpenSpy(monkeypatch, sensitive_files.values())
    p = str(sensitive_files["scan_report.pdf"])
    for fp, call in (
        (p, mp.extract_text_from_pdf),
        (str(sensitive_files["notes.docx"]), mp.extract_text_from_docx),
        (p, mp.extract_text_from_xlsx),
        (p, mp.extract_text_from_pptx),
    ):
        with pytest.raises(SensitiveFileBlockedError):
            call(fp)
    assert not spy.hits


def test_process_image_sensitive_skips_exif_ocr_and_ai(sensitive_files, monkeypatch):
    import src.core.multimodal_processor as mpmod

    def boom(*_a, **_k):
        raise AssertionError("قُرئت صورة حساسة")

    monkeypatch.setattr(mpmod, "extract_image_metadata", boom)
    spy = _OpenSpy(monkeypatch, sensitive_files.values())
    with pytest.raises(SensitiveFileBlockedError):
        mpmod.MultimodalProcessor().process_image(str(sensitive_files["IMG_0001.jpg"]))
    assert not spy.hits


def test_file_copilot_summarize_and_index_skip_sensitive(sensitive_files, monkeypatch):
    from src.core.file_copilot import FileCopilot
    fc = FileCopilot()
    calls = []
    fc._init_hybrid_search = lambda: None
    fc._init_rag_engine = lambda: None
    fc._hybrid_search = types.SimpleNamespace(
        _extract_text=lambda fp: calls.append(fp) or "text", index_files=lambda fp: 0)
    spy = _OpenSpy(monkeypatch, sensitive_files.values())
    assert "محظور" in fc.summarize_file(str(sensitive_files["report.txt"]))
    fc.index_files([str(sensitive_files["report.txt"]), str(sensitive_files[".env"])])
    assert not calls and not spy.hits


def test_non_sensitive_file_still_processed(tmp_path):
    from src.core.ai_engine import AIEngine
    f = tmp_path / "notes.txt"
    f.write_text("hello world")
    eng = AIEngine()
    eng._get_ollama = lambda: types.SimpleNamespace(
        chat=lambda *a, **k: {"message": {"content": "ملخص"}})
    assert eng.summarize_file(str(f)) == "ملخص"


def _dicom_bytes() -> bytes:
    return b"\x00" * 128 + b"DICM" + b"\x00" * 64


def test_extensionless_dicom_is_still_detected_by_magic(tmp_path):
    f = tmp_path / "IM000001"
    f.write_bytes(_dicom_bytes())
    assert is_sensitive_path(f) is True
    assert "DICOM" in classify_sensitivity(f)["reason"]


def test_dicom_disguised_as_jpg_is_detected(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(_dicom_bytes())
    assert is_sensitive_path(f) is True


def test_barrier_does_not_open_files_already_decided_by_name(sensitive_files, monkeypatch):
    spy = _OpenSpy(monkeypatch, sensitive_files.values())
    for p in sensitive_files.values():
        assert is_sensitive_path(p) is True
    assert not spy.hits, "الحاجز فتح ملفًا حُسم بالاسم/المسار"


def test_barrier_does_not_probe_unrelated_extensions(tmp_path, monkeypatch):
    f = tmp_path / "data.csv"
    f.write_bytes(_dicom_bytes())          # ترويسة DICM لكن امتداد غير مرشّح
    spy = _OpenSpy(monkeypatch, [f])
    assert is_sensitive_path(f) is False
    assert not spy.hits, "فُتح ملف بامتداد غير مرشّح لمسح ضخم"
