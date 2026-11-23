import pytest

from src.core.feedback_store import FeedbackStore


def test_feedback_persists_only_bounded_categorical_metadata(tmp_path):
    db = tmp_path / "feedback.sqlite"
    store = FeedbackStore(db)
    event_id = store.record(
        component="classifier",
        event_type="misclassification",
        severity="warning",
        evidence_status="partially_proven",
        expected_code="medical",
        observed_code="documents",
        reproduction_token="case-001",
    )
    assert event_id > 0
    event = store.list_events()[0]
    assert event["component"] == "classifier"
    assert event["expected_code"] == "medical"
    assert "details_sha256" not in event
    with store._connect() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(feedback_events)")}
    assert "details_sha256" not in columns


def test_feedback_api_rejects_free_form_details_keyword(tmp_path):
    store = FeedbackStore(tmp_path / "feedback.sqlite")
    with pytest.raises(TypeError):
        store.record(
            component="classifier",
            event_type="error",
            severity="error",
            evidence_status="unproven",
            local_details="patient name and document contents",
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("component", "patient name"),
        ("event_type", "/home/user/private/report.pdf"),
        ("expected_code", "patient@example.com"),
        ("observed_code", "free form clinical narrative"),
        ("reproduction_token", "https://example.invalid/private"),
    ],
)
def test_feedback_rejects_free_form_or_path_like_values(tmp_path, field, value):
    store = FeedbackStore(tmp_path / "feedback.sqlite")
    values = {
        "component": "classifier",
        "event_type": "error",
        "severity": "error",
        "evidence_status": "unproven",
    }
    values[field] = value
    with pytest.raises(ValueError):
        store.record(**values)


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


def test_feedback_rejects_unsupported_decision(tmp_path):
    store = FeedbackStore(tmp_path / "feedback.sqlite")
    with pytest.raises(ValueError):
        store.set_decision(1, "auto_learned")
