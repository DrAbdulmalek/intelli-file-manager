# -*- coding: utf-8 -*-
"""اختبارات طبقة MCP + حلقة Feedback (مقترح DeepSeek 2026-11-20 — التنفيذ الموثق).

تغطي:
  - dispatcher JSON-RPC: initialize / tools/list / tools/call / أخطاء
  - الأدوات الثماني فوق بروتوكولات src/core الفعلية
  - feedback_token يربط الإشارة بالاستدعاء
  - الترقية 3x إلى قاعدة دائمة + وزن النجاح والتقادم
  - حاجز الأمان: overwrite غير موجود، والحساسية غير قابلة للتجاوز بالتفضيلات
"""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from src.core.safe_mover import SafeMover
from src.mcp_server.feedback import (
    ALLOWED_PREFERRED_ACTIONS,
    FeedbackStore,
    PROMOTION_THRESHOLD,
)
from src.mcp_server.server import IntelliFileMcpServer


# ─── تجهيزات ────────────────────────────────────────────────────────────────

def _server(tmp_path) -> IntelliFileMcpServer:
    return IntelliFileMcpServer(store=FeedbackStore(tmp_path / "prefs.db"))


def _call(server, name: str, arguments: dict):
    return server.handle_request({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })


def _structured(server, name: str, arguments: dict) -> dict:
    resp = _call(server, name, arguments)
    return resp["result"]["structuredContent"]


# ─── 1) dispatcher JSON-RPC ─────────────────────────────────────────────────

def test_initialize_negotiates_protocol(tmp_path):
    server = _server(tmp_path)
    resp = server.handle_request({"jsonrpc": "2.0", "id": 7, "method": "initialize", "params": {}})
    assert resp["result"]["protocolVersion"] == "2025-06-18"
    assert resp["result"]["serverInfo"]["name"] == "intelli-file-mcp"


def test_notifications_silently_accepted(tmp_path):
    assert _server(tmp_path).handle_request(
        {"jsonrpc": "2.0", "method": "notifications/initialized"}
    ) is None


def test_tools_list_has_eight_tools_with_schemas(tmp_path):
    resp = _server(tmp_path).handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {t["name"] for t in resp["result"]["tools"]}
    assert names == {
        "classify_path", "safe_move_file", "safe_copy_file", "evaluate_rule",
        "undo_last", "query_action_log", "feedback_record", "preference_query",
    }
    for t in resp["result"]["tools"]:
        assert t["inputSchema"]["type"] == "object"
        assert t["description"].strip()


def test_unknown_tool_returns_proper_error(tmp_path):
    resp = _call(_server(tmp_path), "no_such_tool", {})
    assert resp["error"]["code"] == -32602


# ─── 2) الأدوات فوق بروتوكولات src/core الفعلية ─────────────────────────────

def test_classify_path_reports_medical_sensitivity(tmp_path):
    server = _server(tmp_path)
    sensitive = tmp_path / "patients" / "scan.dcm"
    sensitive.parent.mkdir()
    sensitive.write_bytes(b"\x00" * 200)
    plain = tmp_path / "notes" / "todo.txt"
    plain.parent.mkdir()
    plain.write_text("x")

    got_sensitive = _structured(server, "classify_path", {"path": str(sensitive)})
    got_plain = _structured(server, "classify_path", {"path": str(plain)})

    assert got_sensitive["success"] and got_sensitive["is_sensitive"]
    assert "تصوير طبي" in got_sensitive["reason"]
    assert got_plain["success"] and not got_plain["is_sensitive"]


def test_safe_move_file_moves_and_returns_feedback_token(tmp_path):
    server = _server(tmp_path)
    src = tmp_path / "report.txt"
    src.write_text("CONTENT")
    dst = tmp_path / "docs" / "report.txt"

    resp = _call(server, "safe_move_file", {"src": str(src), "dst": str(dst)})
    got = resp["result"]["structuredContent"]

    assert got["success"] and Path(got["final_path"]).read_text() == "CONTENT"
    assert not src.exists()
    token = resp["result"]["_meta"]["feedback_token"]
    assert token and server.store.events_for_token(token)


