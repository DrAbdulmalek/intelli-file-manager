from src.core.preference_store import PreferenceStore
from src.core.feedback_store import FeedbackStore


def test_preference_observation_is_pending_and_path_is_not_persisted(tmp_path):
    db = tmp_path / "preferences.sqlite"
    store = PreferenceStore(db)
    result = store.record_observation(
        "folder", "/private/patient-records", "medical", "review-001"
    )
    assert result["state"] == "pending"
    assert result["active_rule_unchanged"] is True
    raw = db.read_bytes()
    assert b"patient-records" not in raw


def test_preference_requires_independent_evidence_and_explicit_approval(tmp_path):
    store = PreferenceStore(tmp_path / "preferences.sqlite")
    first = store.record_observation("extension", ".pdf", "documents", "event-1")
    assert store.approve_candidate(first["candidate_id"], min_evidence=2)["approved"] is False
    store.record_observation("extension", ".pdf", "documents", "event-2")
    approved = store.approve_candidate(first["candidate_id"], min_evidence=2)
    assert approved["approved"] is True
    assert store.list_rules()[0]["category"] == "documents"


def test_conflicting_preference_does_not_replace_active_rule(tmp_path):
    store = PreferenceStore(tmp_path / "preferences.sqlite")
    first = store.record_observation("global", "user", "documents", "event-1")
    store.record_observation("global", "user", "documents", "event-2")
    assert store.approve_candidate(first["candidate_id"])["approved"] is True
    conflict = store.record_observation("global", "user", "archive", "event-3")
    assert conflict["state"] == "conflict"
    assert store.list_rules()[0]["category"] == "documents"


def test_feedback_stores_digest_not_raw_details(tmp_path):
    db = tmp_path / "feedback.sqlite"
    store = FeedbackStore(db)
    event_id = store.record(
        component="classifier",
        event_type="misclassification",
        severity="warning",
        evidence_status="partially_proven",
        expected_code="medical",
        observed_code="documents",
        local_details="sensitive local text must not be stored",
    )
    assert event_id > 0
    raw = db.read_bytes()
    assert b"sensitive local text" not in raw
    assert store.list_events()[0]["details_sha256"]


def test_feedback_rejects_free_form_sensitive_fields(tmp_path):
    store = FeedbackStore(tmp_path / "feedback.sqlite")
    try:
        store.record(
            component="classifier",
            event_type="error",
            severity="error",
            evidence_status="unproven",
            expected_code="patient name",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("free-form content should be rejected")
