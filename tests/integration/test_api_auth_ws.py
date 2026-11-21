# -*- coding: utf-8 -*-
"""اختبارات مصادقة API وWebSocket ومنع تسريب التوكنات.

يغطي (المرحلة 6 من التصلّد):
  - X-API-Key إلزامي على endpoints كانت بلا مصادقة سابقاً.
  - WebSocket /api/copilot/ws: المفتاح قبل accept() — بلا مفتاح/مفتاح
    خاطئ → رفض؛ Origin ليس مصادقة.
  - /api/snippets/export-hf/push: التوكن في Header فقط — الصيغة القديمة
    عبر Query ماتت (لا ظهور للتوكن في أي رد).
  - /api/ner/extract: أُزيل (أسلاك ميتة — medical_ner غير موجودة).
  - /api/file/serve: مصادقة + حاجز حساسي قبل خدمة الصور.
  - إصدار موحّد عبر src/__version__.py.
"""
from __future__ import annotations

import importlib
import io
import os
import sys

import pytest

fastapi = pytest.importorskip("fastapi")
starlette_websockets = pytest.importorskip("starlette.websockets")
WebSocketDisconnect = starlette_websockets.WebSocketDisconnect

from fastapi.testclient import TestClient  # noqa: E402

TEST_KEY = "unit-test-key-123456"


def _make_client(*, api_key: str | None, allowed_dirs: str | None = None):
    """يبني TestClient بعد ضبط البيئة وإعادة تحميل src.api.server.

    يعدّل os.environ مباشرة؛ تنظيفه يتم في fixture بعد الاختبار.
    """
    if api_key is None:
        os.environ.pop("INTELLIFILE_API_KEY", None)
    else:
        os.environ["INTELLIFILE_API_KEY"] = api_key
    if allowed_dirs is None:
        os.environ.pop("INTELLIFILE_ALLOWED_DIRS", None)
    else:
        os.environ["INTELLIFILE_ALLOWED_DIRS"] = allowed_dirs
    import src.api.server as server_module

    reloaded = importlib.reload(server_module)
    reloaded.reset_allowed_dirs_cache()
    app = reloaded.create_app()
    return TestClient(app), reloaded


@pytest.fixture
def restore_clean_server(monkeypatch):
    """يعيد خادم نظيف بلا مفتاح بعد كل اختبار (حماية بقية الطيف)."""
    yield
    monkeypatch.delenv("INTELLIFILE_API_KEY", raising=False)
    monkeypatch.delenv("INTELLIFILE_ALLOWED_DIRS", raising=False)
    import src.api.server as server_module

    importlib.reload(server_module)
    server_module.reset_allowed_dirs_cache()


def _auth_headers(key: str) -> dict:
    return {"X-API-Key": key}


# ─── 1. المصادقة على endpoints كانت مفتوحة سابقاً ────────────────────────────

def test_endpoints_require_api_key_when_configured(restore_clean_server):
    client, _ = _make_client(api_key=TEST_KEY)

    for method, url, kwargs in [
        ("get", "/api/tags/search", {"params": {"directory": ".", "tag": "x"}}),
        ("get", "/api/tags/all", {"params": {"directory": "."}}),
        ("get", "/api/copilot/conversations", {}),
        ("get", "/api/stats", {}),
    ]:
        r = getattr(client, method)(url, **kwargs)
        assert r.status_code == 401, f"{url} بلا مفتاح يجب أن يُرفض"

    # بمفتاح صحيح تُقبل
    r = client.get("/api/stats", headers=_auth_headers(TEST_KEY))
    assert r.status_code == 200


def test_wrong_api_key_rejected(restore_clean_server):
    client, _ = _make_client(api_key=TEST_KEY)
    r = client.get("/api/stats", headers=_auth_headers("wrong-key-000000"))
    assert r.status_code == 401


def test_no_api_key_configured_allows_local(restore_clean_server):
    """السلوك الافتراضي المحلي (بلا مفتاح مضبوط) يبقى يعمل."""
    client, _ = _make_client(api_key=None)
    r = client.get("/api/stats")
    assert r.status_code == 200


# ─── 2. WebSocket ────────────────────────────────────────────────────────────

