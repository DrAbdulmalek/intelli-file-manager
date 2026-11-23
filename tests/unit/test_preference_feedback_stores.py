from src.core.feedback_store import FeedbackStore


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


def test_feedback_decision_is_explicit_and_auditable(tmp_path):
    store = FeedbackStore(tmp_path / "feedback.sqlite")
    event_id = store.record(
        component="ocr",
        event_type="engine_failure",
        severity="error",
        evidence_status="unproven",
    )
    assert store.list_events()[0]["decision"] == "unreviewed"
    assert store.set_decision(event_id, "reviewed") is True
    assert store.list_events()[0]["decision"] == "reviewed"
