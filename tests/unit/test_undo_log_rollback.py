# -*- coding: utf-8 -*-
"""اختبارات التراجع عبر SafeMover في UndoLog — لا استبدال صامت عند التضارب.

الخلفية: مراجعة DeepSeek الخارجية (2026-11-20) وجدت أن _rollback_move كان يستخدم
shutil.move مباشرة — نفس صنف عيب U من المراجعة المستقلة (استبدال صامت لأي ملف
جديد يحتل المسار الأصلي عند التراجع، ومسار قابل للوصول من واجهة سطح المكتب).
الإصلاح: كل التراجع يمر عبر SafeMover — التضارب يأخذ لاحقة _1، لا استبدال.
"""
import os

from src.core.rule_schemas import ActionType, UndoEntry
from src.core.undo_log import UndoLog


def _make_move_entry(tmp_path, content="ORIGINAL-REPORT"):
    """ينفّذ نقلًا فعليًا ويسجّل UndoEntry له (كما يفعل RuleEngine)."""
    orig = tmp_path / "downloads" / "report.txt"
    orig.parent.mkdir(parents=True, exist_ok=True)
    orig.write_text(content)
    moved = tmp_path / "documents" / "report.txt"
    moved.parent.mkdir(parents=True, exist_ok=True)
    os.rename(orig, moved)
    entry = UndoEntry(
        action_type=ActionType.MOVE.value,
        file_path=str(orig),
        file_path_after=str(moved),
        success=True,
    )
    return orig, moved, entry


def test_rollback_move_returns_to_original_path(tmp_path):
    """التراجع العادي (لا شاغل): الملف يعود لمساره الأصلي بمحتواه."""
    orig, moved, entry = _make_move_entry(tmp_path)
    log = UndoLog()
    log.append(entry)

    rolled = log.rollback_last()

    assert rolled is not None and rolled.success
    assert orig.exists() and orig.read_text() == "ORIGINAL-REPORT"
    assert not moved.exists()


def test_rollback_move_with_occupant_uses_suffix_not_replace(tmp_path):
    """التراجع مع شاغل جديد في المسار الأصلي: الشاغل يبقى سليمًا والمرتد يأخذ لاحقة.

    مع shutil.move القديم كان الشاغل يُستبدل بصمت (فقدان بيانات).
    """
    orig, moved, entry = _make_move_entry(tmp_path)
    log = UndoLog()
    log.append(entry)
    occupant = orig
    occupant.write_text("NEW-OCCUPANT-DATA")

    rolled = log.rollback_last()

    assert rolled is not None and rolled.success
    # الشاغل سليم — لا استبدال صامت
    assert occupant.read_text() == "NEW-OCCUPANT-DATA"
    # الملف المرتد أخذ لاحقة آمنة بمحتواه الأصلي
    rolled_file = tmp_path / "downloads" / "report_1.txt"
    assert rolled_file.exists() and rolled_file.read_text() == "ORIGINAL-REPORT"
    assert not rolled.error_message


def test_rollback_move_via_safe_mover_no_shutil(tmp_path):
    """إغلاق البوابة: لا استيراد ولا استدعاء shutil في undo_log (تعليقات مسموحة)."""
    import re
    from pathlib import Path

    src = (Path(__file__).resolve().parents[2] / "src" / "core" / "undo_log.py").read_text()
    assert not re.search(r"import shutil|shutil\.", src)
