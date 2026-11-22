# -*- coding: utf-8 -*-
"""اختبارات P1: rollback_batch مع فحص تعارض مبدئي (abort-before-mutate).

لا تلمس أي ملفات مستخدم حقيقية — كل شيء في pytest tmp_path.
"""
from __future__ import annotations

import json

import pytest

from src.core.rule_schemas import UndoEntry
from src.core.undo_log import UndoLog


@pytest.fixture()
def files(tmp_path):
    src1 = tmp_path / "a"; src1.mkdir()
    dst1 = tmp_path / "b"; dst1.mkdir()
    f1 = src1 / "doc1.txt"; f1.write_text("hello-1", encoding="utf-8")
    f2 = src1 / "doc2.txt"; f2.write_text("hello-2", encoding="utf-8")
    return tmp_path, src1, dst1, f1, f2


def _real_move(log: UndoLog, src, dst) -> UndoEntry:
    """نقل حقيقي عبر SafeMover + تسجيل UndoEntry (move)."""
    from src.core.safe_mover import SafeMover, compute_sha256
    mover = SafeMover(verify_checksum=True, move_sidecar=False)
    before = compute_sha256(src)
    result = mover.move(str(src), str(dst / src.name))
    assert result.success, result.error
    entry = UndoEntry(
        action_type="move",
        file_path=str(src),
        file_path_after=result.final_path,
        rule_name="test",
        timestamp="2026-11-22T00:00:00",
        batch_id="B1",
        checksum_after=result.checksum_after or compute_sha256(result["final_path"] if isinstance(result, dict) else __import__("pathlib").Path(expected := dst / src.name)),
    )
    log.append(entry)
    return entry


def test_rollback_batch_reverses_move(tmp_path):
    log = UndoLog()
    src = tmp_path / "a.txt"
    dst_dir = tmp_path / "d"; dst_dir.mkdir()
    src.write_text("data", encoding="utf-8")
    from src.core.safe_mover import SafeMover, compute_sha256
    mover = SafeMover(verify_checksum=True, move_sidecar=False)
    res = mover.move(str(src), str(dst_dir / "a.txt"))
    assert res.success
    target = dst_dir / "a.txt"
    entry = UndoEntry(
        action_type="move", file_path=str(src), file_path_after=str(target),
        batch_id="B1", timestamp="t", checksum_after=compute_sha256(target),
    )
    log.append(entry)
    out = log.rollback_batch("B1")
    assert out["rolled_back"] == ["move"]
    assert not target.exists()
    assert src.exists() and src.read_text(encoding="utf-8") == "data"
    assert len(log) == 0


def test_rollback_batch_conflict_aborts_without_mutation(tmp_path):
    # ملفان في دفعة واحدة؛ الأول سليم والثاني عُدّل بعد العملية —
    # يجب ألا يُمس أي ملف ولا حذف السجلات.
    log = UndoLog()
    d1 = tmp_path / "d1"; d1.mkdir()
    d2 = tmp_path / "d2"; d2.mkdir()
    from src.core.safe_mover import SafeMover, compute_sha256
    mover = SafeMover(verify_checksum=True, move_sidecar=False)

    # إجراء 1: move سليم
    s1 = tmp_path / "f1.txt"; s1.write_text("one", encoding="utf-8")
    r1 = mover.move(str(s1), str(d1 / "f1.txt"))
    assert r1.success
    ok = UndoEntry(action_type="move", file_path=str(s1),
                   file_path_after=r1.final_path, batch_id="B1",
                   timestamp="t", checksum_after=compute_sha256(d1 / "f1.txt"))
    log.append(ok)

    # إجراء 2: copy ثم تعديل النسخة — تعارض
    s2 = tmp_path / "f2.txt"; s2.write_text("two", encoding="utf-8")
    res_copy = mover.copy(str(s2), str(d2 / "f2.txt"))
    assert res_copy.success
    conflict = UndoEntry(action_type="copy", file_path=str(s2),
                         file_path_after=res_copy.final_path, batch_id="B1",
                         timestamp="t", checksum_after=compute_sha256(d2 / "f2.txt"))
    log.append(conflict)
    (d2 / "f2.txt").write_text("user-edited!", encoding="utf-8")

    copies_before = (d2 / "f2.txt").read_text(encoding="utf-8")
    with pytest.raises(RuntimeError, match="لم يُعدّل أي ملف"):
        log.rollback_batch("B1")
    # لا تعديل على أي ملف (فحص مبدئي قبل التنفيذ)
    assert (d2 / "f2.txt").read_text(encoding="utf-8") == copies_before
    assert (d1 / "f1.txt").exists()          # لم يتراجع عن الإجراء السليم
    assert not s1.exists()                    # بقي كما هو بعد النقل الأصلي
    assert len(log) == 2                      # السجلات لم تُحذف


def test_modified_copy_file_survives_rollback_attempt(tmp_path):
    log = UndoLog()
    s = tmp_path / "orig.txt"; s.write_text("v1", encoding="utf-8")
    d = tmp_path / "out"; d.mkdir()
    from src.core.safe_mover import SafeMover, compute_sha256
    mover = SafeMover(verify_checksum=True, move_sidecar=False)
    r = mover.copy(str(s), str(d / "orig.txt"))
    assert r.success
    entry = UndoEntry(action_type="copy", file_path=str(s),
                      file_path_after=r.final_path, batch_id="B2",
                      timestamp="t", checksum_after=compute_sha256(d / "orig.txt"))
    log.append(entry)
    (d / "orig.txt").write_text("my later work", encoding="utf-8")
    with pytest.raises(RuntimeError, match="عُدّل الملف"):
        log.rollback_batch("B2")
    assert (d / "orig.txt").read_text(encoding="utf-8") == "my later work"
    assert s.read_text(encoding="utf-8") == "v1"


def test_old_entries_without_batch_id_still_load(tmp_path):
    # سجل قديم بلا batch_id — من JSON مباشرة، توافق خلفي كامل
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
    # التراجع الفردي القديم ما زال يعمل
    e = log.rollback_last()
    assert e is not None and e.action_type == "tag"


def test_empty_and_unknown_batch(tmp_path):
    log = UndoLog()
    with pytest.raises(ValueError):
        log.rollback_batch("")
    with pytest.raises(ValueError):
        log.rollback_batch("NOPE-404");