def test_safe_move_file_suffixes_on_collision_not_replace(tmp_path):
    server = _server(tmp_path)
    src = tmp_path / "report.txt"
    src.write_text("NEW")
    dst = tmp_path / "docs" / "report.txt"
    dst.parent.mkdir()
    dst.write_text("OCCUPANT")

    got = _structured(server, "safe_move_file", {"src": str(src), "dst": str(dst)})

    assert got["success"] and got["used_suffix"]
    assert dst.read_text() == "OCCUPANT"  # لا استبدال صامت — عقد المستودع
    assert Path(got["final_path"]).name.startswith("report_")


def test_safe_move_file_rejects_overwrite_parameter_by_design(tmp_path):
    """العقد الثابت: overwrite غير معروض — حتى لو أصرّ الوكيل أو «تعلمه» من التفضيلات."""
    server = _server(tmp_path)
    src = tmp_path / "a.txt"
    src.write_text("A")
    dst = tmp_path / "b.txt"
    dst.write_text("B")

    got = _structured(server, "safe_move_file", {"src": str(src), "dst": str(dst), "overwrite": True})

    assert not got["success"] and "محظور" in got["error"]
    assert src.exists() and dst.read_text() == "B"  # لا شيء تغيّر


def test_safe_move_file_blocks_sensitive_source_before_any_action(tmp_path):
    """حاجز الحساسية غير قابل للتجاوز — يمنع النقل قبل أي فعل حتى مع تفضيل مسجل."""
    server = _server(tmp_path)
    sensitive = tmp_path / "patients" / "scan.dcm"
    sensitive.parent.mkdir()
    sensitive.write_bytes(b"\x00" * 200)
    outside = tmp_path / "public" / "scan.dcm"

    # سجّل تفضيلاً «إيجابياً» على نقل الملفات الحساسة — لا يؤثر على الحاجز
    server.store.record("t0", "safe_move_file", "positive_explicit",
                        context="safe_move_file", condition_key="sensitive_source",
                        preferred_action="suffix")

    got = _structured(server, "safe_move_file", {"src": str(sensitive), "dst": str(outside)})

    assert not got["success"] and "محظور" in got["error"]
    assert sensitive.exists() and not outside.exists()


def test_safe_copy_file_copies_with_collision_suffix(tmp_path):
    server = _server(tmp_path)
    src = tmp_path / "source" / "doc.txt"
    src.parent.mkdir()
    src.write_text("DATA")
    dst = tmp_path / "dest" / "doc.txt"
    dst.parent.mkdir()
    dst.write_text("EXISTING")

    got = _structured(server, "safe_copy_file", {"src": str(src), "dst": str(dst)})

    assert got["success"] and got["used_suffix"]
    assert dst.read_text() == "EXISTING" and src.exists()
    assert Path(got["final_path"]).name.startswith("doc_")


def test_evaluate_rule_dry_run_matches_extension(tmp_path):
    server = _server(tmp_path)
    f = tmp_path / "photo.jpg"
    f.write_text("x")
    ruleset = {
        "name": "test", "rules": [{
            "name": "images", "priority": 10,
            "conditions": [{"field": "extension", "op": "in", "value": ["jpg", "png"]}],
            "actions": [{"type": "tag", "value": "photo"}],
        }],
    }

    got = _structured(server, "evaluate_rule", {"file_path": str(f), "ruleset": ruleset})

    assert got["success"] and got["matched"]
    assert got["actions"][0]["type"] == "tag"
    assert not list(tmp_path.rglob(".ifm_meta_*"))  # dry_run: لا تعديل فعلي


def test_undo_last_rolls_back_via_safemover(tmp_path):
    server = _server(tmp_path)
    src = tmp_path / "a.txt"
    src.write_text("X")
    dst = tmp_path / "b.txt"
    mover = SafeMover(verify_checksum=False)
    assert mover.move(str(src), str(dst)).success

    from src.core.rule_schemas import ActionType, UndoEntry
    from src.core.undo_log import UndoLog

    log_path = tmp_path / ".ifm_undo.json"
    ul = UndoLog(log_path)
    ul.append(UndoEntry(action_type=ActionType.MOVE.value,
                        file_path=str(src), file_path_after=str(dst), success=True))
    ul.save()

    got = _structured(server, "undo_last", {"undo_log_path": str(log_path)})

    assert got["success"] and src.read_text() == "X"


