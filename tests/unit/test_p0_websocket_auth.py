"""P0: /api/copilot/ws كان يتجاوز مفتاح API (بقية الـendpoints ترفض بـ401)."""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from src.api import server  # noqa: E402

KEY = "k3y-for-tests"


@pytest.fixture
def client(monkeypatch):
    """يبني تطبيقًا جديدًا بنسخة FileCopilot وهمية (المحركات داخلية لـ create_app)."""
    import src.core.file_copilot as fc

    class _StubCopilot:
        def chat(self, message, conv_id=None):
            return {"reply": f"echo:{message}"}

    monkeypatch.setattr(fc, "FileCopilot", _StubCopilot)
    monkeypatch.delenv("INTELLIFILE_LIGHTWEIGHT", raising=False)
    app = server.create_app()
    return TestClient(app, raise_server_exceptions=False)


def _chat(ws):
    ws.send_json({"message": "hi"})
    return ws.receive_json()


def test_ws_rejected_without_key_when_key_configured(client, monkeypatch):
    monkeypatch.setattr(server, "_API_KEY", KEY)
    with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect("/api/copilot/ws"):
        pass
    assert exc.value.code in (4401, 1008, 1006) or exc.value.code >= 1000


def test_ws_rejected_with_wrong_key(client, monkeypatch):
    monkeypatch.setattr(server, "_API_KEY", KEY)
    with pytest.raises(WebSocketDisconnect), client.websocket_connect(
        "/api/copilot/ws", headers={"X-API-Key": "wrong"}
    ):
        pass


def test_ws_accepts_correct_header(client, monkeypatch):
    monkeypatch.setattr(server, "_API_KEY", KEY)
    with client.websocket_connect("/api/copilot/ws", headers={"X-API-Key": KEY}) as ws:
        assert _chat(ws) == {"reply": "echo:hi"}


def test_ws_accepts_correct_subprotocol_and_echoes_it(client, monkeypatch):
    monkeypatch.setattr(server, "_API_KEY", KEY)
    with client.websocket_connect("/api/copilot/ws", subprotocols=[f"ifm-key.{KEY}"]) as ws:
        assert ws.accepted_subprotocol == f"ifm-key.{KEY}"
        assert _chat(ws) == {"reply": "echo:hi"}


def test_ws_rejects_wrong_subprotocol_key(client, monkeypatch):
    monkeypatch.setattr(server, "_API_KEY", KEY)
    with pytest.raises(WebSocketDisconnect), client.websocket_connect(
        "/api/copilot/ws", subprotocols=["ifm-key.nope"]
    ):
        pass


def test_ws_foreign_origin_still_rejected_even_with_valid_key(client, monkeypatch):
    monkeypatch.setattr(server, "_API_KEY", KEY)
    with pytest.raises(WebSocketDisconnect), client.websocket_connect(
        "/api/copilot/ws", headers={"X-API-Key": KEY, "Origin": "https://evil.example"}
    ):
        pass


def test_ws_open_when_no_key_configured_localhost_default(client, monkeypatch):
    monkeypatch.setattr(server, "_API_KEY", "")
    with client.websocket_connect("/api/copilot/ws") as ws:
        assert _chat(ws) == {"reply": "echo:hi"}


def test_http_key_check_still_works(client, monkeypatch):
    monkeypatch.setattr(server, "_API_KEY", KEY)
    assert client.get("/api/health").status_code in (200, 401)  # health قد يكون مفتوحًا
    r = client.post("/api/classify", json={"path": "/tmp/x"}, headers={"X-API-Key": "bad"})
    assert r.status_code == 401
