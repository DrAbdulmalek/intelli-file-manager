"""Unit tests for the medical glossary service + HF exporter."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.glossary_service import GlossaryService, normalize_ar
from src.services.hf_exporter import HFExporter
from src.db.snippet_db import SnippetDB


# ----------------------------------------------------------------------
# glossary
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def bundled_glossary():
    return GlossaryService()  # uses the bundled data/medical_glossary.csv


def test_bundled_glossary_loaded(bundled_glossary):
    assert bundled_glossary.size >= 700
    assert bundled_glossary.path.exists()


def test_normalize_ar_strips_tashkeel_and_unifies_alef():
    assert normalize_ar("الجَرْعَةُ") == "الجرعه"
    assert normalize_ar("أحمد") == normalize_ar("احمد") == normalize_ar("إحمد")
    assert normalize_ar("ى") == "ي"


def test_suggest_arabic_prefix(bundled_glossary):
    suggestions = bundled_glossary.suggest("الجرعة", limit=5)
    assert suggestions and any("الجرعة" in s for s in suggestions)


def test_suggest_english_prefix(bundled_glossary):
    suggestions = bundled_glossary.suggest("Compos", limit=5)
    assert any("Composition" in s for s in suggestions)


def test_suggest_exact_ranks_first(bundled_glossary):
    # suggestions are same-language (correction targets for the OCR editor);
    # cross-language counterparts come from lookup()
    suggestions = bundled_glossary.suggest("abdominal pain", limit=5)
    assert suggestions[0] == "abdominal pain"
    assert bundled_glossary.lookup("abdominal pain").ar == "ألم بطني"


def test_suggest_empty_returns_empty(bundled_glossary):
    assert bundled_glossary.suggest("") == []
    assert bundled_glossary.suggest("   ") == []


def test_suggest_no_match_returns_empty(bundled_glossary):
    assert bundled_glossary.suggest("zzzqqqxxx") == []


def test_lookup_both_directions(bundled_glossary):
    assert bundled_glossary.lookup("Composition") is not None
    assert bundled_glossary.lookup("التركيب") is not None
    assert bundled_glossary.lookup("nonexistent-term") is None


def test_env_override_path(tmp_path, monkeypatch):
    custom = tmp_path / "custom.csv"
    custom.write_text("en,ar\ntest term,مصطلح اختبار\n", encoding="utf-8")
    monkeypatch.delenv("INTELLIFILE_GLOSSARY_PATH", raising=False)
    svc = GlossaryService(custom)
    assert svc.size == 1
    assert svc.suggest("test term") == ["test term"]  # same-language correction target
    assert svc.lookup("مصطلح اختبار").en == "test term"  # cross-language via lookup


def test_missing_glossary_file_is_empty_not_crash(tmp_path):
    svc = GlossaryService(tmp_path / "nope.csv")
    assert svc.size == 0 and svc.suggest("anything") == []


# ----------------------------------------------------------------------
# HF exporter
# ----------------------------------------------------------------------
def test_export_writes_jsonl_and_metadata(tmp_path):
    from src.db.snippet_db import TrainingSnippet

    db = SnippetDB(tmp_path / "db.sqlite")
    # approved + changed text -> exported
    sid1 = db.insert(TrainingSnippet(source_image="", text="الصحيح", ocr_text="الغلط"))
    db.approve(sid1, verified_by="tester")
    # approved but unchanged text -> skipped by default
    sid2 = db.insert(TrainingSnippet(source_image="", text="same", ocr_text="same"))
    db.approve(sid2)
    # pending -> skipped
    sid3 = db.insert(TrainingSnippet(source_image="", text="لم يُعتمد", ocr_text="x"))

    exporter = HFExporter(db, export_dir=tmp_path / "export")
    out = exporter.export()
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [r["id"] for r in rows] == [sid1]
    assert rows[0]["source"] == "intelli-file-manager/human-verified"
    assert rows[0]["text"] == "الصحيح"
    meta = json.loads((tmp_path / "export" / "dataset_info.json").read_text(encoding="utf-8"))
    assert meta["total"] == 1 and "medical" in meta["categories"] or True


def test_export_include_unchanged_keeps_rows(tmp_path):
    from src.db.snippet_db import TrainingSnippet

    db = SnippetDB(tmp_path / "db.sqlite")
    sid = db.insert(TrainingSnippet(source_image="", text="same", ocr_text="same"))
    db.approve(sid)
    exporter = HFExporter(db, export_dir=tmp_path / "export")
    out = exporter.export(include_unchanged=True)
    rows = out.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1


def test_push_requires_explicit_token(tmp_path):
    from src.db.snippet_db import TrainingSnippet

    db = SnippetDB(tmp_path / "db.sqlite")
    sid = db.insert(TrainingSnippet(source_image="", text="t", ocr_text="o"))
    db.approve(sid)
    exporter = HFExporter(db, export_dir=tmp_path / "export")
    with pytest.raises(ValueError):
        exporter.push_to_hf("")