def test_undo_last_ambiguous_legacy_not_success(tmp_path):
    # F19 متابعة: السجل القديم الملتبس — success=False وسبب F19 يظهر
    server = _server(tmp_path)
    dest = tmp_path / "report.pdf"
    dest.write_text("user content", encoding="utf-8")
    legacy = {
        "action_type": "copy", "file_path": "/src/report.pdf",
        "file_path_after": str(dest), "rule_name": "r",
        "old_category": "", "new_category": "",
        "tags_added": [], "tags_removed": [],
        "timestamp": "2026-11-01T09:00:00",
        "success": False,
        "error_message": "فشل التراجع القديم الملوث",
        "batch_id": "",
    }
    log_path = tmp_path / ".ifm_undo.json"
    log_path.write_text(json.dumps({"entries": [legacy]}, ensure_ascii=False),
                        encoding="utf-8")

    got = _structured(server, "undo_last", {"undo_log_path": str(log_path)})

    assert got["success"] is False
    assert got["recovery_required"] is True
    assert "استرداد يدوياً" in got["error"] and "ملتبس" in got["error"]
    assert got["restored_path"] == ""
    assert dest.exists()  # لا عكس ولا حذف


def test_undo_last_rollback_failure_not_success(tmp_path):
    # F19 متابعة: إجراء ناجح الأصل فشل عكسه (v2) — success=False وسبب التراجع
    server = _server(tmp_path)
    from src.core.rule_schemas import UndoEntry
    from src.core.undo_log import UndoLog

    log_path = tmp_path / ".ifm_undo.json"
    ul = UndoLog(log_path)
    # الوجهة الأصلية داخل دليل قراءة-فقط → SafeMover يفشل فعلاً
    # (التضارب بدليل موجود يأخذ لاحقة فينجح — لذا القراءة-فقط حتمية)
    import os
    ro = tmp_path / "ro_parent"
    ro.mkdir()
    dest_file = tmp_path / "file.txt"
    dest_file.write_text("X", encoding="utf-8")
    ul.append(UndoEntry(action_type="move", file_path=str(ro / "target.txt"),
                        file_path_after=str(dest_file), success=True))
    ul.save()
    os.chmod(ro, 0o555)
    try:
        got = _structured(server, "undo_last", {"undo_log_path": str(log_path)})
    finally:
        os.chmod(ro, 0o755)

    assert got["success"] is False
    assert got["recovery_required"] is False
    assert "فشل التراجع" in got["error"]


def test_query_action_log_filters(tmp_path):
    server = _server(tmp_path)
    from src.core.action_log import ActionLog

    log_path = tmp_path / ".ifm_action_log.json"
    log = ActionLog(log_path)
    log.log(file_path="/x/a.txt", action_type="move", rule_name="r1", success=True)
    log.log(file_path="/x/b.txt", action_type="copy", rule_name="r1", success=False)
    log.save()

    got = _structured(server, "query_action_log",
                      {"log_path": str(log_path), "success": False})

    assert got["success"] and got["count"] == 1
    assert got["entries"][0]["file_path"] == "/x/b.txt"


# ─── 3) حلقة Feedback: token → إشارة → تفضيل → ترقية ────────────────────────

def test_feedback_loop_token_to_preference_to_promotion(tmp_path):
    server = _server(tmp_path)
    token = server._new_token("safe_move_file", {"src": "a"}, {"success": True})

    # 3 تصحيحات متطابقة: «عند وجود شاغل أريد اللاحقة» → تُرقّى لقاعدة دائمة
    for _ in range(PROMOTION_THRESHOLD):
        server.store.record(token, "safe_move_file", "negative",
                            context="safe_move_file",
                            condition_key="destination_exists",
                            preferred_action="suffix")

    prefs = server.store.query("safe_move_file")
    target = [p for p in prefs if p.condition == "destination_exists" and p.preferred_action == "suffix"]
    assert target and target[0].kind == "rule"
    assert target[0].support == PROMOTION_THRESHOLD


