# -*- coding: utf-8 -*-
"""اختبارات F11: إثبات already-rolled-back لـ MOVE بهوية موثوقة.

المراجعة المستقلة F11: وجود ملف في المسار الأصلي لا يكفي دليلاً على
اكتمال التراجع — المطلوب:
  - fail-closed عندما لا تتوفر هوية موثوقة
  - عدم حذف سجل Undo عند غياب الدليل
  - عدم تصنيف ملف بديل على أنه الملف الأصلي
  - اختبارات: ملف أصلي، ملف بديل، ملف مفقود، ملف معدل

بيانات اصطناعية في tmp_path فقط.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.rule_schemas import UndoEntry, ActionType
from src.core.safe_mover import SafeMover, compute_sha256
from src.core.undo_log import UndoLog


@pytest.fixture()
def log():
    return UndoLog()


def _entry(orig, gone_dest, checksum=None, batch="BF11"):
    return UndoEntry(
        action_type=ActionType.MOVE.value, file_path=str(orig),
        file_path_after=str(gone_dest), rule_name="test", timestamp="t",
        batch_id=batch, checksum_after=checksum,
    )


def test_f11_original_file_with_matching_checksum_marked_already(tmp_path, log):
    """الملف الأصلي المُعاد فعلاً: البصمة تطابق → يُصنَّف already-rolled-back."""
    orig = tmp_path / "doc.txt"; orig.write_text("original-doc", encoding="utf-8")
    gone = tmp_path / "elsewhere" / "doc.txt"
    log.append(_entry(orig, gone, checksum=compute_sha256(orig)))
    out = log.rollback_batch("BF11")
    assert out["already_rolled_back"] == ["move"]
    assert len(log) == 1  # لا حذف السجل
    assert orig.read_text(encoding="utf-8") == "original-doc"


def test_f11_substitute_file_not_classified_as_original(tmp_path, log):
    """ملف بديل (محتوى مختلف) في المسار الأصلي → رفض fail-closed،
    لا تصنيف، والسجل محفوظ."""
    orig = tmp_path / "doc.txt"; orig.write_text("A SUBSTITUTE FILE", encoding="utf-8")
    gone = tmp_path / "elsewhere" / "doc.txt"
    log.append(_entry(orig, gone, checksum="0" * 64))  # بصمة سجلية لا تطابق البديل
    with pytest.raises(RuntimeError, match="ملف بديل أو معدّل.*fail-closed"):
        log.rollback_batch("BF11")
    assert len(log) == 1
    assert orig.read_text(encoding="utf-8") == "A SUBSTITUTE FILE"


def test_f11_modified_file_not_classified_as_original(tmp_path, log):
    """ملف معدّل بعد التراجع (نفس الاسم، محتوى تغيّر) → رفض fail-closed."""
    orig = tmp_path / "doc.txt"; orig.write_text("content-after-real-rollback", encoding="utf-8")
    gone = tmp_path / "elsewhere" / "doc.txt"
    log.append(_entry(orig, gone, checksum="b" * 64))
    orig.write_text("user-edited-after-rollback", encoding="utf-8")
    with pytest.raises(RuntimeError, match="fail-closed"):
        log.rollback_batch("BF11")
    assert len(log) == 1
    assert orig.read_text(encoding="utf-8") == "user-edited-after-rollback"


def test_f11_missing_source_and_target_aborts_fail_closed(tmp_path, log):
    """الملف الأصلي والوجهة مفقودان معاً → غياب غير مفسَّر → أُجهض."""
    log.append(_entry(
        tmp_path / "nope.txt", tmp_path / "nowhere" / "nope.txt",
        checksum="c" * 64,
    ))
    with pytest.raises(RuntimeError, match="أُجهض"):
        log.rollback_batch("BF11")
    assert len(log) == 1


def test_f11_legacy_entry_without_checksum_refused(tmp_path, log):
    """سجل قديم بلا checksum_after + ملف في المسار الأصلي → fail-closed:
    لا هوية موثوقة → لا تصنيف already-rolled-back (تغيّر سلوك متعمد —
    المراجعة F11 تمنع التصنيف بلا هوية)."""
    orig = tmp_path / "legacy.txt"; orig.write_text("x", encoding="utf-8")
    gone = tmp_path / "elsewhere" / "legacy.txt"
    log.append(_entry(orig, gone, checksum=None))
    with pytest.raises(RuntimeError, match="بلا هوية موثوقة.*fail-closed"):
        log.rollback_batch("BF11")
    assert len(log) == 1
    assert orig.exists()


def test_f11_e2e_real_move_rollback_then_identity_proof(tmp_path, log):
    """السيناريو الواقعي: نقل فعلي → تراجع فعلي → إعادة تراجع عن الدفعة
    نفسها: الأصل موجود (بصمة الملف المُعاد = checksum_after) والوجهة
    مفقودة → إثبات هوية يصنّف already-rolled-back."""
    d = tmp_path / "d"; d.mkdir()
    f = tmp_path / "f.txt"; f.write_text("e2e-body", encoding="utf-8")
    mover = SafeMover(verify_checksum=True, move_sidecar=False)
    res = mover.move(str(f), str(d / "f.txt"))
    assert res.success
    dest = Path(res.final_path)
    entry = UndoEntry(
        action_type=ActionType.MOVE.value, file_path=str(f),
        file_path_after=str(dest), rule_name="test", timestamp="t",
        batch_id="BF11E", checksum_after=compute_sha256(dest),
    )
    log.append(entry)
    out1 = log.rollback_batch("BF11E")
    assert out1["rolled_back"] == ["move"]
    assert len(log) == 0 and f.exists() and not dest.exists()
    # محاكاة "السجل عاد من جلسة قديمة": نفس السجل بمحتوياته (بصمة الوجهة)
    log.append(UndoEntry(
        action_type=ActionType.MOVE.value, file_path=str(f),
        file_path_after=str(dest), rule_name="test", timestamp="t",
        batch_id="BF11E2", checksum_after=entry.checksum_after,
    ))
    out2 = log.rollback_batch("BF11E2")
    assert out2["already_rolled_back"] == ["move"]
    assert f.read_text(encoding="utf-8") == "e2e-body"



def test_f11_stale_already_rolled_back_marker_is_cleared_on_retry(tmp_path, log):
    """إذا ظهرت الوجهة بعد تصنيف محاولة سابقة، لا تبقى علامة stale وتتجاوز التراجع."""
    orig = tmp_path / "doc.txt"
    orig.write_text("same-content", encoding="utf-8")
    dest = tmp_path / "elsewhere" / "doc.txt"
    entry = _entry(orig, dest, checksum=compute_sha256(orig), batch="BF11-RETRY")
    log.append(entry)

    # المحاولة الأولى: الوجهة مفقودة والأصل مطابق؛ تُعلّم already-rolled-back.
    log._preflight_rollback(entry)
    assert getattr(entry, "_ifm_already_rolled_back", False) is True

    # تغيّرت الحالة قبل إعادة المحاولة: الوجهة أصبحت موجودة بالمحتوى المتوقع.
    dest.parent.mkdir()
    dest.write_text("same-content", encoding="utf-8")
    log._preflight_rollback(entry)
    assert not getattr(entry, "_ifm_already_rolled_back", False)
