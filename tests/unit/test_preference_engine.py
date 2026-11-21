# -*- coding: utf-8 -*-
"""اختبارات PreferenceEngine — قواعد التعلم والتوازي والتراجع (§9B)

بيانات اصطناعية فقط. تغطي: مطابقة القواعد، أسبقية النطاق، التعارضات
بأولوية متساوية، انتقالات provisional→stable، التأكيدات المستقلة مقابل
المتكررة، disable/enable بحفظ الحالة، delete/revert، شرح الاقتراح،
وno-op prediction.
"""
from __future__ import annotations

import pytest

from src.core.preference_engine import (
    PreferenceEngine,
    Suggestion,
    STABLE_AFTER_INDEPENDENT_SESSIONS,
    SCORE_STABLE,
)
from src.core.preference_store import PreferenceStore, StoreReadOnlyError


@pytest.fixture
def engine(tmp_path) -> PreferenceEngine:
    store = PreferenceStore(tmp_path / "prefs.json")
    return PreferenceEngine(store)


def _meta(extension=".xyz", category="مستندات", name="file1", mime="") -> dict:
    meta = {"name": name, "extension": extension, "category": category}
    if mime:
        meta["mime_type"] = mime
    return meta


def _correct(engine, corrected="صور", session="s1", fp="f1", **kw) -> dict:
    params = dict(
        metadata=_meta(**{k: v for k, v in kw.items() if k in ("extension", "name", "mime")}),
        original_category="مستندات",
        corrected_category=corrected,
        session_id=session,
        file_fingerprint=fp,
    )
    params.update({k: v for k, v in kw.items() if k in ("origin", "feedback_id", "context_directory")})
    return engine.record_correction(**params)


# ─── التعلم والقواعد ────────────────────────────────────────────────────────

def test_correction_creates_provisional_rule(engine):
    result = _correct(engine, session="s1", fp="f1")
    assert result["created"] and result["independent"]
    rules = engine.list_rules()
    assert len(rules) == 1
    rule = rules[0]
    assert rule["status"] == "provisional"
    assert rule["match"] == {"kind": "extension", "value": ".xyz", "case_insensitive": True}
    assert rule["destination"]["category"] == "صور"
    assert rule["confidence"]["independent_sessions"] == 1
    assert rule["source"]["origin"] == "user_correction"


def test_noop_when_no_difference(engine):
    result = engine.record_correction(
        metadata=_meta(), original_category="مستندات",
        corrected_category="مستندات", session_id="s1", file_fingerprint="f1")
    assert result["noop"] is True
    assert engine.list_rules() == []


def test_unlearnable_metadata_refused(engine):
    with pytest.raises(ValueError):
        engine.record_correction(
            metadata={"category": "مستندات"}, original_category="مستندات",
            corrected_category="صور", session_id="s1", file_fingerprint="f1")


def test_unknown_origin_refused(engine):
    with pytest.raises(ValueError):
        _correct(engine, origin="internet")


def test_inactive_engine_blocks_learning(tmp_path):
    store = PreferenceStore(tmp_path / "prefs.json")
    path = tmp_path / "prefs.json"
    path.write_text("{broken", encoding="utf-8")
    engine = PreferenceEngine(store)  # load فاشل داخلياً
    assert engine.active is False
    assert engine.status_report()["active"] is False
    assert "warning" in engine.status_report()
    with pytest.raises(StoreReadOnlyError):
        _correct(engine)


# ─── الاستقلالية والترقية ───────────────────────────────────────────────────

def test_independent_confirmations_promote_to_stable(engine):
    _correct(engine, session="s1", fp="f1")
    _correct(engine, session="s2", fp="f2")
    result = _correct(engine, session="s3", fp="f3")
    assert result["independent_sessions"] == 3
    assert result["promoted"] is True
    rule = engine.list_rules()[0]
    assert rule["status"] == "stable"
    assert rule["confidence"]["score"] == SCORE_STABLE


def test_repeated_same_session_does_not_raise_independence(engine):
    """التكرار غير المستقل (نفس الجلسة/الملف) لا يرفع الثقة."""
    for _ in range(5):
        result = _correct(engine, session="s1", fp="f1")
    assert result["independent"] is False
    rule = engine.list_rules()[0]
    assert rule["confidence"]["total_confirmations"] == 5
    assert rule["confidence"]["independent_sessions"] == 1
    assert rule["status"] == "provisional"


def test_promotion_threshold_is_exact(engine):
    for i in range(STABLE_AFTER_INDEPENDENT_SESSIONS - 1):
        _correct(engine, session=f"s{i}", fp=f"f{i}")
    assert engine.list_rules()[0]["status"] == "provisional"
    _correct(engine, session="sX", fp="fX")
    assert engine.list_rules()[0]["status"] == "stable"


