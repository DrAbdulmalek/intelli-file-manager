# -*- coding: utf-8 -*-
"""اختبارات F9: فشل داخل الإجراء متعدد الخطوات — تعويض داخلي + Recovery.

المطلوب من المراجعة المستقلة F9:
  - نجاح نقل الملف وفشل نقل sidecar → تعويض داخلي (الملف يعود للوجهة)
  - فشل نقل الملف قبل أي تغيير → لا تغيير إطلاقاً
  - نجاح حذف نسخة COPY وفشل معالجة sidecar → النسخة تعود من staging
  - فشل التعويض نفسه → حالة موثقة بصدق + النسخة الاحتياطية محفوظة
  - بقاء سجلات التراجع وعدم الادعاء الكاذب باستعادة الحالة

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


def _setup_moved_with_sidecar(tmp_path: Path, content: str = "body-1"):
    """ينقل ملفاً (مع sidecar) من tmp إلى مجلد الوجهة — كما فعلت عملية move ناجحة."""
    orig = tmp_path / "f.txt"
    orig.write_text(content, encoding="utf-8")
    from src.core.rule_engine import _sidecar_path, _save_sidecar_tags
    _save_sidecar_tags(str(orig), ["keep-tag"])
    d = tmp_path / "d"; d.mkdir()
    mover = SafeMover(verify_checksum=True, move_sidecar=True)
    res = mover.move(str(orig), str(d / "f.txt"))
    assert res.success, res.error
    entry = UndoEntry(
        action_type=ActionType.MOVE.value,
        file_path=str(orig), file_path_after=str(d / "f.txt"),
        rule_name="test", timestamp="t", batch_id="BF9",
    )
    return entry, orig, d / "f.txt", _sidecar_path(str(d / "f.txt"))


def test_f9_move_ok_sidecar_move_fails_compensates(tmp_path, log, monkeypatch):
    """الخطوة 1 ناجحة (الملف الأساسي) والخطوة 2 فاشلة (sidecar) →
    تعويض داخلي: الملف الأساسي يعود إلى الوجهة، الحالة Recovery."""
    entry, orig, dest, sidecar = _setup_moved_with_sidecar(tmp_path)
    log.append(entry)
    real_move = SafeMover.move

    def fake_move(self, src, dst, **kw):
        if str(src) == str(sidecar):
            from src.core.safe_mover import MoveResult
            return MoveResult(
                source=str(src), destination=str(dst),
                checksum_before="", checksum_after="", success=False,
                error="حقن فشل نقل sidecar", sidecar_moved=False,
                duration_ms=0,
            )
        return real_move(self, src, dst, **kw)

    monkeypatch.setattr(SafeMover, "move", fake_move)
    with pytest.raises(RuntimeError, match="عُوّض داخل الإجراء.*Recovery"):
        log.rollback_batch("BF9")
    monkeypatch.undo()
    # تعويض داخلي: الملف الأساسي عاد إلى الوجهة (حالة ما بعد الدفعة)
    assert dest.exists()
    assert not orig.exists()
    # الـsidecar ما زال في الوجهة (لم يُحذف ولم يُستبدل)
    assert sidecar.exists()
    # لا حذف أي سجل
    assert len(log) == 1


def test_f9_move_fails_before_any_change(tmp_path, log, monkeypatch):
    """فشل نقل الملف الأساسي في الخطوة الأولى → لا تغيير إطلاقاً."""
    entry, orig, dest, sidecar = _setup_moved_with_sidecar(tmp_path)
    log.append(entry)

    def fake_move(self, src, dst, **kw):
        from src.core.safe_mover import MoveResult
        return MoveResult(
            source=str(src), destination=str(dst),
            checksum_before="", checksum_after="", success=False,
            error="حقن فشل في الخطوة الأولى", sidecar_moved=False,
            duration_ms=0,
        )

    monkeypatch.setattr(SafeMover, "move", fake_move)
    with pytest.raises(RuntimeError, match="فشل التراجع عن النقل"):
        log.rollback_batch("BF9")
    monkeypatch.undo()
    # لا تغيير: كل شيء في مكانه بعد الدفعة
    assert dest.exists() and sidecar.exists() and not orig.exists()
    assert len(log) == 1


def test_f9_copy_deleted_sidecar_unlink_fails_restores(tmp_path, log, monkeypatch):
    """حذف النسخة نجح وفشل حذف الـsidecar → النسخة تعود بمحتواها الأصلي من staging."""
    content = "copy-body-original"
    src = tmp_path / "s.txt"; src.write_text(content, encoding="utf-8")
    from src.core.rule_engine import _sidecar_path, _save_sidecar_tags
    d = tmp_path / "d"; d.mkdir()
    mover = SafeMover(verify_checksum=True, move_sidecar=True)
    res = mover.copy(str(src), str(d / "s.txt"))
    assert res.success
    copied = Path(res.final_path)
    _save_sidecar_tags(str(copied), ["copied-tag"])
    copied_sidecar = _sidecar_path(str(copied))
    assert copied_sidecar.exists()
    log.append(UndoEntry(
        action_type=ActionType.COPY.value, file_path=str(src),
        file_path_after=str(copied), rule_name="test", timestamp="t",
        batch_id="BF9C", checksum_after=compute_sha256(copied),
    ))

    real_unlink = Path.unlink

    def fake_unlink(self, *a, **k):
        if self.name.startswith(".ifm_meta_"):
            raise OSError("حقن فشل حذف sidecar")
        return real_unlink(self, *a, **k)

    monkeypatch.setattr(Path, "unlink", fake_unlink)
    with pytest.raises(RuntimeError, match="أُعيدت النسخة بمحتواها الأصلي.*Recovery"):
        log.rollback_batch("BF9C")
    monkeypatch.undo()
    # تعويض داخلي: النسخة عودة بمحتواها الأصلي المُتحقق
    assert copied.exists()
    assert copied.read_text(encoding="utf-8") == content
    # الـsidecar ما زال موجوداً (لم يُحذف)
    assert copied_sidecar.exists()
    # النسخة الاحتياطية نُظفت بعد استعادة مُتحققة
    stages = list(d.glob("*.ifm_undo_stage_*"))
    assert stages == []
    # لا حذف أي سجل
    assert len(log) == 1


def test_f9_compensation_itself_fails_staging_preserved(tmp_path, log, monkeypatch):
    """فشل التعويض الداخلي نفسه → حالة موثقة بصدق، النسخة الاحتياطية
    (staging) محفوظة على القرص، ولا تدّعية باستعادة الحالة."""
    content = "precious-copy-body"
    src = tmp_path / "s.txt"; src.write_text(content, encoding="utf-8")
    from src.core.rule_engine import _sidecar_path, _save_sidecar_tags
    d = tmp_path / "d"; d.mkdir()
    mover = SafeMover(verify_checksum=True, move_sidecar=True)
    res = mover.copy(str(src), str(d / "s.txt"))
    assert res.success
    copied = Path(res.final_path)
    _save_sidecar_tags(str(copied), ["copied-tag"])
    copied_sidecar = _sidecar_path(str(copied))
    log.append(UndoEntry(
        action_type=ActionType.COPY.value, file_path=str(src),
        file_path_after=str(copied), rule_name="test", timestamp="t",
        batch_id="BF9D", checksum_after=compute_sha256(copied),
    ))

    real_unlink = Path.unlink
    real_copy = SafeMover.copy
    calls = {"copy": 0}

    def fake_unlink(self, *a, **k):
        if self.name.startswith(".ifm_meta_"):
            raise OSError("حقن فشل حذف sidecar")
        return real_unlink(self, *a, **k)

    def fake_copy(self, s, dst, **kw):
        calls["copy"] += 1
        if calls["copy"] == 2:  # الاستعادة (الثانية) فاشلة — الأولى staging ناجحة
            from src.core.safe_mover import CopyResult
            return CopyResult(
                source=str(s), destination=str(dst),
                checksum_before="", checksum_after="", success=False,
                error="حقن فشل التعويض نفسه", sidecar_copied=False,
                duration_ms=0,
            )
        return real_copy(self, s, dst, **kw)

    monkeypatch.setattr(Path, "unlink", fake_unlink)
    monkeypatch.setattr(SafeMover, "copy", fake_copy)
    with pytest.raises(RuntimeError, match="فشل إعادة النسخة من النسخة الاحتياطية.*Recovery"):
        log.rollback_batch("BF9D")
    monkeypatch.undo()
    # التعويض فشل فعلاً: النسخة محذوفة — لكن بيانات المستخدم محفوظة في staging
    assert not copied.exists()
    stages = list(d.glob("*.ifm_undo_stage_*"))
    assert len(stages) == 1
    assert stages[0].read_text(encoding="utf-8") == content
    # السجل كامل ورسالة الفشل لا تدّعي استعادة ناجحة
    assert len(log) == 1


def test_f9_rollback_last_failure_keeps_record_and_reports_honestly(tmp_path, log, monkeypatch):
    """فشل التراجع عبر rollback_last لا يفقد السجل (كان يُحذف قبل F9)
    والرسالة لا تدّعي استعادة الحالة."""
    entry, orig, dest, sidecar = _setup_moved_with_sidecar(tmp_path)
    log.append(entry)

    def fake_move(self, src, dst, **kw):
        if str(src) == str(sidecar):
            from src.core.safe_mover import MoveResult
            return MoveResult(
                source=str(src), destination=str(dst),
                checksum_before="", checksum_after="", success=False,
                error="حقن فشل نقل sidecar", sidecar_moved=False,
                duration_ms=0,
            )
        return real_move(self, src, dst, **kw)

    real_move = SafeMover.move
    monkeypatch.setattr(SafeMover, "move", fake_move)
    returned = log.rollback_last()
    monkeypatch.undo()
    assert returned is not None
    # success يصف نجاح MOVE الأصلي، لا محاولة التراجع الفاشلة.
    assert returned.success is True
    assert "Recovery" in returned.rollback_error_message
    assert returned.error_message == ""
    # F9: السجل بقي ويمكن إعادة المحاولة بعد زوال سبب الفشل.
    assert len(log) == 1
    assert log.entries[0] is returned
    retried = log.rollback_last()
    assert retried is returned
    assert retried.rollback_error_message == ""
    assert len(log) == 0
    assert orig.exists() and not dest.exists()



def test_f9_rollback_all_stops_after_failure_without_spinning(tmp_path, log, monkeypatch):
    """الفشل يبقي السجل؛ rollback_all يجب أن يتوقف بدلاً من الدوران عليه."""
    entry, orig, dest, sidecar = _setup_moved_with_sidecar(tmp_path)
    log.append(entry)

    def fail_move(self, src, dst, **kw):
        from src.core.safe_mover import MoveResult
        return MoveResult(
            source=str(src), destination=str(dst),
            checksum_before="", checksum_after="", success=False,
            error="حقن فشل rollback_all", sidecar_moved=False, duration_ms=0,
        )

    monkeypatch.setattr(SafeMover, "move", fail_move)
    returned = log.rollback_all()
    assert returned == [entry]
    assert len(log) == 1
    assert entry.success is True
    assert "حقن فشل rollback_all" in entry.rollback_error_message


def test_f9_rollback_n_stops_after_failure_and_preserves_record(tmp_path, log, monkeypatch):
    """rollback_n لا يكرر محاولة السجل الفاشل ضمن الاستدعاء نفسه."""
    entry, orig, dest, sidecar = _setup_moved_with_sidecar(tmp_path)
    log.append(entry)

    def fail_move(self, src, dst, **kw):
        from src.core.safe_mover import MoveResult
        return MoveResult(
            source=str(src), destination=str(dst),
            checksum_before="", checksum_after="", success=False,
            error="حقن فشل rollback_n", sidecar_moved=False, duration_ms=0,
        )

    monkeypatch.setattr(SafeMover, "move", fail_move)
    returned = log.rollback_n(5)
    assert returned == [entry]
    assert len(log) == 1
    assert entry.success is True
    assert "حقن فشل rollback_n" in entry.rollback_error_message
