# -*- coding: utf-8 -*-
"""حراسة حقن الفشل الحتمي (F006) — لا يجوز أن يعتمد على بتات الصلاحيات.

خلفية موثقة: اختبار «فشل التراجع لا يُعرض نجاحاً» (F19 متابعة) كان يحقن
الفشل بـ``os.chmod(ro_parent, 0o555)``. تحت الجذر (uid 0) يتجاوز POSIX
بتات الصلاحيات، فينجح التراجع فعلاً ويَسقط الاختبار رغم سلامة المنتج —
وهي حالة أي حاوية Docker/devcontainer تعمل بالجذر.

هذه الاختبارات تثبت أن البديل (``tests.fs_failures.blocked_parent``)
يفشل حقاً لأي uid، وأن سلسلة الإبلاغ كاملة (UndoLog → MCP) تُبلّغ الفشل
كفشل، وأن السجل والملف يبقيان سليمين.
"""
import os

import pytest

from src.core.rule_schemas import UndoEntry
from src.core.safe_mover import SafeMover
from src.core.undo_log import UndoLog
from tests.fs_failures import blocked_parent, is_root


def _move_entry(tmp_path, *, name="blocked_parent"):
    """سجل MOVE ناجح الأصل، وجهته الأصلية داخل أبٍ محجوب حتمياً."""
    blocked = blocked_parent(tmp_path, name)
    dest = tmp_path / "file.txt"
    dest.write_text("X", encoding="utf-8")
    return UndoEntry(action_type="move",
                     file_path=str(blocked / "target.txt"),
                     file_path_after=str(dest), success=True), dest


# ─── 1) الآلية نفسها ────────────────────────────────────────────────────────

def test_blocked_parent_is_a_regular_file_not_a_directory(tmp_path):
    p = blocked_parent(tmp_path)
    assert p.exists() and p.is_file() and not p.is_dir()


def test_blocked_parent_refuses_to_clobber_existing_path(tmp_path):
    existing = tmp_path / "blocked_parent"
    existing.write_text("مستخدم", encoding="utf-8")
    with pytest.raises(FileExistsError):
        blocked_parent(tmp_path)
    assert existing.read_text(encoding="utf-8") == "مستخدم"  # لا استبدال


def test_move_into_blocked_parent_fails_for_any_uid(tmp_path):
    """فشل نقل حقيقي من نظام الملفات — لا mock، ولا اعتماد على mode."""
    entry, dest = _move_entry(tmp_path)
    result = SafeMover().move(entry.file_path_after, entry.file_path)
    assert result.success is False
    assert result.error
    assert dest.read_text(encoding="utf-8") == "X"  # المصدر لم يُفقد


@pytest.mark.skipif(not is_root(), reason="يلزم الجذر لإثبات تجاوزه لبتات الصلاحيات")
def test_chmod_injection_is_not_deterministic_under_root(tmp_path):
    """توثيق executable للخطر: 0o555 لا يمنع الجذر من الكتابة.

    لو عاد أحد إلى حقن الفشل بـchmod فسيصير اختبار F19 متذبذباً بحسب uid.
    هذا الاختبار يُبقي الحقيقة مُثبتة بمخرَج لا بتعليق.
    """
    ro = tmp_path / "ro_parent"
    ro.mkdir()
    os.chmod(ro, 0o555)
    try:
        (ro / "probe.txt").write_text("root يتجاوز البتات", encoding="utf-8")
        assert (ro / "probe.txt").exists()  # ← لهذا لا نستخدم chmod للحقن
    finally:
        os.chmod(ro, 0o755)


# ─── 2) عقد UndoLog تحت الفشل الحتمي ────────────────────────────────────────

def test_rollback_failure_preserves_entry_and_user_file(tmp_path):
    entry, dest = _move_entry(tmp_path)
    log = tmp_path / ".ifm_undo.json"
    ul = UndoLog(log)
    ul.append(entry)
    ul.save()

    got = ul.rollback_last()

    assert got.rollback_error_message            # سبب تراجع موثق (F14)
    assert got.requires_recovery is False        # فشل عادي لا التباس قديم
    assert got.success is True                   # نتيجة الأصل لم تُلوث (F9)
    assert len(ul.entries) == 1                  # السجل محفوظ لإعادة المحاولة
    assert len(UndoLog(log).entries) == 1         # وثبات عبر save/load
    assert dest.read_text(encoding="utf-8") == "X"


def test_rollback_all_stops_at_first_real_failure(tmp_path):
    """F15: لا دوران — التوقف عند أول فشل تراجع حقيقي، والسجلات تبقى.

    الترتيب LIFO: السجل المحجوب هو الأخير فيُحاول أولاً ويفشل، فيتوقف
    rollback_all فوراً ولا يمس السجل الذي قبله (لا استهلاك ولا تعديل).
    """
    log = tmp_path / ".ifm_undo.json"
    ul = UndoLog(log)
    ok_dest = tmp_path / "ok.txt"
    ok_dest.write_text("Y", encoding="utf-8")
    orig_dir = tmp_path / "orig"
    orig_dir.mkdir()
    ul.append(UndoEntry(action_type="move",
                        file_path=str(orig_dir / "ok.txt"),
                        file_path_after=str(ok_dest), success=True))
    blocked_entry, _ = _move_entry(tmp_path)
    ul.append(blocked_entry)
    ul.save()

    rolled = ul.rollback_all()

    assert len(rolled) == 1                      # توقف عند الفاشل
    assert rolled[0].rollback_error_message
    assert len(ul.entries) == 2                  # الفاشل محفوظ + ما قبله لم يُستهلك
    assert not (orig_dir / "ok.txt").exists()     # لم يُحاول عكس السجل السابق
    assert ok_dest.read_text(encoding="utf-8") == "Y"


def test_mcp_undo_last_reports_failure_not_success(tmp_path):
    """سطح MCP: الفشل لا يُعرض نجاحاً، مع سبب التراجع لا سبب الأصل."""
    from src.mcp_server.feedback import FeedbackStore
    from src.mcp_server.server import IntelliFileMcpServer

    server = IntelliFileMcpServer(store=FeedbackStore(tmp_path / "prefs.db"))
    entry, dest = _move_entry(tmp_path)
    log = tmp_path / ".ifm_undo.json"
    ul = UndoLog(log)
    ul.append(entry)
    ul.save()

    resp = server.handle_request({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "undo_last",
                   "arguments": {"undo_log_path": str(log)}},
    })
    got = resp["result"]["structuredContent"]

    assert got["success"] is False
    assert got["recovery_required"] is False
    assert "فشل التراجع" in got["error"]
    assert resp["result"].get("isError") is True
    assert dest.read_text(encoding="utf-8") == "X"
