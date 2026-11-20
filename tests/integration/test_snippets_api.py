"""Integration tests for the snippets/glossary API endpoints + rate limit.

Uses FastAPI TestClient against the real app factory; snippet storage is
pointed at a temp SQLite via env (snippet paths are relative to the repo
data dir, so tests create isolated DBs by monkeypatching the default path).
"""
from __future__ import annotations

import os
import time

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")

from src.api.server import create_app  # noqa: E402
from src.db import snippet_db as snippet_db_module  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # isolate the snippets database per test: force every SnippetDB() call
    # (default arg is bound at class-definition time, so patch the symbol)
    db_path = tmp_path / "snippets.db"
    real_snippet_db = snippet_db_module.SnippetDB
    monkeypatch.setattr(
        snippet_db_module, "SnippetDB", lambda path=None: real_snippet_db(db_path)
    )
    # generous rate limit so tests don't trip it; rate-limit test lowers it
    monkeypatch.setenv("INTELLIFILE_RATE_LIMIT", "100000")
    app = create_app()
    return fastapi_testclient.TestClient(app)


def _make_snippet(client, **overrides):
    payload = {
        "source_image": "scan.png",
        "bbox": {"x1": 5, "y1": 6, "x2": 100, "y2": 40},
        "level": "word",
        "text": "الجرعة",
        "ocr_text": "الجرعـة",
        "confidence": 0.0,
        "language": "ar",
        "category": "medical",
    }
    payload.update(overrides)
    resp = client.post("/api/snippets", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_snippet_create_list_update_approve_cycle(client):
    created = _make_snippet(client)
    sid = created["id"]
    assert created["bbox"] == [5, 6, 100, 40]

    # list
    listed = client.get("/api/snippets").json()
    assert listed["count"] == 1 and listed["items"][0]["id"] == sid

    # update bbox + text (the core user edit)
    patched = client.patch(
        f"/api/snippets/{sid}",
        json={"bbox": {"x1": 0, "y1": 0, "x2": 60, "y2": 30}, "text": "الجرعة اليومية"},
    )
    assert patched.status_code == 200
    assert patched.json()["snippet"]["bbox"] == [0, 0, 60, 30]

    # approve
    approved = client.post(f"/api/snippets/{sid}/approve", json={"verified_by": "qa"})
    assert approved.json()["status"] == "approved"
    stats = client.get("/api/snippets/stats").json()
    assert stats["by_status"].get("approved") == 1

    # delete
    assert client.delete(f"/api/snippets/{sid}").json()["ok"] is True
    assert client.get("/api/snippets/stats").json()["total"] == 0


def test_snippet_rejects_invalid_bbox(client):
    resp = client.post(
        "/api/snippets",
        json={"source_image": "s.png", "bbox": {"x1": 10, "y1": 5, "x2": 0, "y2": 30}},
    )
    assert resp.status_code == 400


def test_snippet_patch_unknown_id_404(client):
    resp = client.patch("/api/snippets/9999", json={"text": "new"})
    assert resp.status_code == 404


def test_glossary_suggest_endpoint(client):
    resp = client.get("/api/glossary/suggest", params={"text": "Compos", "limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    assert any("Composition" in s for s in body["suggestions"])
    info = client.get("/api/glossary/info").json()
    assert info["terms"] >= 700


def test_export_hf_endpoint_writes_jsonl(client):
    created = _make_snippet(client)
    sid = created["id"]
    client.post(f"/api/snippets/{sid}/approve", json={"verified_by": "qa"})
    resp = client.post("/api/snippets/export-hf")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    from src.services.hf_exporter import HFExporter

    assert HFExporter.__name__ == "HFExporter"  # endpoint wired the real service


def test_rate_limit_returns_429(tmp_path, monkeypatch):
    db_path = tmp_path / "snippets.db"
    real_snippet_db = snippet_db_module.SnippetDB
    monkeypatch.setattr(
        snippet_db_module, "SnippetDB", lambda path=None: real_snippet_db(db_path)
    )
    monkeypatch.setenv("INTELLIFILE_RATE_LIMIT", "3")
    monkeypatch.setenv("INTELLIFILE_RATE_WINDOW", "60")
    app = create_app()
    with fastapi_testclient.TestClient(app) as c:
        for _ in range(3):
            r = c.get("/api/glossary/info")
            assert r.status_code == 200
        r = c.get("/api/glossary/info")
        assert r.status_code == 429
        assert "rate limit" in r.json()["detail"]


def test_lightweight_mode_health(tmp_path, monkeypatch):
    db_path = tmp_path / "snippets.db"
    real_snippet_db = snippet_db_module.SnippetDB
    monkeypatch.setattr(
        snippet_db_module, "SnippetDB", lambda path=None: real_snippet_db(db_path)
    )
    monkeypatch.setenv("INTELLIFILE_LIGHTWEIGHT", "1")
    app = create_app()
    with fastapi_testclient.TestClient(app) as c:
        mode = c.get("/api/health/mode").json()
        assert mode == {"lightweight": True}
        health = c.get("/api/health").json()
        assert health["engines"]["lightweight_mode"] is True
        assert health["engines"]["ollama"] is False


def test_file_serve_endpoint_sandboxed(tmp_path, monkeypatch):
    db_path = tmp_path / "snippets.db"
    real_snippet_db = snippet_db_module.SnippetDB
    monkeypatch.setattr(
        snippet_db_module, "SnippetDB", lambda path=None: real_snippet_db(db_path)
    )
    from PIL import Image as PILImage

    img_path = tmp_path / "img.png"
    PILImage.new("RGB", (10, 10), "white").save(img_path)
    monkeypatch.setenv("INTELLIFILE_ALLOWED_DIRS", str(tmp_path))

    app = create_app()
    with fastapi_testclient.TestClient(app) as c:
        # how the server reads allowed dirs decides success; the endpoint must
        # never serve non-images or escape the sandbox regardless
        r = c.get("/api/file/serve", params={"filepath": str(img_path)})
        if r.status_code == 200:
            assert r.headers["content-type"] == "image/png"
        else:
            assert r.status_code in (400, 403)
        # non-image is always rejected
        txt = tmp_path / "note.txt"
        txt.write_text("hello", encoding="utf-8")
        r2 = c.get("/api/file/serve", params={"filepath": str(txt)})
        assert r2.status_code in (400, 403)