def test_explicit_confirm_rule_counts_and_promotes(engine):
    _correct(engine, session="s1", fp="f1")
    rule_id = engine.list_rules()[0]["rule_id"]
    result = engine.confirm_rule(rule_id, session_id="s2", file_fingerprint="f2")
    assert result["independent_sessions"] == 2
    engine.confirm_rule(rule_id, session_id="s3", file_fingerprint="f3")
    assert engine.get_rule(rule_id)["status"] == "stable"


# ─── التنبؤ والمطابقة ───────────────────────────────────────────────────────

def test_predict_returns_suggestion(engine):
    _correct(engine, corrected="صور")
    suggestion = engine.predict(_meta(category="مستندات"))
    assert isinstance(suggestion, Suggestion)
    assert suggestion.category == "صور"
    assert suggestion.match_kind == "extension"
    assert suggestion.independent_confirmations == 1
    assert suggestion.reason  # سبب مفهوم للعرض


def test_predict_noop_when_suggestion_equals_current(engine):
    """الوجهة تساوي التصنيف الحالي → لا اقتراح (اتساق applied مع suggestion)."""
    _correct(engine, corrected="مستندات")
    assert engine.predict(_meta(category="مستندات")) is None


def test_predict_none_when_no_rules(engine):
    assert engine.predict(_meta()) is None


def test_predict_none_when_engine_inactive(tmp_path):
    (tmp_path / "prefs.json").write_text("{", encoding="utf-8")
    engine = PreferenceEngine(PreferenceStore(tmp_path / "prefs.json"))
    assert engine.predict(_meta()) is None


def test_predict_none_for_disabled_rule(engine):
    _correct(engine, corrected="صور")
    rule_id = engine.list_rules()[0]["rule_id"]
    engine.disable_rule(rule_id)
    assert engine.predict(_meta(category="مستندات")) is None


def test_mime_match(engine):
    engine.record_correction(
        metadata=_meta(extension="", mime="application/x-unknown"),
        original_category="مستندات", corrected_category="أرشيفات",
        session_id="s1", file_fingerprint="f1")
    suggestion = engine.predict(_meta(extension="", mime="application/x-unknown"))
    assert suggestion is not None and suggestion.category == "أرشيفات"
    assert suggestion.match_kind == "mime"


def test_name_contains_match(engine):
    engine.record_correction(
        metadata=_meta(extension="", name="invoice-2026"),
        original_category="مستندات", corrected_category="صور",
        session_id="s1", file_fingerprint="f1")
    assert engine.list_rules()[0]["match"]["kind"] == "name_contains"
    suggestion = engine.predict(_meta(extension="", name="invoice-2026-final"))
    assert suggestion is not None and suggestion.category == "صور"


# ─── أسبقية النطاق ──────────────────────────────────────────────────────────

def test_scope_precedence_file_over_directory_over_global(engine):
    _correct(engine, corrected="صور")  # global
    _correct(engine, corrected="أرشيفات", context_directory="/data/labels",
             session="s2", fp="f2")
    engine.record_correction(
        metadata=_meta(), original_category="مستندات", corrected_category="فيديو",
        session_id="s3", file_fingerprint="FP99")
    rules = engine.list_rules()
    file_rule_id = [r for r in rules if r["destination"]["category"] == "فيديو"][0]["rule_id"]
    # تعديل واحد متسق: scope ملف بقيمة البصمة (mutator واحد يجتاز التحقق)
    engine.store.update_rule(
        file_rule_id,
        lambda r: (r["scope"].__setitem__("kind", "file"),
                   r["scope"].__setitem__("value", "FP99")))
    suggestion = engine.predict(_meta(), current_path="/data/labels",
                                file_fingerprint="FP99")
    assert suggestion.category == "فيديو"  # file يغلب
    suggestion = engine.predict(_meta(), current_path="/data/labels",
                                file_fingerprint="OTHER")
    assert suggestion.category == "أرشيفات"  # directory يغلب على global
    suggestion = engine.predict(_meta(), current_path="/elsewhere",
                                file_fingerprint="OTHER")
    assert suggestion.category == "صور"  # global فقط مطابق


def test_directory_scope_not_applied_outside(engine):
    _correct(engine, corrected="أرشيفات", context_directory="/data/labels",
             session="s1", fp="f1")
    assert engine.predict(_meta(), current_path="/other") is None


# ─── التعارضات وحسم التساوي ────────────────────────────────────────────────

