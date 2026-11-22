# -*- coding: utf-8 -*-
"""اختبارات F12: المحافظة على الوسوم السابقة — التراجع لا يزيل ما لم تضفه العملية.

المراجعة المستقلة F12: _exec_tag كان يسجل tags_added حتى لو كان الوسم
موجوداً قبل العملية. المطلوب:
  - TAG لوسم موجود مسبقاً ثم rollback: يجب أن يبقى
  - TAG لوسم غير موجود ثم rollback: يجب أن يُزال
  - UNTAG لوسم موجود ثم rollback: يجب أن يعود
  - UNTAG لوسم غير موجود: لا تغيير
  - DELETE_FLAG مع وجود الوسم مسبقاً ثم rollback: لا حذف لبيانات سابقة

كل الاختبارات عبر مسار RuleEngine.execute الحقيقي (لا dataclass مفردة)،
بيانات اصطناعية في tmp_path فقط.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.rule_engine import RuleEngine, _load_sidecar_tags, _save_sidecar_tags
from src.core.rule_schemas import (
    Action, ActionType, DryRunPlan, PlannedAction, Ruleset, UndoEntry,
)
from src.core.undo_log import UndoLog


@pytest.fixture()
def engine():
    return RuleEngine(Ruleset(name="F12"))


def _tag_plan(f: Path, tag: str) -> DryRunPlan:
    plan = DryRunPlan(ruleset_name="F12")
    plan.planned_actions.append(PlannedAction(
        rule_name="r", file_path=str(f), file_name=f.name,
        action=Action(type=ActionType.TAG.value, value=tag),
    ))
    return plan


def _untag_plan(f: Path, tag: str) -> DryRunPlan:
    plan = DryRunPlan(ruleset_name="F12")
    plan.planned_actions.append(PlannedAction(
        rule_name="r", file_path=str(f), file_name=f.name,
        action=Action(type=ActionType.UNTAG.value, value=tag),
    ))
    return plan


def _delete_flag_plan(f: Path) -> DryRunPlan:
    plan = DryRunPlan(ruleset_name="F12")
    plan.planned_actions.append(PlannedAction(
        rule_name="r", file_path=str(f), file_name=f.name,
        action=Action(type=ActionType.DELETE_FLAG.value),
    ))
    return plan


def _execute_and_load(tmp_path, engine, plan, batch="BF12", confirm=False):
    undo_path = tmp_path / "undo.json"
    entries = engine.execute(plan, undo_log_path=undo_path, batch_id=batch,
                             confirm_destructive=confirm)
    log = UndoLog(undo_path)
    return entries, log


def test_f12_tag_preexisting_rollback_keeps_tag(tmp_path, engine):
    """TAG لوسم موجود مسبقاً ثم rollback: الوسم يبقى — العملية لم تضفه."""
    f = tmp_path / "doc.txt"; f.write_text("x", encoding="utf-8")
    _save_sidecar_tags(str(f), ["already-here"])
    entries, log = _execute_and_load(tmp_path, engine, _tag_plan(f, "already-here"))
    # التسجيل يميز: لم يُضف فعلياً
    assert entries[0].tags_added == []
    assert entries[0].tags_already_present == ["already-here"]
    assert _load_sidecar_tags(str(f)) == ["already-here"]
    out = log.rollback_batch("BF12")
    assert out["rolled_back"] == ["tag"]
    # الوسم الموجود مسبقاً لم يُمس بالتراجع
    assert _load_sidecar_tags(str(f)) == ["already-here"]


def test_f12_tag_new_rollback_removes_tag(tmp_path, engine):
    """TAG لوسم غير موجود ثم rollback: الوسم يُزال (أضيفه فعلاً)."""
    f = tmp_path / "doc.txt"; f.write_text("x", encoding="utf-8")
    _save_sidecar_tags(str(f), [])
    entries, log = _execute_and_load(tmp_path, engine, _tag_plan(f, "t-new"))
    assert entries[0].tags_added == ["t-new"]
    assert entries[0].tags_already_present == []
    out = log.rollback_batch("BF12")
    assert _load_sidecar_tags(str(f)) == []


def test_f12_untag_existing_rollback_restores_tag(tmp_path, engine):
    """UNTAG لوسم موجود ثم rollback: الوسم يعود."""
    f = tmp_path / "doc.txt"; f.write_text("x", encoding="utf-8")
    _save_sidecar_tags(str(f), ["keep-me", "other"])
    entries, log = _execute_and_load(tmp_path, engine, _untag_plan(f, "keep-me"))
    assert entries[0].tags_removed == ["keep-me"]
    assert _load_sidecar_tags(str(f)) == ["other"]
    out = log.rollback_batch("BF12")
    assert sorted(_load_sidecar_tags(str(f))) == ["keep-me", "other"]


def test_f12_untag_missing_no_change(tmp_path, engine):
    """UNTAG لوسم غير موجود: لا تغيير إطلاقاً (tags_removed فارغ)."""
    f = tmp_path / "doc.txt"; f.write_text("x", encoding="utf-8")
    _save_sidecar_tags(str(f), ["untouched"])
    entries, log = _execute_and_load(tmp_path, engine, _untag_plan(f, "ghost-tag"))
    assert entries[0].tags_removed == []
    assert _load_sidecar_tags(str(f)) == ["untouched"]
    out = log.rollback_batch("BF12")
    assert out["rolled_back"] == ["untag"]
    assert _load_sidecar_tags(str(f)) == ["untouched"]


def test_f12_delete_flag_preexisting_rollback_preserves_data(tmp_path, engine):
    """DELETE_FLAG مع وجود to_delete مسبقاً ثم rollback: لا حذف لبيانات سابقة."""
    f = tmp_path / "doc.txt"; f.write_text("x", encoding="utf-8")
    _save_sidecar_tags(str(f), ["to_delete", "user-tag"])
    entries, log = _execute_and_load(
        tmp_path, engine, _delete_flag_plan(f),
        batch="BF12D", confirm=True,
    )
    # التسجيل يميز: العملية لم تضف شيئاً
    assert entries[0].tags_added == []
    assert entries[0].tags_already_present == ["to_delete"]
    out = log.rollback_batch("BF12D")
    assert out["rolled_back"] == ["delete_flag"]
    # وسم الحذف السابق ووسم المستخدم كلاهما بقيا — التراجع لم يحذف بيانات سابقة
    assert sorted(_load_sidecar_tags(str(f))) == ["to_delete", "user-tag"]


def test_f12_delete_flag_new_rollback_removes_flag(tmp_path, engine):
    """DELETE_FLAG لوسم غير موجود ثم rollback: يُزال (أضيفه فعلاً) —
    والسجلات القديمة (tags_added=['to_delete'] دائماً) بسلوكها الموثق."""
    f = tmp_path / "doc.txt"; f.write_text("x", encoding="utf-8")
    _save_sidecar_tags(str(f), ["user-tag"])
    entries, log = _execute_and_load(tmp_path, engine, _delete_flag_plan(f), batch="BF12N", confirm=True)
    assert entries[0].tags_added == ["to_delete"]
    out = log.rollback_batch("BF12N")
    assert _load_sidecar_tags(str(f)) == ["user-tag"]
    # التوافق الخلفي: سجل قديم بصيغة ما قبل F12 — يعمل كما كان (حد موثق)
    legacy = UndoEntry(
        action_type=ActionType.DELETE_FLAG.value, file_path=str(f),
        rule_name="legacy", timestamp="t", tags_added=["to_delete"],
    )
    _save_sidecar_tags(str(f), ["to_delete", "user-tag"])
    log.append(legacy)
    log.rollback_last()
    assert sorted(_load_sidecar_tags(str(f))) == ["user-tag"]