def test_ws_rejects_missing_key(restore_clean_server):
    client, _ = _make_client(api_key=TEST_KEY)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/copilot/ws"):
            pass


def test_ws_rejects_wrong_key(restore_clean_server):
    client, _ = _make_client(api_key=TEST_KEY)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/api/copilot/ws", headers={"x-api-key": "bad-key"}
        ):
            pass


def test_ws_accepts_correct_key_and_replies(restore_clean_server):
    client, _ = _make_client(api_key=TEST_KEY)
    with client.websocket_connect(
        "/api/copilot/ws", headers={"x-api-key": TEST_KEY}
    ) as ws:
        ws.send_json({"message": "مرحبا"})
        data = ws.receive_json()
        assert "response" in data or "error" in data


def test_ws_works_without_key_when_not_configured(restore_clean_server):
    """بلا INTELLIFILE_API_KEY: وضع localhost المحلي يبقى متاحاً."""
    client, _ = _make_client(api_key=None)
    with client.websocket_connect("/api/copilot/ws") as ws:
        ws.send_json({"message": "مرحبا"})
        data = ws.receive_json()
        assert "response" in data or "error" in data


def test_ws_rejects_untrusted_origin_even_with_key(restore_clean_server):
    """Origin غير موثوق يُرفض (دفاع متصفحات إضافي — ليس مصادقة)."""
    client, _ = _make_client(api_key=TEST_KEY)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/api/copilot/ws",
            headers={"x-api-key": TEST_KEY, "origin": "https://evil.example"},
        ):
            pass


# ─── 3. HuggingFace token ────────────────────────────────────────────────────

def test_hf_push_requires_token_header_not_query(restore_clean_server):
    client, _ = _make_client(api_key=TEST_KEY)
    auth = _auth_headers(TEST_KEY)

    # 1) بلا توكن نهائياً → 400 مع إرشاد لـHeader
    r = client.post("/api/snippets/export-hf/push", headers=auth)
    assert r.status_code == 400
    assert "X-HF-Token" in r.json()["detail"]

    # 2) التوكن عبر Query (الصيغة القديمة المسربة) → ميت: لا رفع ولا ظهور
    r = client.post(
        "/api/snippets/export-hf/push",
        params={"token": "hf_supposedly_secret_token_value"},
        headers=auth,
    )
    assert r.status_code == 400
    body = r.json()
    assert "hf_supposedly_secret_token_value" not in body.get("detail", "")

    # 3) التوكن في Header → يُقبل ويُمرَّر للمصدر (فشل رفع متوقع بلا شبكة
    #    الحقيقي؛ الفحص هنا أن الصيغة مقبولة والرسالة لا تظهر التوكن)
    r = client.post(
        "/api/snippets/export-hf/push",
        headers={**auth, "X-HF-Token": "hf_header_token_value_123"},
    )
    # إما نجاح (نادر في CI) أو 400 بلا تسريب التوكن في أي رسالة
    assert r.status_code in (200, 400)
    assert "hf_header_token_value_123" not in r.text


# ─── 4. NER الأسلاك الميتة ───────────────────────────────────────────────────

def test_ner_endpoint_removed(restore_clean_server):
    """medical_ner غير موجودة وPRODUCT_IDENTITY يستبعد NER — الـendpoint أُزيل."""
    client, _ = _make_client(api_key=None)
    r = client.post("/api/ner/extract", json={"text": "test"})
    assert r.status_code in (404, 405)


def test_health_has_no_ner_engine_and_unified_version(restore_clean_server):
    client, _ = _make_client(api_key=None)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert "ner" not in body["engines"]
    from src.__version__ import __version__
    assert body["version"] == __version__
    assert body["version"] == client.get("/api/stats").json()["version"]


# ─── 5. /api/file/serve: مصادقة + حاجز ───────────────────────────────────────

def _make_png(path):
    from PIL import Image

    Image.new("RGB", (4, 4), color=(200, 100, 50)).save(path, format="PNG")