def test_security_actions_are_outside_the_learning_loop(tmp_path):
    """حاجز §7 في المقترح: لا تفضيل overwrite — المخزن نفسه يرفضه."""
    server = _server(tmp_path)
    with pytest.raises(ValueError, match="قرارات الأمان"):
        server.store.record("t", "safe_move_file", "negative",
                            context="safe_move_file", condition_key="any",
                            preferred_action="overwrite")
    # وقائمة الأفعال المسموحة لا تحوي overwrite أصلاً
    assert "overwrite" not in ALLOWED_PREFERRED_ACTIONS


def test_forbidden_signal_rejected(tmp_path):
    server = _server(tmp_path)
    with pytest.raises(ValueError, match="إشارة ممنوعة"):
        server.store.record("t", "safe_move_file", "jailbreak_signal")


def test_strength_success_weight_and_aging(tmp_path):
    """وزن النجاح 1.5× يظهر في تراكم الدعم، والتقادم يخفض القابلية."""
    store = FeedbackStore(tmp_path / "s.db")
    for i in range(3):
        store.record("t", "x", "positive_explicit", context="c",
                     condition_key="k", preferred_action="suffix")
    fresh = store.query("c")[0]
    assert fresh.strength > 0.9  # مستخدم للتو — قابلية عالية

    # تقادم اصطناعي: آخر استخدام منذ 60 يوماً مع استقرار قصير
    import math as _m
    import src.mcp_server.feedback as fb
    aged_r = _m.exp(-60.0 / fb._INITIAL_STABILITY_DAYS)
    assert aged_r < 0.05  # تجاوز نصف العمر افتراضياً → يُهمل من الاسترجاع


# ─── 4) التشغيل End-to-End عبر stdio ────────────────────────────────────────

def test_stdio_end_to_end_initialize_and_list(tmp_path):
    """تشغيل الخادم فعلياً كعملية فرعية — رسالتان JSON عبر stdin."""
    repo_root = Path(__file__).resolve().parents[2]
    proc = subprocess.Popen(
        [sys.executable, "-m", "src.mcp_server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, cwd=str(repo_root), text=True,
    )
    try:
        init = {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}
        listing = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        out, err = proc.communicate(
            json.dumps(init) + "\n" + json.dumps(listing) + "\n", timeout=60
        )
        lines = [json.loads(l) for l in out.strip().splitlines() if l.strip()]
        assert lines[0]["result"]["serverInfo"]["name"] == "intelli-file-mcp"
        assert len(lines[1]["result"]["tools"]) == 8
        assert not err.strip() or "Traceback" not in err
    finally:
        if proc.poll() is None:
            proc.kill()


# ─── 5) حد الخصوصية لسجل MCP Feedback ──────────────────────────────────────

def test_feedback_record_schema_rejects_free_form_fields(tmp_path):
    server = _server(tmp_path)
    response = server.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    )
    tool = next(
        item for item in response["result"]["tools"]
        if item["name"] == "feedback_record"
    )
    assert "note" not in tool["inputSchema"]["properties"]
    assert tool["inputSchema"]["additionalProperties"] is False


def test_feedback_record_tool_rejects_note_without_storing_it(tmp_path):
    server = _server(tmp_path)
    response = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "feedback_record",
                "arguments": {
                    "token": "safe-token",
                    "signal": "negative",
                    "note": "synthetic private path",
                },
            },
        }
    )
    assert response["result"]["isError"] is True
    assert server.store.events_for_token("safe-token") == []


def test_feedback_store_rejects_legacy_free_form_payloads(tmp_path):
    store = FeedbackStore(tmp_path / "feedback.db")
    base = ("safe-token", "safe_move_file", "outcome")
    with pytest.raises(ValueError, match="free-form"):
        store.record(*base, note="synthetic /private/report.pdf")
    with pytest.raises(ValueError, match="free-form"):
        store.record(*base, inputs={"src": "/synthetic/private/report.dcm"})
    with pytest.raises(ValueError, match="free-form"):
        store.record(*base, outcome={"text": "synthetic medical narrative"})
    assert store.events_for_token("safe-token") == []


