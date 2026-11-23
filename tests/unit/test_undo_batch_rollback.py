# -*- coding: utf-8 -*-
"""اختبارات P1 المُقوّاة: rollback_batch + التعويض + fail-closed (مراجعة مستقلة).

بيانات اصطناعية في tmp_path فقط.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.rule_schemas import UndoEntry, ActionType
from src.core.safe_mover import SafeMover, compute_sha256
from src.core.undo_log import UndoLog


@pytest.fixture()
def mover():
    return SafeMover(verify_checksum=True, move_sidecar=False)


@pytest.fixture()
def log():
    return UndoLog()


def _move_op(mover, log, src, target_dir, batch):
    src = Path(src)
    res = mover.move(str(src), str(Path(target_dir) / src.name))
    assert res.success, res.error
    final = Path(res.final_path)
    log.append(UndoEntry(
        action_type=ActionType.MOVE.value, file_path=str(src),
        file_path_after=str(final), rule_name="test", timestamp="t",
        batch_id=batch,
    ))
    return final


def _copy_op(mover, log, src, target_dir, batch):
    src = Path(src)
    res = mover.copy(str(src), str(Path(target_dir) / src.name))
    assert res.success, res.error
    final = Path(res.final_path)
    log.append(UndoEntry(
        action_type=ActionType.COPY.value, file_path=str(src),
        file_path_after=str(final), rule_name="test", timestamp="t",
        batch_id=batch, checksum_after=compute_sha256(final),
    ))
    return final


# ─── الأساس: التراجع السليم ──────────────────────────────────────────────

def test_rollback_batch_reverses_move(tmp_path, mover, log):
    src = tmp_path / "a.txt"; src.write_text("data", encoding="utf-8")
    dst_dir = tmp_path / "d"; dst_dir.mkdir()
    target = _move_op(mover, log, src, dst_dir, "B1")
    out = log.rollback_batch("B1")
    assert out["rolled_back"] == ["move"]
    assert not target.exists()
    assert src.exists() and src.read_text(encoding="utf-8") == "data"
    assert len(log) == 0


def test_conflict_aborts_without_mutation(tmp_path, mover, log):
    d1 = tmp_path / "d1"; d1.mkdir()
    d2 = tmp_path / "d2"; d2.mkdir()
    s1 = tmp_path / "f1.txt"; s1.write_text("one", encoding="utf-8")
    _move_op(mover, log, s1, d1, "B1")
    s2 = tmp_path / "f2.txt"; s2.write_text("two", encoding="utf-8")
    c2 = _copy_op(mover, log, s2, d2, "B1")
    c2.write_text("user-edited!", encoding="utf-8")
    with pytest.raises(RuntimeError, match="لم يُعدّل أي ملف"):
        log.rollback_batch("B1")
    assert c2.read_text(encoding="utf-8") == "user-edited!"
    assert (d1 / "f1.txt").exists() and not s1.exists()
    assert len(log) == 2


def test_modified_copy_survives_rollback_attempt(tmp_path, mover, log):
    s = tmp_path / "orig.txt"; s.write_text("v1", encoding="utf-8")
    d = tmp_path / "out"; d.mkdir()
    copied = _copy_op(mover, log, s, d, "B2")
    copied.write_text("my later work", encoding="utf-8")
    with pytest.raises(RuntimeError, match="عُدّل الملف"):
        log.rollback_batch("B2")
    assert copied.read_text(encoding="utf-8") == "my later work"
    assert s.read_text(encoding="utf-8") == "v1"


# ─── Finding 4: فشل منتصف الدفعة → تعويض + لا حذف سجلات ────────────────

def test_mid_batch_failure_compensates_and_keeps_records(tmp_path, monkeypatch, mover, log):
    from src.core.rule_engine import _load_sidecar_tags, _save_sidecar_tags
    base = tmp_path
    d1 = base / "d1"; d1.mkdir()
    d2 = base / "d2"; d2.mkdir()
    c1 = base / "c1"; c1.mkdir()
    c2 = base / "c2"; c2.mkdir()
    f1 = base / "f1.txt"; f1.write_text("moved-1", encoding="utf-8")
    f2 = base / "f2.txt"; f2.write_text("copied-1", encoding="utf-8")
    f3 = base / "f3.txt"; f3.write_text("moved-2", encoding="utf-8")
    f4 = base / "f4.txt"; f4.write_text("copied-2", encoding="utf-8")
    t1 = base / "t1.txt"; t1.write_text("tagged", encoding="utf-8")
    _save_sidecar_tags(str(t1), [])
    B = "B9"
    m1 = _move_op(mover, log, f1, d1, B)
    cp1 = _copy_op(mover, log, f2, c1, B)
    m2 = _move_op(mover, log, f3, d2, B)
    cp2 = _copy_op(mover, log, f4, c2, B)
    log.append(UndoEntry(
        action_type=ActionType.TAG.value, file_path=str(t1),
        rule_name="test", timestamp="t", batch_id=B, tags_added=["x-tag"],
    ))
    _save_sidecar_tags(str(t1), ["x-tag"])

    assert len(log) == 5
    # حقن فشل في التراجع عن النقل (الثالث في الترتيب العكسي)
    def inject(self, entry):
        raise RuntimeError("حقن فشل اختباري")
    monkeypatch.setattr(UndoLog, "_rollback_move", inject)
    with pytest.raises(RuntimeError, match="استرداد تعويضي"):
        log.rollback_batch(B)
    monkeypatch.undo()
    # 1) لا حذف أي سجل
    assert len(log) == 5
    # 2) الحالة المُعادها = حالة ما بعد الدفعة الأصلية (تعويضcomplete)
    assert (d1 / "f1.txt").exists()          # لم يُمس (التراجع لم يصل إليه)
    assert (c1 / "f2.txt").exists()          # لم يُمس
    assert (d2 / "f3.txt").exists()          # عُكس ثم عُوّض (أعيد نقله)
    assert not f3.exists()
    assert (c2 / "f4.txt").exists()          # عُكس (حُذف) ثم عُوّض (أعيدت النسخة)
    assert _load_sidecar_tags(str(t1)) == ["x-tag"]  # عُكس ثم عُوّض
    # 3) الاسترداد: إزالة الحقن → التراجع يكتمل بالكامل دون فقد
    out = log.rollback_batch(B)
    assert out["rolled_back"] == ["tag", "copy", "move", "copy", "move"]
    assert len(log) == 0
    # الحالة السابقة بالكامل استُعيدت
    assert not (d1 / "f1.txt").exists() and f1.exists()
    assert not (c1 / "f2.txt").exists() and f2.exists()
    assert not (d2 / "f3.txt").exists() and f3.exists()
    assert not (c2 / "f4.txt").exists() and f4.exists()
    assert _load_sidecar_tags(str(t1)) == []


# ─── Finding 5: غياب الملف المستهدف — دلالات لكل نوع ────────────────────

def test_move_missing_target_source_present_marks_already(tmp_path, log):
    src = tmp_path / "still-here.txt"; src.write_text("s", encoding="utf-8")
    gone = tmp_path / "nowhere" / "still-here.txt"
    log.append(UndoEntry(
        action_type=ActionType.MOVE.value, file_path=str(src),
        file_path_after=str(gone), rule_name="test", timestamp="t",
        batch_id="BM",
        # F11: هوية موثوقة — بصمة الملف الموجود في المسار الأصلي تطابق
        # بصمة الملف بعد النقل الأصلي (MOVE لا يغيّر المحتوى)
        checksum_after=compute_sha256(src),
    ))
    out = log.rollback_batch("BM")
    assert out["already_rolled_back"] == ["move"]
    # fail-closed: السجل يبقى ولا يُحذف بلا دليل عكس فعلي
    assert len(log) == 1
    assert src.exists()


def test_move_missing_target_and_source_aborts(tmp_path, log):
    log.append(UndoEntry(
        action_type=ActionType.MOVE.value, file_path="/nonexistent/src.txt",
        file_path_after="/nonexistent/dst.txt", rule_name="test",
        timestamp="t", batch_id="BM2",
    ))
    with pytest.raises(RuntimeError, match="أُجهض"):
        log.rollback_batch("BM2")
    assert len(log) == 1


def test_copy_missing_target_aborts(tmp_path, mover, log):
    src = tmp_path / "src.txt"; src.write_text("s", encoding="utf-8")
    log.append(UndoEntry(
        action_type=ActionType.COPY.value, file_path=str(src),
        file_path_after="/nonexistent/copy.txt", rule_name="test",
        timestamp="t", batch_id="BC",
    ))
    with pytest.raises(RuntimeError, match="أُجهض"):
        log.rollback_batch("BC")
    assert len(log) == 1
    assert src.exists()


# ─── Finding 6: preflight أنواع sidecar ─────────────────────────────────

def test_sidecar_op_missing_file_aborts(tmp_path, log):
    log.append(UndoEntry(
        action_type=ActionType.TAG.value, file_path="/nonexistent/f.txt",
        rule_name="test", timestamp="t", batch_id="BT",
        tags_added=["q"],
    ))
    with pytest.raises(RuntimeError, match="أساسي مفقود"):
        log.rollback_batch("BT")
    assert len(log) == 1


def test_sidecar_ops_rollback_happy_path(tmp_path, log):
    from src.core.rule_engine import (
        _load_sidecar, _load_sidecar_tags, _save_sidecar, _save_sidecar_tags,
    )
    f = tmp_path / "doc.txt"; f.write_text("x", encoding="utf-8")
    _save_sidecar_tags(str(f), [])
    _save_sidecar(str(f), {"tags": [], "category": "old"})
    B = "BS"
    log.append(UndoEntry(action_type=ActionType.TAG.value, file_path=str(f),
                         timestamp="t", batch_id=B, tags_added=["t-new"]))
    # الحالة الفعلية بعد الدفعة تُطبَّق على sidecar كما يفعل المنفّذ (_exec_tag)
    _save_sidecar_tags(str(f), ["t-new"])
    log.append(UndoEntry(action_type=ActionType.SET_CATEGORY.value, file_path=str(f),
                         timestamp="t", batch_id=B, old_category="old",
                         new_category="new"))
    _save_sidecar(str(f), {"tags": ["t-new"], "category": "new"})
    # الحالة بعد الدفعة
    assert _load_sidecar_tags(str(f)) == ["t-new"]
    assert _load_sidecar(str(f))["category"] == "new"
    out = log.rollback_batch(B)
    assert out["rolled_back"] == ["set_category", "tag"]
    assert _load_sidecar_tags(str(f)) == []
    assert _load_sidecar(str(f))["category"] == "old"


# ─── التوافق الخلفي ──────────────────────────────────────────────────────

def test_old_entries_without_batch_id_still_load(tmp_path):
    p = tmp_path / "undo.json"
    p.write_text(json.dumps({
        "version": 1,
        "saved_at": "2025-01-01T00:00:00",
        "entries": [{
            "action_type": "tag",
            "file_path": "/x/صور/old.jpg",
            "rule_name": "legacy",
            "tags_added": ["old-tag"],
            "tags_removed": [],
            "timestamp": "2025-01-01T00:00:00",
            "success": True,
        }],
    }, ensure_ascii=False), encoding="utf-8")
    log = UndoLog(p)
    assert len(log) == 1
    assert log.entries[0].batch_id == ""
    e = log.rollback_last()
    assert e is not None and e.action_type == "tag"


def test_empty_and_unknown_batch(log):
    with pytest.raises(ValueError):
        log.rollback_batch("")
    with pytest.raises(ValueError):
        log.rollback_batch("NOPE-404")
