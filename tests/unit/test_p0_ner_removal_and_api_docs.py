"""P0: NER أُزيل بحكم PRODUCT_IDENTITY — لا أسلاك ميتة ولا وعود README بلا endpoint."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from src.api import server  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def app():
    return getattr(server, "app", None) or server.create_app()


def test_ner_endpoint_is_gone_not_500(app, monkeypatch):
    monkeypatch.setattr(server, "_API_KEY", "")
    r = TestClient(app, raise_server_exceptions=False).post("/api/ner/extract", json={"text": "x"})
    assert r.status_code == 404


def test_health_does_not_probe_removed_engine(app, monkeypatch):
    monkeypatch.setattr(server, "_API_KEY", "")
    body = TestClient(app, raise_server_exceptions=False).get("/api/health").json()
    assert "ner" not in body["engines"]


def test_no_server_reference_to_missing_medical_ner_module():
    text = (ROOT / "src/api/server.py").read_text(encoding="utf-8")
    assert "medical_ner" not in text and "NerRequest" not in text


def test_every_readme_endpoint_exists_in_the_app(app):
    """README لا يعلن endpoint غير موجود في التطبيق (انحراف توثيق عام).

    ملاحظة: لا يكشف هذا الاختبار وحده وحدة ميتة خلف route موجود (حالة NER)؛ لذلك
    توجد اختبارات صريحة أعلاه.
    """
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"^\| \d+ \| `(?:GET|POST|PUT|DELETE|WS)` \| `([^`]+)`", readme, re.M))
    assert documented, "لم تُستخرج أي endpoints من README — تغيّر شكل الجدول؟"
    routes = {re.sub(r"\{[^}]+\}", "{}", r.path) for r in app.routes if hasattr(r, "path")}
    missing = sorted(p for p in documented if re.sub(r"\{[^}]+\}", "{}", p) not in routes)
    assert not missing, f"موثّقة في README وغير موجودة في التطبيق: {missing}"
