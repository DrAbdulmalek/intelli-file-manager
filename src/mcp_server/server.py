# -*- coding: utf-8 -*-
"""خادم MCP لـ intelli-file-manager — بروتوكولات المستودع كأدوات لوكيل خارجي.

يوصل وكلاء مثل AlphaCode ببروتوكولات المستودع الفعلية:
  path/sensitive_barrier/safe_mover/rule_engine/undo_log/action_log
دون إعادة اختراع أي منطق — كل أداة تغليف رقيق فوق src/core.

بروتوكول MCP عبر stdio (JSON-RPC 2.0) — تنفيذ بلا تبعيات خارجية حتى
يعمل في CI وشجرة PR دون شبكة:
  initialize → notifications/initialized → tools/list → tools/call

كل أداة تغيير حالة تُرجع _meta.feedback_token لربط إشارة لاحقة عبر
أداة feedback_record — دورة: فعل ← إشارة ← تفضيل ← حقن في الاستدعاء التالي.

العقد الثابت (غير القابل للتعلم — مقترح DeepSeek §7):
  - safe_move_file لا يعرض overwrite إطلاقاً (تصحيح لمثال المقترح الذي
    كان يمرر overwrite=True ويناقض قسمه 7 — OverwriteForbiddenError عقود)
  - block_if_sensitive يُستدعى قبل كل نقل/نسخ — الحساسية غير قابلة للتجاوز
"""
from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.action_log import ActionLog
from ..core.rule_engine import RuleEngine
from ..core.safe_mover import SafeMover
from ..core.undo_log import UndoLog
from ..db.schemas import FileMetadata
from ..core.sensitive_barrier import (
    SensitiveFileBlockedError,
    block_if_sensitive,
    classify_sensitivity,
)
from .feedback import FeedbackStore

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "intelli-file-mcp", "version": "1.0.0"}

# ─── المخططات (inputSchema) ─────────────────────────────────────────────────

_TOOL_DEFS: List[Dict[str, Any]] = [
    {
        "name": "classify_path",
        "description": (
            "تصنيف حساسية مسار ملف عبر بروتوكول sensitive_barrier الفعلي "
            "(امتدادات طبية، دليمة DICOM، أجزاء مسار حساسة). استدعِه قبل أي "
            "عملية على ملف — إذا كان حساساً فلا تقرأ محتواه أبداً."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "مسار الملف"}},
            "required": ["path"],
        },
    },
    {
        "name": "safe_move_file",
        "description": (
            "نقل آمن عبر SafeMover: ذرّي، لا استبدال صامت (تضارب → لاحقة _1)، "
            "تحقق checksum، حاجز حساسية قبل التنفيذ. لا يوجد خيار overwrite — "
            "محظور كلياً بعقد المستودع."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "src": {"type": "string"},
                "dst": {"type": "string"},
            },
            "required": ["src", "dst"],
        },
    },
    {
        "name": "safe_copy_file",
        "description": "نسخ آمن عبر SafeMover (مؤقت + ربط ذرّي، حاجز حساسية، لا استبدال).",
        "inputSchema": {
            "type": "object",
            "properties": {"src": {"type": "string"}, "dst": {"type": "string"}},
            "required": ["src", "dst"],
        },
    },
    {
        "name": "evaluate_rule",
        "description": (
            "تقييم قواعد المستودع على ملف واحد عبر RuleEngine.dry_run — محاكاة "
            "بلا تعديل: أدخل قاعدة inline (ruleset) أو مسار YAML، يرجع المطابقة والإجراء."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "ruleset": {"type": "object", "description": "قاموس Ruleset (اختياري)"},
                "ruleset_yaml_path": {"type": "string", "description": "مسار YAML (بديل)"},
                "base_dir": {"type": "string", "description": "المجلد الأساسي للأهداف النسبية"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "undo_last",
        "description": (
            "التراجع عن آخر إجراء مسجل في UndoLog — يمر عبر SafeMover (لاحقة لا "
            "استبدال، فشل صريح). لا تحذف الملفات يدوياً أبداً."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "undo_log_path": {"type": "string", "description": "مسار .ifm_undo.json"},
                "condition": {"type": "string", "description": "سياق الإشارة للتفضيل (اختياري)"},
            },
            "required": ["undo_log_path"],
        },
    },
    {
        "name": "query_action_log",
        "description": "استعلام سجل الإجراءات المرئي مع تصفية اختيارية.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "log_path": {"type": "string"},
                "action_type": {"type": "string"},
                "rule_name": {"type": "string"},
                "success": {"type": "boolean"},
                "limit": {"type": "integer"},
            },
            "required": ["log_path"],
        },
    },
    {
        "name": "feedback_record",
        "description": (
            "تسجيل إشارة مستخدم على استدعاء سابق عبر feedback_token: "
            "negative / positive_implicit / positive_explicit / outcome — مع سياق "
            "وحالة مفضلة (suffix/reject/ask_user فقط؛ الأمان خارج التعلم)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "token": {"type": "string"},
                "signal": {"type": "string", "enum": ["negative", "positive_implicit", "positive_explicit", "outcome"]},
                "note": {"type": "string"},
                "context": {"type": "string", "description": "الأداة صاحبة التوكن مثل safe_move_file"},
                "condition": {"type": "string"},
                "preferred_action": {"type": "string", "enum": ["suffix", "reject", "ask_user"]},
            },
            "required": ["token", "signal"],
        },
    },
    {
        "name": "preference_query",
        "description": "استرجاع التفضيلات المتقادة لسياق أداة — حقنها في القرار قبل التنفيذ.",
        "inputSchema": {
            "type": "object",
            "properties": {"context": {"type": "string"}, "limit": {"type": "integer"}},
            "required": ["context"],
        },
    },
]