def test_equal_priority_conflict_detected_and_tie_broken(engine):
    """قاعدتان بنفس المفتاح ووجهتين مختلفتين: تعارض مكشوف + حسم حتمي."""
    r1 = _correct(engine, corrected="صور", session="s1", fp="f1")
    r2 = _correct(engine, corrected="فيديو", session="s2", fp="f2")
    assert r2["conflicts"] == [r1["rule_id"]]
    suggestion = engine.predict(_meta())
    ids = sorted([r1["rule_id"], r2["rule_id"]])
    assert suggestion.rule_id == ids[0]  # حسم التساوي: rule_id القاموسي الأصغر
    loser_id = ids[1]
    assert suggestion.conflicts == [loser_id]


def test_more_confirmations_win_tie(engine):
    r1 = _correct(engine, corrected="صور", session="s1", fp="f1")
    r2 = _correct(engine, corrected="فيديو", session="s2", fp="f2")
    engine.confirm_rule(r2["rule_id"], session_id="sX", file_fingerprint="fX")
    suggestion = engine.predict(_meta())
    assert suggestion.category == "فيديو"  # تأكيدات مستقلة أكثر تتفوق على القاموسية
    assert suggestion.rule_id == r2["rule_id"]


# ─── الإدارة والتراجع ───────────────────────────────────────────────────────

def test_disable_preserves_and_enable_restores_status(engine):
    _correct(engine, session="s1", fp="f1")
    _correct(engine, session="s2", fp="f2")
    _correct(engine, session="s3", fp="f3")
    rule_id = engine.list_rules()[0]["rule_id"]
    assert engine.get_rule(rule_id)["status"] == "stable"
    engine.disable_rule(rule_id)
    disabled = engine.get_rule(rule_id)
    assert disabled["status"] == "disabled"
    assert disabled["status_before_disable"] == "stable"
    engine.enable_rule(rule_id)
    assert engine.get_rule(rule_id)["status"] == "stable"  # استعادت الحالة كاملة


def test_enable_returns_provisional_when_it_was_provisional(engine):
    _correct(engine)
    rule_id = engine.list_rules()[0]["rule_id"]
    engine.disable_rule(rule_id)
    engine.enable_rule(rule_id)
    assert engine.get_rule(rule_id)["status"] == "provisional"


def test_delete_is_soft_and_revert_restores(engine):
    _correct(engine)
    rule_id = engine.list_rules()[0]["rule_id"]
    engine.delete_rule(rule_id)
    assert engine.list_rules() == []  # المحذوف يختفي من القوائم
    assert engine.predict(_meta()) is None
    on_disk = engine.get_rule(rule_id)
    assert on_disk["status"] == "deleted"  # محفوظ على القرص
    engine.revert_last_update()
    assert engine.list_rules()[0]["rule_id"] == rule_id  # عاد بعد التراجع
    assert engine.get_rule(rule_id)["status"] == "provisional"


def test_reverted_rules_not_in_lists_but_recoverable(engine):
    """القاعدة المحذوفة تختفي من القوائم؛ التراجع يعيدها ولا يتكرر."""
    _correct(engine)
    rule_id = engine.list_rules()[0]["rule_id"]
    engine.delete_rule(rule_id)
    assert engine.list_rules() == []
    engine.revert_last_update()
    assert len(engine.list_rules()) == 1
    assert engine.list_rules()[0]["rule_id"] == rule_id
    # لا تراجع ثانٍ لنفس الحذف (لا أحد متبقٍ للاستعادة قبل الإنشاء)
    assert engine.revert_last_update() is None


def test_explain_suggestion_full_fields(engine):
    _correct(engine, corrected="صور", session="s1", fp="f1", feedback_id="fb-1")
    suggestion = engine.predict(_meta())
    explanation = engine.explain_suggestion(suggestion)
    assert explanation["category"] == "صور"
    assert explanation["rule_id"] == suggestion.rule_id
    assert explanation["independent_confirmations"] == 1
    assert explanation["confidence_score"] == 0.5
    assert explanation["origin_feedback_ids"] == ["fb-1"]
    assert explanation["note"]  # التنبيه: لا تنفيذ تلقائي
    assert "match" in explanation and "scope" in explanation


def test_no_shell_or_mover_imports_in_engine_module():
    """حاجز معماري: محرك التفضيل لا يستورد أدوات التنفيذ إطلاقًا."""
    import sys
    import src.core.preference_engine as pe
    loaded = [m for m in sys.modules if m in ("src.core.safe_mover", "src.core.file_handler")]
    # إن كانت محمّلة من اختبارات أخرى فليس من استيراد الوحدة نفسها —
    # المهم أن الوحدة لا تستوردها في نصها:
    source = open(pe.__file__, encoding="utf-8").read()
    assert "safe_mover" not in source
    assert "file_handler" not in source
    assert "subprocess" not in source
