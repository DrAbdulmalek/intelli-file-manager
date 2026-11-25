# -*- coding: utf-8 -*-
"""اختبارات FeedbackEngine — الحلقة الكاملة والخصوصية (§9C)

تغطي: accept/reject/correct، تكرار الـfeedback، التعارض، الجلسات
المستقلة، واستبعاد الميتاداتا الحساسة. بيانات اصطناعية فقط.
"""
from __future__ import annotations

import json

import pytest

from src.core.feedback_engine import FeedbackEngine, sanitize_evidence, fingerprint_path
from src.core.preference_engine import PreferenceEngine
from src.core.preference_store import PreferenceStore


@pytest.fixture
def engines(tmp_path):
    store = PreferenceStore(tmp_path / "prefs.json")
    engine = PreferenceEngine(store)
    feedback = FeedbackEngine(engine, tmp_path / "feedback_log.jsonl")
    return engine, feedback


_META = {"name": "scan001.png", "extension": ".png", "category": "مستندات"}


def _capture(feedback, action="correct", corrected="صور", session="s1",
             fp="f1", evidence=None, **kw):
    params = dict(
        user_action=action,
        original_prediction="مستندات",
        session_id=session,
        file_fingerprint=fp,
        corrected_value=corrected,
        evidence=evidence or {"extension": ".png", "mime_type": "image/png"},
    )
    params.update(kw)
    return feedback.capture(**params)


# ─── الأفعال الثلاثة الأساسية ───────────────────────────────────────────────

def test_correct_creates_pending_candidate_not_applied(engines):
    engine, feedback = engines
    record = _capture(feedback, action="correct")
    assert record["review_status"] == "pending_review"
    assert feedback.category_label(record["candidate"]["destination_category_id"]) == "صور"
    assert record["candidate"]["requires_explicit_confirmation"] is True
    # لم يُطبَّق على المحرك بعد — لا قواعد
    assert engine.list_rules() == []


def test_reject_never_creates_rule(engines):
    engine, feedback = engines
    record = _capture(feedback, action="reject")
    assert record["review_status"] == "dismissed"
    assert record["candidate"] is None
    # بعد التأكيد والتطبيق: الرفض مرفوض صراحةً
    with pytest.raises(ValueError):
        feedback.apply_confirmed(record["feedback_id"], metadata=_META,
                                 original_category="مستندات",
                                 session_id="s1", file_fingerprint="f1")
    assert engine.list_rules() == []


def test_accept_without_rule_is_dismissed(engines):
    engine, feedback = engines
    record = _capture(feedback, action="accept")
    assert record["review_status"] == "dismissed"


def test_full_loop_correct_confirm_apply(engines):
    engine, feedback = engines
    record = _capture(feedback, action="correct", session="s1", fp="f1",
                      evidence={"extension": ".png", "mime_type": "image/png",
                                "size_bucket": "small"})
    feedback.confirm(record["feedback_id"])
    assert feedback.get_feedback(record["feedback_id"])["review_status"] == "confirmed"
    result = feedback.apply_confirmed(
        record["feedback_id"], metadata=_META, original_category="مستندات",
        session_id="s1", file_fingerprint="f1")
    assert result["review_status"] == "applied"
    assert result["engine_result"]["created"] is True
    rules = engine.list_rules()
    assert len(rules) == 1
    assert rules[0]["destination"]["category"] == "صور"
    assert rules[0]["source"]["feedback_ids"] == [record["feedback_id"]]
    # سجل Feedback يحتفظ بمعرفات الفئات فقط؛ أسماء العرض في PreferenceStore المحلي.
    public_record = feedback.get_feedback(record["feedback_id"])
    assert public_record["review_status"] == "applied"
    assert "original_prediction" not in public_record
    assert "corrected_value" not in public_record
    log_text = feedback.log_path.read_text(encoding="utf-8")
    assert "مستندات" not in log_text and "صور" not in log_text
    assert "category_catalog" in engine.store.path.read_text(encoding="utf-8")


def test_apply_requires_explicit_confirmation(engines):
    engine, feedback = engines
    record = _capture(feedback, action="correct")
    with pytest.raises(ValueError):
        feedback.apply_confirmed(record["feedback_id"], metadata=_META,
                                 original_category="مستندات",
                                 session_id="s1", file_fingerprint="f1")
    assert engine.list_rules() == []


def test_temp_override_never_becomes_rule(engines):
    engine, feedback = engines
    record = _capture(feedback, action="temp_override")
    assert record["review_status"] == "dismissed"
    with pytest.raises(ValueError):
        feedback.confirm(record["feedback_id"])
    assert engine.list_rules() == []


def test_unknown_action_refused(engines):
    engine, feedback = engines
    with pytest.raises(ValueError):
        feedback.capture(user_action="purge_everything",
                         original_prediction="مستندات", session_id="s",
                         file_fingerprint="f")


# ─── التكرار والتعارض والاستقلالية ─────────────────────────────────────────