_TOOL_NAMES = {t["name"] for t in _TOOL_DEFS}


def _default_store() -> FeedbackStore:
    db = os.environ.get("IFM_PREFERENCE_DB")
    return FeedbackStore(Path(db).expanduser() if db else None)


class IntelliFileMcpServer:
    """خادم MCP: dispatcher JSON-RPC + تغليف الأدوات فوق src/core."""

    def __init__(self, store: Optional[FeedbackStore] = None):
        self.store = store or _default_store()

    # ─── أدوات التغليف ─────────────────────────────────────────────────

    def _tool_classify_path(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = str(args["path"])
        classification = classify_sensitivity(path)
        exists = Path(path).exists()
        structured = {
            "success": True,
            "path": path,
            "exists": exists,
            "is_sensitive": classification["is_sensitive"],
            "reason": classification["reason"],
            "extension": classification["extension"],
            "preference_hint": (
                "الحساسية غير قابلة للتعلم — الحاجز ثابت مهما كانت التفضيلات"
                if classification["is_sensitive"]
                else ""
            ),
        }
        return self._result(structured)

    def _tool_safe_move_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        src, dst = str(args["src"]), str(args["dst"])
        if "overwrite" in args:
            # حاجز التصميم: معامل overwrite غير موجود — أي محاولة تُرفض صراحة
            return self._result(
                {
                    "success": False,
                    "error": "overwrite غير مدعوم في هذه الأداة: محظور بعقد المستودع "
                    "(OverwriteForbiddenError) — التضارب يأخذ لاحقة دائماً",
                },
                is_error=True,
            )
        # حاجز الحساسية (عقد ثابت — غير قابل للتعلم): منع نقل بيانات طبية
        # خارج مواضعها المحمية. الوجهة لا تُحجب (النقل إلى موضع محمي وقائي).
        block_if_sensitive(src, operation="النقل الآمن عبر MCP")
        mover = SafeMover(verify_checksum=True, move_sidecar=True)
        try:
            result = mover.move(src, dst)
        except SensitiveFileBlockedError as e:
            return self._result({"success": False, "error": str(e)}, is_error=True)
        structured = {
            "success": result.success,
            "final_path": result.final_path,
            "used_suffix": bool(result.success and result.renamed_due_to_collision),
            "checksum_ok": bool(result.success and result.checksum_after),
            "error": result.error,
        }
        token = None
        if result.success:
            token = self._new_token("safe_move_file", {"src": src, "dst": dst}, structured)
            structured["condition"] = "destination_exists" if structured["used_suffix"] else "normal"
        return self._result(structured, token=token, is_error=not result.success)

    def _tool_safe_copy_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        src, dst = str(args["src"]), str(args["dst"])
        block_if_sensitive(src, operation="النسخ الآمن عبر MCP")
        mover = SafeMover(verify_checksum=True, move_sidecar=True)
        try:
            result = mover.copy(src, dst)
        except SensitiveFileBlockedError as e:
            return self._result({"success": False, "error": str(e)}, is_error=True)
        structured = {
            "success": result.success,
            "final_path": result.final_path,
            "used_suffix": bool(result.success and result.renamed_due_to_collision),
            "error": result.error,
        }
        token = None
        if result.success:
            token = self._new_token("safe_copy_file", {"src": src, "dst": dst}, structured)
        return self._result(structured, token=token, is_error=not result.success)

    def _tool_evaluate_rule(self, args: Dict[str, Any]) -> Dict[str, Any]:
        file_path = str(args["file_path"])
        if args.get("ruleset_yaml_path"):
            ruleset = _load_ruleset_from_yaml(str(args["ruleset_yaml_path"]))
        elif args.get("ruleset"):
            ruleset = _load_ruleset_from_dict(args["ruleset"])
        else:
            return self._result(
                {"success": False, "error": "مطلوب ruleset أو ruleset_yaml_path"}, is_error=True
            )
        from ..db.schemas import FileRecord

        path_obj = Path(file_path)
        record = FileRecord(
            metadata=FileMetadata(
                file_name=path_obj.name,
                file_path=str(path_obj),
                file_size=path_obj.stat().st_size if path_obj.exists() else 0,
                # عهد المستودع: الامتداد بلا نقطة (مطابق file_inventory)
                extension=path_obj.suffix.lower().lstrip("."),
            )
        )
        engine = RuleEngine(ruleset)
        plan = engine.dry_run([record], base_dir=str(args.get("base_dir", "")))
        actions = [
            {
                "rule": a.rule_name if hasattr(a, "rule_name") else "",
                "type": a.action.type if hasattr(a, "action") else "",
                "target": a.target_path if hasattr(a, "target_path") else "",
            }
            for a in plan.planned_actions
        ]
        structured = {
            "success": True,
            "matched": bool(actions),
            "actions": actions,
            "summary": plan.summary,
        }
        return self._result(structured)

    def _tool_undo_last(self, args: Dict[str, Any]) -> Dict[str, Any]:
        log_path = str(args["undo_log_path"])
        undo_log = UndoLog(log_path)
        entry = undo_log.rollback_last()
        structured: Dict[str, Any] = {
            "success": bool(entry is not None and entry.success),
            "error": entry.error_message if entry is not None else "السجل فارغ",
            "restored_path": entry.file_path if entry is not None else "",
        }
        token = None
        if structured["success"]:
            token = self._new_token("undo_last", {"undo_log_path": log_path}, structured)
        return self._result(structured, token=token, is_error=not structured["success"])

    def _tool_query_action_log(self, args: Dict[str, Any]) -> Dict[str, Any]:
        log = ActionLog(str(args["log_path"]))
        entries = log.list_entries(
            action_type=args.get("action_type"),
            rule_name=args.get("rule_name"),
            success=args.get("success"),
            limit=args.get("limit"),
        )
        return self._result(
            {"success": True, "entries": [e.to_dict() for e in entries], "count": len(entries)}
        )

    def _tool_feedback_record(self, args: Dict[str, Any]) -> Dict[str, Any]:
        token = str(args["token"])
        context = str(args.get("context", "unknown"))
        try:
            stored = self.store.record(
                token=token,
                tool=context,
                signal=str(args["signal"]),
                note=str(args.get("note", "")),
                context=context,
                condition_key=str(args.get("condition", "")),
                preferred_action=str(args.get("preferred_action", "")),
            )
        except ValueError as e:
            return self._result({"success": False, "error": str(e)}, is_error=True)
        return self._result({"success": bool(stored.get("stored")), "token": token})

    def _tool_preference_query(self, args: Dict[str, Any]) -> Dict[str, Any]:
        prefs = self.store.query(str(args["context"]), limit=int(args.get("limit", 5)))
        return self._result(
            {
                "success": True,
                "preferences": [p.to_dict() for p in prefs],
                "note": "التفضيلات تُحسن الاختيار فقط — قرارات الأمان ثابتة",
            }
        )

    # ─── البنية ────────────────────────────────────────────────────────

    def _new_token(self, tool: str, inputs: dict, outcome: dict) -> str:
        token = uuid.uuid4().hex[:16]
        try:
            self.store.record(token=token, tool=tool, signal="outcome",
                              context=tool, inputs=inputs, outcome=outcome)
        except Exception as e:  # pragma: no cover — لا تُفشل الأداة بسبب السجل
            logger.warning("تعذر تسجيل outcome: %s", e)
        return token

    def _result(
        self,
        structured: Dict[str, Any],
        token: Optional[str] = None,
        is_error: bool = False,
    ) -> Dict[str, Any]:
        text = json.dumps(structured, ensure_ascii=False, indent=2)
        meta: Dict[str, Any] = {}
        if token:
            meta["feedback_token"] = token
        result: Dict[str, Any] = {"content": [{"type": "text", "text": text}], "isError": is_error}
        if structured:
            result["structuredContent"] = structured
        if meta:
            result["_meta"] = meta
        return result

    # ─── dispatcher JSON-RPC ───────────────────────────────────────────

    def handle_request(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """يعالج رسالة JSON-RPC واحدة ويرجع الاستجابة (None للإشعارات)."""
        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params") or {}

        if method == "initialize":
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": SERVER_INFO,
                },
            }
        if method.startswith("notifications/"):
            return None
        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": _TOOL_DEFS}}
        if method == "tools/call":
            name = str(params.get("name", ""))
            if name not in _TOOL_NAMES:
                return self._rpc_error(msg_id, -32602, f"أداة غير معروفة: {name}")
            handler = getattr(self, f"_tool_{name}")
            try:
                result = handler(dict(params.get("arguments") or {}))
            except SensitiveFileBlockedError as e:
                result = self._result({"success": False, "error": str(e)}, is_error=True)
            except Exception as e:
                logger.exception("فشل الأداة %s", name)
                result = self._result({"success": False, "error": f"{type(e).__name__}: {e}"}, is_error=True)
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        if msg_id is not None:
            return self._rpc_error(msg_id, -32601, f"طريقة غير معروفة: {method}")
        return None

    @staticmethod
    def _rpc_error(msg_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}

    def serve_stdio(self) -> None:
        """حلقة stdio: سطر JSON لكل رسالة، استجابة لكل طلب."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError as e:
                sys.stdout.write(json.dumps(self._rpc_error(None, -32700, f"JSON غير صالح: {e}")) + "\n")
                sys.stdout.flush()
                continue
            response = self.handle_request(msg)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()


def _load_ruleset_from_yaml(path: str):
    from ..core.rule_schemas import Ruleset

    return Ruleset.from_yaml(path)


def _load_ruleset_from_dict(d: dict):
    from ..core.rule_schemas import Ruleset

    return Ruleset.from_dict(d)


def main() -> None:
    logging.basicConfig(level=os.environ.get("IFM_MCP_LOG_LEVEL", "WARNING"), stream=sys.stderr)
    IntelliFileMcpServer().serve_stdio()


if __name__ == "__main__":
    main()
