# -*- coding: utf-8 -*-
"""اختبارات F18: سجلات الإخفاق no-op في rollback_last/all/n — لا عكس لما لم يُنفّذ.

المراجعة المستقلة (جولة التحقق على HEAD 4c084415): _rollback_entry كان يحاول
العكس حتى لسجلات success=False (تحذير فقط ثم يكمل)، فيتوقف rollback_all عند
آخر سجل (فشل MOVE بلا file_path_after يرفع ValueError) ولا يصل للناجحين قبله،
وسجل إخفاق TAG يعيد كتابة sidecar لملف قد لا يكون موجوداً. الاتساق المطلوب
مع دلالات rollback_batch (F13: skipped_failed).

بيانات اصطناعية في tmp_path فقط.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.rule_engine import _sidecar_path
from src.core.rule_schemas import UndoEntry, ActionType
from src.core.safe_mover import SafeMover
from src.core.undo_log import UndoLog


@pytest.fixture()
def log():
    return UndoLog()


def test_f18_rollback_all_passes_through_failed_records(tmp_path, log):
    """rollback_all يستهلك سجلات الإخفاق بلا خطأ ويكمل عكس الناجحين قبلها —
    قبل F18 كان يتوقف عند سجل الإخفاق الأخير ولا يصل للناجح."""
    d = tmp_path / "d"; d.mkdir()
    f = tmp_path / "f.txt"; f.write_text("body", encoding="utf-8")
    mover = SafeMover(verify_checksum=True, move_sidecar=False)
    res = mover.move(str(f), str(d / "f.txt"))
    assert res.success
    dest = Path(res.final_path)
    # الترتيب الزمني: نقل ناجح ثم سجل إخفاق TAG ثم سجل إخفاق MOVE (الأحدث آخراً)
    log.append(UndoEntry(
        action_type=ActionType.MOVE.value, file_path=str(f),
        file_path_after=str(dest), rule_name="t", timestamp="t",
        batch_id="B18", success=True,
    ))
    log.append(UndoEntry(
        action_type=ActionType.TAG.value, file_path=str(tmp_path / "gone.txt"),
        rule_name="t", timestamp="t", batch_id="B18", success=False,
        error_message="الملف المصدر غير موجود",
    ))
    log.append(UndoEntry(
        action_type=ActionType.MOVE.value, file_path=str(tmp_path / "ghost.txt"),
        file_path_after=None, rule_name="t", timestamp="t",
        batch_id="B18", success=False,
        error_message="الملف المصدر غير موجود",
    ))
    rolled = log.rollback_all()
    # العكس اكتمل: سجل الإخفاق استُهلك بلا استثناء، والنقل الناجح عُكس فعلاً
    assert len(log) == 0
    assert f.exists() and not dest.exists()
    assert f.read_text(encoding="utf-8") == "body"
    assert rolled[-1].action_type == ActionType.MOVE.value
    assert rolled[-1].rollback_error_message == ""
    # سجلات الإخفاق نفسها: success يبقى وصفاً للإجراء الأصلي (فاشل)
    assert rolled[0].success is False and rolled[1].success is False


def test_f18_failed_tag_record_does_not_create_sidecar(tmp_path, log):
    """سجل إخفاق TAG: لا يُنشأ ولا يُعاد كتابة sidecar لملف غير موجود."""
    ghost = tmp_path / "no-such-file.txt"
    log.append(UndoEntry(
        action_type=ActionType.TAG.value, file_path=str(ghost),
        rule_name="t", timestamp="t", success=False,
        error_message="الملف المصدر غير موجود",
    ))
    returned = log.rollback_last()
    assert returned is not None
    assert returned.success is False  # وصف الإجراء الأصلي لم يُمس
    assert returned.rollback_error_message == ""
    # قبل F18: _rollback_tag كان يكتب sidecar جديداً لملف غير موجود
    assert not _sidecar_path(str(ghost)).exists()
    assert len(log) == 0  # استُهلك — لا شيء لعكسه، والأثر في ActionLog


def test_f18_rollback_last_on_failed_move_record_no_exception(tmp_path, log):
    """فشل MOVE بلا file_path_after: لا استثناء، لا توقف — استهلاك صامت."""
    log.append(UndoEntry(
        action_type=ActionType.MOVE.value, file_path=str(tmp_path / "x.txt"),
        file_path_after=None, rule_name="t", timestamp="t",
        success=False, error_message="الملف المصدر غير موجود",
    ))
    returned = log.rollback_last()
    assert returned is not None
    assert returned.file_path_after is None
    assert returned.rollback_error_message == ""
    assert len(log) == 0


def test_f18_rollback_n_skips_failed_and_reverses_successful(tmp_path, log):
    """rollback_n(n=2): سجل إخفاق + إجراء ناجح — الناجح يُعكس والفاشل يُستهلك."""
    d = tmp_path / "d"; d.mkdir()
    f = tmp_path / "f.txt"; f.write_text("n-body", encoding="utf-8")
    mover = SafeMover(verify_checksum=True, move_sidecar=False)
    res = mover.move(str(f), str(d / "f.txt"))
    assert res.success
    dest = Path(res.final_path)
    log.append(UndoEntry(
        action_type=ActionType.MOVE.value, file_path=str(f),
        file_path_after=str(dest), rule_name="t", timestamp="t",
        success=True,
    ))
    log.append(UndoEntry(
        action_type=ActionType.SET_CATEGORY.value, file_path=str(tmp_path / "ghost.txt"),
        rule_name="t", timestamp="t", success=False,
        error_message="الملف المصدر غير موجود",
    ))
    rolled = log.rollback_n(2)
    assert len(rolled) == 2 and len(log) == 0
    assert f.exists() and not dest.exists()
    assert rolled[0].success is False  # الإخفاق: استهلاك بلا عكس
    assert rolled[1].action_type == ActionType.MOVE.value
