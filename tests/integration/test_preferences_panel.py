# -*- coding: utf-8 -*-
"""اختبارات لوحة تفضيلات التصنيف (مهمة §7) — PySide6 offscreen

تغطي: عرض حقول الاقتراح الإلزامية، قبول=تأكيد قاعدة بلا أي عملية ملف،
رفض بلا تعلم، إدارة القواعد (تعطيل/تفعيل/حذف)، التراجع عن التعلم،
وحالة المحرك المعطل.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.desktop

# استيراد محمي — libEGL.so.1 قد لا تتوفر (CI/headless): تتخطى بنظافة
try:
    from src.core.feedback_engine import FeedbackEngine
    from src.core.preference_engine import PreferenceEngine
    from src.core.preference_store import PreferenceStore
    from src.desktop.panels.preferences_panel import PreferencesPanel
    _QT_AVAILABLE = True
except ImportError:
    FeedbackEngine = PreferenceEngine = PreferenceStore = PreferencesPanel = None
    _QT_AVAILABLE = False


@pytest.fixture
def engines(tmp_path):
    store = PreferenceStore(tmp_path / "prefs.json")
    engine = PreferenceEngine(store)
    feedback = FeedbackEngine(engine, tmp_path / "feedback.jsonl")
    return engine, feedback


@pytest.fixture
def panel(qapp, engines):
    engine, feedback = engines
    p = PreferencesPanel(engine=engine, feedback=feedback)
    return p


def _learn(engine):
    for i in range(3):
        engine.record_correction(
            metadata={"name": f"p{i}", "extension": ".xyz"},
            original_category="أخرى", corrected_category="صور",
            session_id=f"s{i}", file_fingerprint=f"f{i}")


def _suggestion_payload(engine):
    suggestion = engine.predict({"name": "x", "extension": ".xyz",
                                 "category": "أخرى"})
    return {
        "active": True,
        "original_category": "أخرى",
        "suggested_category": suggestion.category,
        "rule_id": suggestion.rule_id,
        "rule_status": suggestion.rule_status,
        "confidence_score": suggestion.confidence_score,
        "independent_confirmations": suggestion.independent_confirmations,
        "conflicts": [],
        "source": "user_correction",
        "reason": suggestion.reason,
    }


def test_panel_displays_all_required_fields(qapp, panel, engines):
    engine, _ = engines
    _learn(engine)
    panel.set_suggestion(_suggestion_payload(engine))
    assert panel.lbl_original.text() == "أخرى"
    assert panel.lbl_suggested.text() == "صور"
    assert panel.lbl_reason.text()
    assert panel.lbl_confidence.text() == "0.9"
    assert panel.lbl_confirmations.text() == "3"
    assert panel.lbl_rule.text() != "—"
    assert panel.lbl_conflict.text() == "لا"
    assert panel.lbl_source.text() == "user_correction"


def test_accept_confirms_rule_without_any_file_operation(qapp, panel, engines,
                                                        tmp_path):
    engine, _ = engines
    _learn(engine)
    payload = _suggestion_payload(engine)
    panel.set_suggestion(payload)
    watch_dir = tmp_path / "watched"
    watch_dir.mkdir()
    f = watch_dir / "file.xyz"
    f.write_text("synthetic")
    panel.btn_accept.click()
    rule = engine.get_rule(payload["rule_id"])
    assert rule["confidence"]["total_confirmations"] == 4  # تأكيد صريح سُجّل
    assert f.exists()                      # لا عملية ملف
    assert list(watch_dir.iterdir()) == [f]


def test_reject_records_feedback_and_never_learns(qapp, panel, engines, tmp_path):
    engine, feedback = engines
    _learn(engine)
    payload = _suggestion_payload(engine)
    panel.set_suggestion(payload)
    before_rules = len(engine.list_rules())
    panel.btn_reject.click()
    records = feedback.list_feedback()
    assert records and records[0]["user_action"] == "reject"
    assert records[0]["review_status"] == "dismissed"
    assert len(engine.list_rules()) == before_rules  # لا قاعدة جديدة


def test_rules_table_lists_and_disable_enable_delete(qapp, panel, engines):
    engine, _ = engines
    _learn(engine)
    panel.refresh()
    assert panel.rules_table.rowCount() == 1
    rule_id = engine.list_rules()[0]["rule_id"]
    panel.rules_table.selectRow(0)
    panel.btn_disable.click()
    assert engine.get_rule(rule_id)["status"] == "disabled"
    panel.rules_table.selectRow(0)
    panel.btn_enable.click()
    assert engine.get_rule(rule_id)["status"] == "stable"
    panel.rules_table.selectRow(0)
    panel.btn_delete.click()
    assert engine.get_rule(rule_id)["status"] == "deleted"


def test_undo_learning_restores_last_change(qapp, panel, engines):
    engine, _ = engines
    _learn(engine)
    rule_id = engine.list_rules()[0]["rule_id"]
    engine.delete_rule(rule_id)
    panel.refresh()
    assert panel.rules_table.rowCount() == 0  # المحذوف يختفي من الجدول
    panel.btn_undo_learning.click()
    assert engine.get_rule(rule_id)["status"] == "stable"


def test_disabled_engine_shows_no_actions(qapp, tmp_path):
    store = PreferenceStore(tmp_path / "prefs.json")
    broken = tmp_path / "prefs.json"
    broken.write_text("{corrupt", encoding="utf-8")
    engine = PreferenceEngine(store)  # read-only
    panel = PreferencesPanel(engine=engine)
    panel.set_suggestion({"active": False, "original_category": "أخرى"})
    assert not panel.btn_accept.isEnabled()
    assert not panel.btn_reject.isEnabled()
    assert not panel.btn_correct.isEnabled()