def test_duplicate_feedback_detected(engines):
    engine, feedback = engines
    first = _capture(feedback, session="s1", fp="f1")
    second = _capture(feedback, session="s1", fp="f1")
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    # التكرار لا يمنع السجل (أثر تدقيقي كامل) لكنه معلَّم
    assert len(feedback.list_feedback()) == 2


def test_duplicate_does_not_raise_independence(engines):
    """تكرار نفس التصحيح على نفس الملف/الجلسة: التكرار noop كاملًا —
    لا مجموع تأكيدات ولا استقلالية ترتفع (تكرار غير مستقل = لا ثقة)."""
    engine, feedback = engines
    recs = [_capture(feedback, session="s1", fp="f1") for _ in range(3)]
    feedback.confirm(recs[0]["feedback_id"])
    feedback.apply_confirmed(recs[0]["feedback_id"], metadata=_META,
                             original_category="مستندات",
                             session_id="s1", file_fingerprint="f1")
    for rec in recs[1:]:
        feedback.confirm(rec["feedback_id"])
        # نفس الملف — أصله الآن "صور" بعد أول تصحيح، فالتصحيح نفسه noop
        result = feedback.apply_confirmed(rec["feedback_id"], metadata=_META,
                                          original_category="صور",
                                          session_id="s1", file_fingerprint="f1")
        assert result["engine_result"]["noop"] is True
    rule = engine.list_rules()[0]
    assert rule["confidence"]["total_confirmations"] == 1
    assert rule["confidence"]["independent_sessions"] == 1
    assert rule["status"] == "provisional"
    # وفي السجل: التكراران معلّمان duplicate
    assert feedback.get_feedback(recs[1]["feedback_id"])["duplicate"] is True


def test_independent_sessions_raise_independence(engines):
    engine, feedback = engines
    sessions = [("s1", "f1"), ("s2", "f2"), ("s3", "f3")]
    for s, f in sessions:
        rec = _capture(feedback, session=s, fp=f, evidence={"extension": ".png"})
        feedback.confirm(rec["feedback_id"])
        feedback.apply_confirmed(rec["feedback_id"], metadata=_META,
                                 original_category="مستندات",
                                 session_id=s, file_fingerprint=f)
    rule = engine.list_rules()[0]
    assert rule["confidence"]["total_confirmations"] == 3
    assert rule["confidence"]["independent_sessions"] == 3
    assert rule["status"] == "stable"


def test_conflicting_feedback_flagged(engines):
    """نفس المفتاح بوجهة مختلفة عن قاعدة قائمة → راية تعارض في المرشح."""
    engine, feedback = engines
    # قاعدة قائمة: .png → صور
    rec1 = _capture(feedback, corrected="صور", session="s1", fp="f1")
    feedback.confirm(rec1["feedback_id"])
    feedback.apply_confirmed(rec1["feedback_id"], metadata=_META,
                             original_category="مستندات",
                             session_id="s1", file_fingerprint="f1")
    # feedback جديد: .png → أرشيفات (تعارض)
    rec2 = _capture(feedback, corrected="أرشيفات", session="s2", fp="f2")
    assert rec2["candidate"]["conflict_with_existing"] is True
    # والقاعدة الأولى علمت بالتعارض بعد التطبيق
    rule = engine.list_rules()[0]
    assert rule["destination"]["category"] == "صور"


# ─── الخصوصية ───────────────────────────────────────────────────────────────

def test_sensitive_evidence_keys_stripped(engines):
    engine, feedback = engines
    record = _capture(
        feedback,
        evidence={
            "extension": ".png",
            "path": "/home/user/medical/mri_scan001.png",   # حساس — يُسقط
            "name": "mri_scan001.png",                       # حساس — يُسقط
            "content": "patient report text...",             # حساس — يُسقط
            "size_bucket": "small",
        })
    stored_evidence = feedback.get_feedback(record["feedback_id"])["evidence"]
    assert stored_evidence == {"extension": ".png", "size_bucket": "small"}
    # ولا شيء حساس في ملف السجل على القرص
    log_text = feedback.log_path.read_text(encoding="utf-8")
    assert "mri_scan001" not in log_text
    assert "/home/user" not in log_text
    assert "patient report" not in log_text


def test_sanitize_evidence_unit():
    clean = sanitize_evidence({
        "extension": "PNG", "mime_type": "image/png", "size_bucket": 2,
        "file_path": "/secret/x", "text": "حساس", "preview": b"raw",
    })
    assert clean == {"extension": ".png", "mime_type": "image/png", "size_bucket": 2}


def test_fingerprint_path_is_not_reversible_string():
    fp = fingerprint_path("/home/user/private/report.pdf")
    assert isinstance(fp, str) and len(fp) == 64
    assert "/home" not in fp and "report" not in fp


# ─── سجل منفصل وappend-only ────────────────────────────────────────────────

def test_feedback_log_separate_from_preferences_file(engines, tmp_path):
    engine, feedback = engines
    _capture(feedback, action="correct")
    assert feedback.log_path.name == "feedback_log.jsonl"
    assert feedback.log_path != engine.store.path
    # سجل التفضيلات لا يحتوي أسطر feedback
    assert "feedback" not in engine.store.path.read_text(encoding="utf-8") \
        if engine.store.path.exists() else True


