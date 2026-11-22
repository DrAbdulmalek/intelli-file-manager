# -*- coding: utf-8 -*-
"""اختبار تكامل F13: وصول batch_id من البداية للنهاية.

المراجعة المستقلة F13: اختبار تكامل حقيقي (لا dataclass ولا حقول منفردة):

    RuleEngine.execute(batch_id="TEST-BATCH-001")
    → UndoLog (ملف على القرص)
    → ActionLog (ملف على القرص)
    → export_csv (CSV فعلي)

التحقق: القيمة نفسها تصل إلى **جميع** السجلات الناجحة والفاشلة.

بيانات اصطناعية في tmp_path فقط.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from src.core.action_log import ActionLog
from src.core.rule_engine import RuleEngine, _load_sidecar_tags, _save_sidecar_tags
from src.core.rule_schemas import (
    Action, ActionType, DryRunPlan, PlannedAction, Ruleset,
)
from src.core.undo_log import UndoLog

BATCH = "TEST-BATCH-001"


@pytest.fixture()
def workspace(tmp_path):
    """ملفات اصطناعية + خطة إجراءات حقيقية: 6 ناجحة + 1 فاشلة."""
    d_move = tmp_path / "moved"; d_move.mkdir()
    d_copy = tmp_path / "copied"; d_copy.mkdir()

    f_move = tmp_path / "report.txt"; f_move.write_text("report-body", encoding="utf-8")
    f_copy = tmp_path / "photo.jpg"; f_copy.write_text("photo-bytes", encoding="utf-8")
    f_tag = tmp_path / "doc.txt"; f_tag.write_text("doc-body", encoding="utf-8")
    _save_sidecar_tags(str(f_tag), [])
    f_untag = tmp_path / "old.txt"; f_untag.write_text("old-body", encoding="utf-8")
    _save_sidecar_tags(str(f_untag), ["stale"])
    f_cat = tmp_path / "scan.pdf"; f_cat.write_text("scan-body", encoding="utf-8")
    f_flag = tmp_path / "junk.log"; f_junk_flag = f_flag; f_flag.write_text("junk", encoding="utf-8")

    def pa(rule, file_path, action):
        # target_path يُحتسب كما في _build_planned_action (هدف مطلق)
        target_path = None
        if action.type in (ActionType.MOVE.value, ActionType.COPY.value):
            target_path = str(Path(action.target) / Path(file_path).name)
        return PlannedAction(
            rule_name=rule, file_path=str(file_path),
            file_name=Path(file_path).name, action=action,
            target_path=target_path,
        )

    plan = DryRunPlan(ruleset_name="F13")
    plan.planned_actions = [
        pa("r", f_move, Action(type=ActionType.MOVE.value, target=str(d_move))),
        pa("r", f_copy, Action(type=ActionType.COPY.value, target=str(d_copy))),
        pa("r", f_tag, Action(type=ActionType.TAG.value, value="fresh-tag")),
        pa("r", f_untag, Action(type=ActionType.UNTAG.value, value="stale")),
        pa("r", f_cat, Action(type=ActionType.SET_CATEGORY.value, value="scans")),
        pa("r", f_junk_flag, Action(type=ActionType.DELETE_FLAG.value)),
        # الإجراء الفاشل: نقل ملف غير موجود — يُسجل فاشلاً بنفس الدفعة
        pa("r", tmp_path / "ghost-missing.txt",
           Action(type=ActionType.MOVE.value, target=str(d_move))),
    ]
    files = {
        "f_move": f_move, "f_copy": f_copy, "f_tag": f_tag,
        "f_untag": f_untag, "f_cat": f_cat, "f_flag": f_junk_flag,
        "d_move": d_move, "d_copy": d_copy,
    }
    return plan, files


def test_f13_batch_id_reaches_every_record_end_to_end(tmp_path, workspace):
    plan, files = workspace
    undo_path = tmp_path / "undo.json"
    action_log_path = tmp_path / "actions.json"
    csv_path = tmp_path / "actions.csv"

    engine = RuleEngine(Ruleset(name="F13"))
    action_log = ActionLog(action_log_path)

    entries = engine.execute(
        plan,
        undo_log_path=undo_path,
        action_log=action_log,
        batch_id=BATCH,
        confirm_destructive=True,
    )

    # ─── 1) الإجراءات المُرجعة: القيمة نفسها للناجح والفاشل ───────────
    assert len(entries) == 7
    successes = [e for e in entries if e.success]
    failures = [e for e in entries if not e.success]
    assert len(successes) == 6 and len(failures) == 1
    assert all(e.batch_id == BATCH for e in successes)
    assert all(e.batch_id == BATCH for e in failures)
    assert failures[0].action_type == ActionType.MOVE.value
    assert "ghost-missing" in failures[0].file_path

    # ─── 2) UndoLog من القرص: كل السجلات تحمل الدفعة ──────────────────
    log = UndoLog(undo_path)
    assert len(log) == 7
    assert all(e.batch_id == BATCH for e in log.entries)
    saved = json.loads(undo_path.read_text(encoding="utf-8"))
    assert all(e["batch_id"] == BATCH for e in saved["entries"])

    # ─── 3) ActionLog: السجلات المرئية كاملة بالقيمة نفسها ─────────────
    all_actions = action_log.list_entries()
    assert len(all_actions) == 7
    assert all(a.batch_id == BATCH for a in all_actions)
    by_batch = action_log.by_batch(BATCH)
    assert len(by_batch) == 7
    assert len(action_log.by_batch("OTHER-BATCH")) == 0
    # السجل الفاشل وصل ActionLog أيضاً (مسار except في execute)
    assert sum(1 for a in all_actions if not a.success) == 1

    # ─── 4) export_csv: العمود موجود والقيمة نفسها في كل الصفوف ────────
    out = action_log.export_csv(csv_path)
    assert Path(out).exists()
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 7
    assert "batch_id" in rows[0]
    assert all(r["batch_id"] == BATCH for r in rows)
    # الصفوف الفاشلة والناجحة في CSV تحمل القيمة نفسها
    csv_failed = [r for r in rows if r["success"].strip().lower() in ("false", "0", "no")]
    csv_ok = [r for r in rows if r not in csv_failed]
    assert len(csv_ok) == 6 and len(csv_failed) == 1
    assert all(r["batch_id"] == BATCH for r in csv_failed)
    assert all(r["batch_id"] == BATCH for r in csv_ok)


def test_f13_executed_effects_are_real_and_batch_reversible(tmp_path, workspace):
    """الأثر الفعلي على القرص حقيقي (النقل/النسخ/الوسوم نفّذت) — والدفععة
    قابلة للتراجع كاملة عبر batch_id نفسه (دليل وصول نهائي)."""
    plan, files = workspace
    undo_path = tmp_path / "undo.json"
    engine = RuleEngine(Ruleset(name="F13"))
    entries = engine.execute(plan, undo_log_path=undo_path, batch_id=BATCH,
                             confirm_destructive=True)
    # أثر فعلي: النقل والنسخ والوسوم
    assert (files["d_move"] / "report.txt").read_text(encoding="utf-8") == "report-body"
    assert (files["d_copy"] / "photo.jpg").read_text(encoding="utf-8") == "photo-bytes"
    assert _load_sidecar_tags(str(files["f_tag"])) == ["fresh-tag"]
    assert _load_sidecar_tags(str(files["f_untag"])) == []
    assert "to_delete" in _load_sidecar_tags(str(files["f_flag"]))

    # التراجع عن الدفعة كاملة عبر batch_id (السجل الفاشل يُفحص مبدئياً
    # ويُعلَّم already-rolled-back لأنه لم يُنفّذ فعلاً — لا ملف عكسه)
    log = UndoLog(undo_path)
    out = log.rollback_batch(BATCH)
    assert set(out["rolled_back"]) == {
        "move", "copy", "tag", "untag", "set_category", "delete_flag",
    }
    # الأثر عاد: الملفات في أماكنها الأصلية
    assert files["f_move"].read_text(encoding="utf-8") == "report-body"
    assert files["f_copy"].read_text(encoding="utf-8") == "photo-bytes"
    assert _load_sidecar_tags(str(files["f_tag"])) == []
    assert _load_sidecar_tags(str(files["f_untag"])) == ["stale"]
    assert not (files["d_move"] / "report.txt").exists()
    assert not (files["d_copy"] / "photo.jpg").exists()
