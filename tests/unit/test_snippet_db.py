"""Unit tests for SnippetDB — the training-snippets SQLite store."""
from __future__ import annotations

import sqlite3

import pytest

from src.db.snippet_db import SnippetDB, TrainingSnippet


@pytest.fixture()
def db(tmp_path):
    return SnippetDB(tmp_path / "snippets.db")


def _make(**overrides) -> TrainingSnippet:
    base = dict(
        source_image="scan1.png",
        level="word",
        bbox=(10, 20, 110, 50),
        text="الجرعة",
        ocr_text="الجرعـة",
        confidence=0.0,
        language="ar",
        category="medical",
    )
    base.update(overrides)
    return TrainingSnippet(**base)


def test_insert_and_get_roundtrip(db):
    sid = db.insert(_make())
    assert sid == 1
    got = db.get(sid)
    assert got is not None
    assert got.text == "الجرعة" and got.ocr_text == "الجرعـة"
    assert got.bbox == (10, 20, 110, 50)
    assert got.status == "pending" and got.language == "ar"


def test_update_bbox_is_the_core_user_edit(db):
    sid = db.insert(_make())
    assert db.update_bbox(sid, (0, 0, 50, 30)) is True
    assert db.get(sid).bbox == (0, 0, 50, 30)
    assert db.update_bbox(999, (0, 0, 1, 1)) is False


def test_update_bbox_rejects_malformed(db):
    sid = db.insert(_make())
    with pytest.raises(ValueError):
        db.update_bbox(sid, (1, 2, 3))  # type: ignore[arg-type]


def test_update_text_and_category(db):
    sid = db.insert(_make())
    assert db.update_text(sid, "الجرعة اليومية")
    assert db.update_category(sid, "formula")
    got = db.get(sid)
    assert got.text == "الجرعة اليومية" and got.category == "formula"
    assert got.updated_at >= got.created_at


def test_approve_and_reject_workflow(db):
    s1 = db.insert(_make())
    s2 = db.insert(_make(text="x", ocr_text="y"))
    assert db.approve(s1, verified_by="dr.malek") is True
    assert db.reject(s2, reason="garbled") is True
    assert db.get(s1).status == "approved"
    assert db.get(s1).verified_by == "dr.malek"
    assert db.get(s2).status == "rejected"
    assert db.get(s2).notes == "garbled"
    approved = db.get_approved()
    assert [s.id for s in approved] == [s1]


def test_get_by_source_orders_reading_order(db):
    db.insert(_make(bbox=(0, 100, 50, 130)))
    db.insert(_make(bbox=(10, 0, 60, 30)))
    db.insert(_make(bbox=(0, 50, 60, 80)))
    rows = db.get_by_source("scan1.png")
    assert [s.bbox[1] for s in rows] == [0, 50, 100]


def test_delete_removes_row(db):
    sid = db.insert(_make())
    assert db.delete(sid) is True
    assert db.get(sid) is None
    assert db.delete(sid) is False


def test_stats_counts_by_status_and_category(db):
    db.insert(_make())
    db.insert(_make(category="general"))
    db.insert(_make(category="general"))
    stats = db.stats()
    assert stats["total"] == 3
    assert stats["by_status"] == {"pending": 3}
    assert stats["by_category"] == {"medical": 1, "general": 2}


def test_to_dict_serializes_bbox_as_list(db):
    sid = db.insert(_make())
    d = db.to_dict(db.get(sid))
    assert d["bbox"] == [10, 20, 110, 50]
    assert d["text"] == "الجرعة"


def test_default_db_schema_has_indexes(tmp_path):
    path = tmp_path / "idx.db"
    SnippetDB(path)
    conn = sqlite3.connect(path)
    idx = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    conn.close()
    assert "idx_snippets_status" in idx and "idx_snippets_source" in idx