def test_feedback_survives_engine_restart(engines, tmp_path):
    engine, feedback = engines
    record = _capture(feedback, action="correct")
    # محرك جديد على نفس الملفات — الفهرسة من السجل تعمل
    reopened = FeedbackEngine(engine, tmp_path / "feedback_log.jsonl")
    assert reopened.get_feedback(record["feedback_id"])["review_status"] == "pending_review"


def test_review_update_lines_are_append_only(engines, tmp_path):
    engine, feedback = engines
    record = _capture(feedback, action="correct")
    before = feedback.log_path.read_text(encoding="utf-8").splitlines()
    feedback.confirm(record["feedback_id"])
    after = feedback.log_path.read_text(encoding="utf-8").splitlines()
    # السطر الأصلي لم يُعد كتابته — أُلحق سطر تحديث فقط
    assert after[:len(before)] == before
    assert len(after) == len(before) + 1
    last = json.loads(after[-1])
    assert last["type"] == "review_update"

def test_category_labels_are_opaque_in_feedback_log(engines):
    engine, feedback = engines
    record = _capture(feedback, corrected="صور")
    raw = feedback.log_path.read_text(encoding="utf-8")
    assert "مستندات" not in raw
    assert "صور" not in raw
    assert record["original_category_id"]
    assert record["corrected_category_id"]
    assert feedback.category_label(record["corrected_category_id"]) == "صور"
    assert "صور" in engine.store.path.read_text(encoding="utf-8")


def test_custom_categories_are_registered_in_existing_preference_store(tmp_path):
    store = PreferenceStore(tmp_path / "prefs.json")
    engine = PreferenceEngine(store)
    feedback = FeedbackEngine(
        engine, tmp_path / "feedback.jsonl",
        allowed_categories=["مستندات", "صور العائلة"],
    )
    record = _capture(feedback, corrected="صور العائلة")
    assert feedback.category_label(record["corrected_category_id"]) == "صور العائلة"
    assert "صور العائلة" not in feedback.log_path.read_text(encoding="utf-8")
    assert "صور العائلة" in store.path.read_text(encoding="utf-8")
    assert not (tmp_path / "category_store.json").exists()


def test_unknown_category_rejected_without_feedback_write(engines):
    engine, feedback = engines
    with pytest.raises(ValueError, match="category_not_in_configured_catalog"):
        _capture(feedback, corrected="اسم شخص حساس")
    assert not feedback.log_path.exists()
    assert engine.list_rules() == []


def test_name_only_evidence_cannot_create_learning_candidate(engines):
    engine, feedback = engines
    record = _capture(
        feedback,
        evidence={"name": "patient-report.pdf", "path": "/private/patient-report.pdf"},
    )
    assert record["review_status"] == "dismissed"
    assert record["candidate"] is None
    raw = feedback.log_path.read_text(encoding="utf-8")
    assert "patient-report" not in raw
    assert "/private" not in raw


def test_dismiss_pending_feedback_prevents_application(engines):
    engine, feedback = engines
    record = _capture(feedback)
    dismissed = feedback.dismiss(record["feedback_id"])
    assert dismissed["review_status"] == "dismissed"
    with pytest.raises(ValueError, match="explicit_confirmation_required"):
        feedback.apply_confirmed(record["feedback_id"])
    assert engine.list_rules() == []


def test_confirmed_feedback_can_apply_after_restart(engines):
    engine, feedback = engines
    record = _capture(feedback, evidence={"extension": ".png"})
    feedback.confirm(record["feedback_id"])
    reopened = FeedbackEngine(engine, feedback.log_path)
    result = reopened.apply_confirmed(record["feedback_id"])
    assert result["review_status"] == "applied"
    assert engine.list_rules()[0]["destination"]["category"] == "صور"

def test_category_catalog_rejects_paths_and_email(tmp_path):
    from src.core.preference_store import InvalidRuleError

    store = PreferenceStore(tmp_path / "prefs.json")
    with pytest.raises(InvalidRuleError, match="category_label_invalid"):
        store.register_category("/home/user/private")
    with pytest.raises(InvalidRuleError, match="category_label_invalid"):
        store.register_category("person@example.invalid")
    assert not store.path.exists()


def test_feedback_rejects_path_like_session_and_fingerprint(engines):
    engine, feedback = engines
    with pytest.raises(ValueError, match="source_session_must_be_opaque_token"):
        feedback.capture(
            user_action="correct", original_prediction="مستندات",
            corrected_value="صور", session_id="/home/user", file_fingerprint="fp1",
            evidence={"extension": ".png"},
        )
    with pytest.raises(ValueError, match="file_fingerprint_must_be_opaque_token"):
        feedback.capture(
            user_action="correct", original_prediction="مستندات",
            corrected_value="صور", session_id="s1",
            file_fingerprint="/private/report.pdf", evidence={"extension": ".pdf"},
        )
    assert not feedback.log_path.exists()
    assert engine.list_rules() == []
