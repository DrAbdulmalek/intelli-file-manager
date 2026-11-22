# -*- coding: utf-8 -*-
"""اختبارات F10: دقة تعويض COPY — لا استرجاع من مصدر معدّل.

السيناريو الإلزامي (المراجعة المستقلة F10):
  1. إنشاء نسخة COPY.
  2. تعديل المصدر بعد النسخ.
  3. بدء rollback.
  4. حقن فشل لاحق.
  5. التعويض يعيد النسخة الأصلية تماماً — لا النسخة المعدلة من المصدر.

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


def test_f10_compensation_restores_original_copy_not_modified_source(tmp_path, log, monkeypatch):
    """السيناريو الإلزامي كامل: نسخ → تعديل المصدر → rollback → فشل لاحق →
    التعويض يعيد محتوى النسخة الأصلي (لا محتوى المصدر المعدل)."""
    d_copy = tmp_path / "dc"; d_copy.mkdir()
    d_move = tmp_path / "dm"; d_move.mkdir()
    f_copy = tmp_path / "c.txt"; f_copy.write_text("original-copy-content", encoding="utf-8")
    f_move = tmp_path / "m.txt"; f_move.write_text("move-content", encoding="utf-8")
    mover = SafeMover(verify_checksum=True, move_sidecar=False)
    # الدفعة: نقل ثم نسخ — العكس بالترتيب العكسي: النسخ أولاً ثم النقل
    moved = _move_op(mover, log, f_move, d_move, "B10")
    copied = _copy_op(mover, log, f_copy, d_copy, "B10")
    original_copy_checksum = compute_sha256(copied)
    # (2) تعديل المصدر بعد النسخ — لو عوّض من المصدر لكانت النتيجة خاطئة
    f_copy.write_text("SOURCE-MODIFIED-AFTER-COPY", encoding="utf-8")
    # (4) حقن فشل في التراجع عن النقل (يأتي بعد النسخ في الترتيب العكسي)
    def inject(self, entry):
        raise RuntimeError("حقن فشل لاحق")
    monkeypatch.setattr(UndoLog, "_rollback_move", inject)
    with pytest.raises(RuntimeError, match="استرداد تعويضي"):
        log.rollback_batch("B10")
    monkeypatch.undo()
    # (5) التعويض أعاد النسخة الأصلية تماماً — لا محتوى المصدر المعدل
    assert copied.exists()
    assert copied.read_text(encoding="utf-8") == "original-copy-content"
    assert compute_sha256(copied) == original_copy_checksum
    assert "SOURCE-MODIFIED" not in copied.read_text(encoding="utf-8")
    # النسخة الاحتياطية نُظفت بعد استعادة مُتحققة
    assert list(d_copy.glob("*.ifm_undo_stage_*")) == []
    # السجلات كاملة
    assert len(log) == 2
    # إعادة المحاولة بعد رفع السبب تكمل الدفعة كاملة
    out = log.rollback_batch("B10")
    assert sorted(out["rolled_back"]) == ["copy", "move"]
    assert len(log) == 0


def test_f10_compensation_from_matching_source_allowed(tmp_path, log):
    """بلا staging لكن المصدر مُثبت التطابق بالبصمة → التعويض منه صحيح
    (المحتوى المُثبت مطابق النسخة الأصلية)."""
    d = tmp_path / "d"; d.mkdir()
    s = tmp_path / "s.txt"; s.write_text("stable-content", encoding="utf-8")
    mover = SafeMover(verify_checksum=True, move_sidecar=False)
    copied = _copy_op(mover, log, s, d, "B10X")
    copied.unlink()
    log._compensate_copy(log.entries[0])
    assert copied.exists()
    assert copied.read_text(encoding="utf-8") == "stable-content"


def test_f10_compensation_fails_closed_when_source_modified_no_staging(tmp_path, log):
    """بلا staging ومصدر معدّل → fail-closed: لا نسخة بمحتوى خاطئ أبداً."""
    d = tmp_path / "d"; d.mkdir()
    s = tmp_path / "s.txt"; s.write_text("pre-copy-content", encoding="utf-8")
    mover = SafeMover(verify_checksum=True, move_sidecar=False)
    copied = _copy_op(mover, log, s, d, "B10Y")
    original_checksum = compute_sha256(copied)
    copied.unlink()          # محاكاة: التراجع حذف النسخة
    s.write_text("user-edited-source", encoding="utf-8")  # تعديل المصدر
    with pytest.raises(RuntimeError, match="fail-closed.*Recovery"):
        log._compensate_copy(log.entries[0])
    # لا ملف أعيد بمحتوى خاطئ
    assert not copied.exists()


def test_f10_compensation_fails_closed_when_registered_staging_missing(tmp_path, log):
    """staging مسجل لكنه مفقود من القرص → fail-closed (لا معايرة بالمصدر)."""
    d = tmp_path / "d"; d.mkdir()
    s = tmp_path / "s.txt"; s.write_text("content", encoding="utf-8")
    mover = SafeMover(verify_checksum=True, move_sidecar=False)
    copied = _copy_op(mover, log, s, d, "B10Z")
    copied.unlink()
    log._pending_staging[str(copied)] = str(d / ".ghost.ifm_undo_stage_1.part")
    with pytest.raises(RuntimeError, match="staging.*مفقودة.*Recovery"):
        log._compensate_copy(log.entries[0])
    assert not copied.exists()


def test_f10_staging_survives_failed_compensation(tmp_path, log, monkeypatch):
    """فشل التعويض مع وجود staging → staging يبقى على القرص (لا تُضح
    ببيانات المستخدم) والحالة قابلة للاستكمال."""
    d = tmp_path / "d"; d.mkdir()
    s = tmp_path / "s.txt"; s.write_text("survivable-content", encoding="utf-8")
    mover = SafeMover(verify_checksum=True, move_sidecar=False)
    copied = _copy_op(mover, log, s, d, "B10W")
    # تراجع ناجح ينشئ staging ويحذف النسخة
    entry = log.entries[0]
    stage = log._create_staging_backup(entry, copied)
    copied.unlink()
    # حقن فشل الاستعادة
    def fake_copy(self, src, dst, **kw):
        from src.core.safe_mover import CopyResult
        return CopyResult(
            source=str(src), destination=str(dst),
            checksum_before="", checksum_after="", success=False,
            error="حقن فشل الاستعادة", sidecar_copied=False, duration_ms=0,
        )
    real_copy = SafeMover.copy
    monkeypatch.setattr(SafeMover, "copy", fake_copy)
    with pytest.raises(RuntimeError, match="Recovery"):
        log._compensate_copy(entry)
    monkeypatch.undo()
    # staging ما زال موجوداً بمحتوى النسخة الأصلي — قابل للاستكمال
    assert stage.exists()
    assert stage.read_text(encoding="utf-8") == "survivable-content"
    # الاستكمال فعلياً: بعد رفع السبب التعويض ينجح من نفس الـstaging
    log._compensate_copy(entry)
    assert copied.read_text(encoding="utf-8") == "survivable-content"
    assert not stage.exists()