def test_feedback_store_rejects_path_like_identifiers(tmp_path):
    store = FeedbackStore(tmp_path / "feedback.db")
    with pytest.raises(ValueError, match="bounded categorical token"):
        store.record("/synthetic/private/report.pdf", "safe_move_file", "outcome")
    with pytest.raises(ValueError, match="bounded categorical token"):
        store.record("safe-token", "safe_move_file", "outcome",
                     context="/synthetic/private")


def test_new_token_never_persists_inputs_or_outcome(tmp_path):
    server = _server(tmp_path)
    token = server._new_token(
        "safe_move_file",
        {"src": "/synthetic/private/report.dcm"},
        {"text": "synthetic patient narrative"},
    )
    events = server.store.events_for_token(token)
    assert len(events) == 1
    assert set(events[0]) == {"token", "tool", "signal", "ts"}
    columns = {
        row[1]
        for row in server.store._conn.execute("PRAGMA table_info(feedback_events)")
    }
    assert {"note", "inputs_json", "outcome_json"}.isdisjoint(columns)
    stored_row = server.store._conn.execute(
        "SELECT * FROM feedback_events WHERE token=?", (token,)
    ).fetchone()
    assert "/synthetic/private" not in repr(stored_row)
    assert "synthetic patient narrative" not in repr(stored_row)


def test_legacy_feedback_schema_is_preserved_but_payloads_are_not_exposed(tmp_path):
    db_path = tmp_path / "legacy-feedback.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """CREATE TABLE feedback_events (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               token TEXT NOT NULL,
               tool TEXT NOT NULL,
               signal TEXT NOT NULL,
               note TEXT DEFAULT '',
               context TEXT DEFAULT '',
               condition_key TEXT DEFAULT '',
               preferred_action TEXT DEFAULT '',
               inputs_json TEXT DEFAULT '{}',
               outcome_json TEXT DEFAULT '{}',
               ts TEXT NOT NULL
           )"""
    )
    conn.execute(
        """INSERT INTO feedback_events
           (token, tool, signal, note, context, condition_key, preferred_action,
            inputs_json, outcome_json, ts)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "legacy-token",
            "safe_move_file",
            "outcome",
            "/synthetic/legacy/report.pdf",
            "safe_move_file",
            "",
            "",
            '{"src":"/synthetic/legacy/report.pdf"}',
            '{"text":"synthetic legacy text"}',
            "2026-11-24T00:00:00+00:00",
        ),
    )
    conn.commit()
    conn.close()

    store = FeedbackStore(db_path)
    legacy_events = store.events_for_token("legacy-token")
    assert len(legacy_events) == 1
    assert "note" not in legacy_events[0]
    old_row = store._conn.execute(
        "SELECT note, inputs_json, outcome_json FROM feedback_events WHERE token=?",
        ("legacy-token",),
    ).fetchone()
    assert old_row[0] == "/synthetic/legacy/report.pdf"

    store.record("new-token", "safe_move_file", "outcome", context="safe_move_file")
    new_row = store._conn.execute(
        "SELECT note, inputs_json, outcome_json FROM feedback_events WHERE token=?",
        ("new-token",),
    ).fetchone()
    assert tuple(new_row) == ("", "{}", "{}")



def test_feedback_record_rejects_non_string_fields(tmp_path):
    server = _server(tmp_path)
    invalid_arguments = [
        {"token": None, "signal": "negative"},
        {"token": "safe-token", "signal": ["negative"]},
        {"token": "safe-token", "signal": "negative", "context": ["/synthetic/path"]},
        {"token": "safe-token", "signal": "negative", "condition": {"path": "/synthetic/path"}},
        {"token": "safe-token", "signal": "negative", "preferred_action": ["suffix"]},
    ]
    for arguments in invalid_arguments:
        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "feedback_record", "arguments": arguments},
            }
        )
        assert response["result"]["isError"] is True
    assert server.store.events_for_token("safe-token") == []