def test_file_serve_requires_auth(restore_clean_server, tmp_path):
    _make_png(tmp_path / "photo.png")
    client, _ = _make_client(api_key=TEST_KEY,
                             allowed_dirs=str(tmp_path))
    r = client.get("/api/file/serve", params={"filepath": str(tmp_path / "photo.png")})
    assert r.status_code == 401
    r = client.get("/api/file/serve", params={"filepath": str(tmp_path / "photo.png")},
                   headers=_auth_headers(TEST_KEY))
    assert r.status_code == 200


def test_file_serve_blocks_sensitive_images(restore_clean_server, tmp_path):
    """صورة باسم/مسار حساس لا تُخدم عبر HTTP إطلاقاً."""
    patients = tmp_path / "patients"
    patients.mkdir()
    _make_png(patients / "xray.png")
    client, _ = _make_client(api_key=TEST_KEY,
                             allowed_dirs=str(tmp_path))
    r = client.get("/api/file/serve", params={"filepath": str(patients / "xray.png")},
                   headers=_auth_headers(TEST_KEY))
    assert r.status_code == 403


def test_file_serve_blocks_secret_named_files(restore_clean_server, tmp_path):
    _make_png(tmp_path / "server.pem")  # صورة PNG باسم شهادة خاصة
    client, _ = _make_client(api_key=TEST_KEY,
                             allowed_dirs=str(tmp_path))
    r = client.get("/api/file/serve", params={"filepath": str(tmp_path / "server.pem")},
                   headers=_auth_headers(TEST_KEY))
    assert r.status_code == 403


# ─── 6. sandbox المجلدات المسموحة ────────────────────────────────────────────

def test_allowed_dirs_explicit_not_extended_with_cwd(restore_clean_server, tmp_path):
    """ثغرة سابقة: INTELLIFILE_ALLOWED_DIRS صريح + إلحاق Path.cwd() دائماً
    كان يسمح بأي مسار تحت cwd. الآن القائمة الصريحة تُحترم حرفياً."""
    import os
    from pathlib import Path

    outside = tmp_path / "outside.png"
    _make_png(outside)
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    client, module = _make_client(api_key=TEST_KEY,
                                  allowed_dirs=str(sandbox))
    dirs = module._get_allowed_dirs()
    assert Path(str(sandbox)).resolve() in dirs
    # مجلد العمل الحالي (خارج الصندوق عمداً) ليس ضمن القائمة الصريحة
    assert Path(os.getcwd()).resolve() not in dirs


def test_default_mode_still_includes_cwd(restore_clean_server):
    """الوضع الافتراضي (بلا env) يحافظ على السلوك القديم (cwd مسموح)."""
    import os
    from pathlib import Path

    client, module = _make_client(api_key=None, allowed_dirs=None)
    dirs = module._get_allowed_dirs()
    assert Path(os.getcwd()).resolve() in dirs


# ─── 7. process endpoints المكسورة سابقاً ────────────────────────────────────

def test_process_document_endpoint_works(restore_clean_server, tmp_path):
    """كانت ترمي AttributeError (الصنف بلا process_document) → الآن تعمل."""
    doc = tmp_path / "note.txt"
    doc.write_text("نص قابل للاستخراج")
    client, _ = _make_client(api_key=None, allowed_dirs=str(tmp_path))
    r = client.post("/api/process/document", params={"filepath": str(doc)})
    assert r.status_code == 200
    assert "نص قابل للاستخراج" in r.json().get("extracted_text", "")


def test_process_document_blocks_sensitive(restore_clean_server, tmp_path):
    patients = tmp_path / "patients"
    patients.mkdir()
    secret = patients / "report.txt"
    secret.write_text("بيانات اصطناعية")
    client, _ = _make_client(api_key=None, allowed_dirs=str(tmp_path))
    r = client.post("/api/process/document", params={"filepath": str(secret)})
    assert r.status_code == 403


def test_process_image_endpoint_accepts_fix_scan_kwarg(restore_clean_server, tmp_path):
    """كانت ترمي TypeError (process_image بلا fix_scan) → الآن تعمل."""
    from PIL import Image

    img = tmp_path / "pic.png"
    Image.new("RGB", (4, 4)).save(img, format="PNG")
    client, _ = _make_client(api_key=None, allowed_dirs=str(tmp_path))
    r = client.post("/api/process/image",
                    params={"filepath": str(img), "fix_scan": "false"})
    assert r.status_code == 200
