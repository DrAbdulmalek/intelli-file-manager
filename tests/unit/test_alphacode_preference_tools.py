# -*- coding: utf-8 -*-
"""اختبارات أدوات تفضيلات AlphaCode عبر خادم MCP (§9E)

كل الاتصال عبر dispatch() في العملية نفسها — وهذا هو النقل المحلي نفسه
(stdio). تغطي: الاتصال المحلي، رفض العميل غير الموثق (قبل التهيئة)،
رفض payload غير صالح، لا تنفيذ shell، لا آثار ملفات، وحالة المعطّل.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from src.integrations import alphacode_mcp_server as server
from src.integrations.alphacode_preference_tools import PREFERENCE_TOOLS


@pytest.fixture
def env_paths(tmp_path, monkeypatch):
    store = tmp_path / "store" / "prefs.json"
    monkeypatch.setenv("IFM_PREFERENCES_JSON", str(store))
    monkeypatch.setenv("IFM_FEEDBACK_JSONL", str(tmp_path / "store" / "feedback.jsonl"))
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return store, data_dir


def _init(state):
    resp = server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                            "params": {"protocolVersion": "2025-11-25"}}, state)
    server.dispatch({"jsonrpc": "2.0", "method": "notifications/initialized"}, state)
    assert resp["result"]["serverInfo"]["version"] == "0.2.0"
    return resp


def _call(name, args, state):
    return server.dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                            "params": {"name": name, "arguments": args}}, state)


_META = {"name": "scan.png", "extension": ".png", "category": "مستندات"}


# ─── الاتصال المحلي ─────────────────────────────────────────────────────────

def test_tools_listed_after_initialize(env_paths):
    state = {}
    _init(state)
    resp = server.dispatch({"jsonrpc": "2.0", "id": 3, "method": "tools/list"}, state)
    names = [t["name"] for t in resp["result"]["tools"]]
    for tool in PREFERENCE_TOOLS:
        assert tool["name"] in names


def test_get_suggestion_null_then_learning_then_suggestion(env_paths):
    store, data_dir = env_paths
    state = {}
    _init(state)
    r1 = _call("intellifile.get_suggestion",
               {"metadata": _META, "file_fingerprint": "FP1"}, state)
    body = json.loads(r1["result"]["content"][0]["text"])
    assert body["suggestion"] is None
    # تعلم عبر المسار الموثق: تصحيح + تأكيد صريح
    r2 = _call("intellifile.record_user_correction",
               {"metadata": _META, "original_prediction": "مستندات",
                "corrected_value": "صور", "source_session": "ui-1",
                "file_fingerprint": "FP1", "user_confirmed": True}, state)
    body2 = json.loads(r2["result"]["content"][0]["text"])
    assert body2["applied"]["engine_result"]["created"] is True
    r3 = _call("intellifile.get_suggestion",
               {"metadata": _META, "file_fingerprint": "FP2"}, state)
    body3 = json.loads(r3["result"]["content"][0]["text"])
    assert body3["suggestion"]["category"] == "صور"


def test_record_without_explicit_confirmation_stays_pending(env_paths):
    state = {}
    _init(state)
    r = _call("intellifile.record_user_correction",
              {"metadata": _META, "original_prediction": "مستندات",
               "corrected_value": "صور", "source_session": "ui-1",
               "file_fingerprint": "FP1"}, state)
    body = json.loads(r["result"]["content"][0]["text"])
    assert body["review_status"] == "pending_review"
    assert body["applied"] is None
    # لا قاعدة تعلمت
    sg = _call("intellifile.get_suggestion",
               {"metadata": _META, "file_fingerprint": "FP9"}, state)
    assert json.loads(sg["result"]["content"][0]["text"])["suggestion"] is None


# ─── رفض غير الموثق والـpayload غير الصالح ─────────────────────────────────

def test_tools_rejected_before_initialize(env_paths):
    """هوية العميل: بوابة التهيئة إلزامية قبل أي أداة (رفض غير الموثق)."""
    state = {}
    r = _call("intellifile.get_suggestion",
              {"metadata": _META, "file_fingerprint": "FP"}, state)
    assert "error" in r and r["error"]["message"] == "Server not initialized"


def test_invalid_payload_rejected(env_paths):
    state = {}
    _init(state)
    r = _call("intellifile.record_user_correction",
              {"source_session": "x"}, state)  # metadata ناقصة
    assert r["result"]["isError"] is True
    assert "metadata" in json.loads(r["result"]["content"][0]["text"])["error"]


def test_unknown_tool_refused(env_paths):
    state = {}
    _init(state)
    r = _call("intellifile.launch_missiles", {}, state)
    assert r["result"]["isError"] is True


def test_unknown_rule_refused(env_paths):
    state = {}
    _init(state)
    for tool in ("intellifile.explain_rule", "intellifile.disable_rule",
                 "intellifile.enable_rule", "intellifile.confirm_rule"):
        r = _call(tool, {"rule_id": "no-such"}, state)
        assert r["result"]["isError"] is True


# ─── إدارة القواعد عبر الأدوات ──────────────────────────────────────────────

def test_disable_enable_and_explain_flow(env_paths):
    state = {}
    _init(state)
    rec = json.loads(_call("intellifile.record_user_correction",
                           {"metadata": _META, "original_prediction": "مستندات",
                            "corrected_value": "صور", "source_session": "ui-1",
                            "file_fingerprint": "FP1", "user_confirmed": True},
                           state)["result"]["content"][0]["text"])
    rule_id = rec["applied"]["engine_result"]["rule_id"]
    # disable → لا اقتراح
    d = json.loads(_call("intellifile.disable_rule", {"rule_id": rule_id}, state)
                   ["result"]["content"][0]["text"])
    assert d["status"] == "disabled"
    sg = json.loads(_call("intellifile.get_suggestion",
                          {"metadata": _META, "file_fingerprint": "FP2"}, state)
                    ["result"]["content"][0]["text"])
    assert sg["suggestion"] is None
    # enable → يعود الاقتراح
    e = json.loads(_call("intellifile.enable_rule", {"rule_id": rule_id}, state)
                   ["result"]["content"][0]["text"])
    assert e["status"] == "provisional"
    sg2 = json.loads(_call("intellifile.get_suggestion",
                           {"metadata": _META, "file_fingerprint": "FP2"}, state)
                     ["result"]["content"][0]["text"])
    assert sg2["suggestion"]["category"] == "صور"
    # explain_rule كامل الحقول
    ex = json.loads(_call("intellifile.explain_rule", {"rule_id": rule_id}, state)
                    ["result"]["content"][0]["text"])
    assert ex["rule"]["rule_id"] == rule_id
    assert ex["explanation"]["independent_confirmations"] == 1


def test_list_applicable_rules(env_paths):
    state = {}
    _init(state)
    _call("intellifile.record_user_correction",
          {"metadata": _META, "original_prediction": "مستندات",
           "corrected_value": "صور", "source_session": "ui-1",
           "file_fingerprint": "FP1", "user_confirmed": True}, state)
    lst = json.loads(_call("intellifile.list_applicable_rules",
                           {"metadata": _META}, state)["result"]["content"][0]["text"])
    assert lst["count"] == 1
    assert lst["applicable"][0]["destination"] == "صور"


# ─── الأمان: لا shell ولا آثار ملفات ───────────────────────────────────────

def test_no_shell_execution_in_tools_or_server():
    """فحص AST: لا استيراد subprocess ولا استدعاءات os.system/Popen."""
    import ast

    def uses_shell(path: str) -> bool:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name.split(".")[0] == "subprocess" for alias in node.names):
                    return True
            if isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] == "subprocess":
                    return True
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in ("system", "popen", "Popen"):
                    return True
        return False

    import src.integrations
    pkg_dir = Path(src.integrations.__file__).parent
    assert not uses_shell(str(pkg_dir / "alphacode_preference_tools.py"))
    assert not uses_shell(str(pkg_dir / "alphacode_mcp_server.py"))


def test_no_file_operation_side_effects(env_paths):
    store, data_dir = env_paths
    state = {}
    _init(state)
    (data_dir / "target.xyz").write_text("synthetic")
    _call("intellifile.record_user_correction",
          {"metadata": _META, "original_prediction": "مستندات",
           "corrected_value": "صور", "source_session": "ui-1",
           "file_fingerprint": "FP1", "user_confirmed": True}, state)
    # ملف البيانات لم يُمس ولا انتقل
    assert (data_dir / "target.xyz").exists()
    assert list(data_dir.iterdir()) == [data_dir / "target.xyz"]
    # المتغيرات المكتوبة: مخزن التفضيلات + سجل feedback فقط (لا مسارات نقل)
    store_files = sorted(p.name for p in store.parent.iterdir())
    assert all(n.startswith(("prefs.json", "feedback.jsonl")) for n in store_files)


def test_ops_log_strips_payloads(env_paths, tmp_path, monkeypatch):
    ops = tmp_path / "ops" / "ops.log"
    monkeypatch.setenv("IFM_ADAPTER_OPS_LOG", str(ops))
    state = {}
    _init(state)
    _call("intellifile.record_user_correction",
          {"metadata": {"name": "SECRET-NAME.png", "extension": ".png",
                        "category": "مستندات"},
           "original_prediction": "مستندات", "corrected_value": "صور",
           "source_session": "ui-1", "file_fingerprint": "FP1",
           "user_confirmed": True}, state)
    log_text = ops.read_text(encoding="utf-8")
    assert "SECRET-NAME" not in log_text      # لا payload في سجل العمليات
    assert "user_correction" in log_text       # اسم الأداة فقط


def test_raw_file_path_never_stored_verbatim(env_paths):
    state = {}
    _init(state)
    _call("intellifile.record_user_correction",
          {"metadata": _META,
           "file_path": "/home/user/private/scan.png",
           "original_prediction": "مستندات", "corrected_value": "صور",
           "source_session": "ui-1", "user_confirmed": True}, state)
    on_disk = (env_paths[0].read_text(encoding="utf-8")
               + env_paths[0].with_suffix(".json.bak").read_text(encoding="utf-8")
               if env_paths[0].with_suffix(".json.bak").exists()
               else env_paths[0].read_text(encoding="utf-8"))
    assert "/home/user/private" not in on_disk
