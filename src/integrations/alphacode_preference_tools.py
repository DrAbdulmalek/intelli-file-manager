# -*- coding: utf-8 -*-
"""أدوات تفضيلات التصنيف لجسر AlphaCode (MCP) — محلي بالكامل (P2)

توسّع الخادم الموجود ``alphacode_mcp_server`` بسبع أدوات تعمل على
مخزن التفضيلات المحلي فقط، دون أي أداة نقل/حذف/تنفيذ:

    intellifile.get_suggestion / record_user_correction / explain_rule /
    list_applicable_rules / confirm_rule / disable_rule / enable_rule

حدود الأمان (متطلب المهمة §8):
  - النقل stdio محلي: هوية العميل = مستخدم نظام التشغيل صاحب الأنبوب —
    لا منفذ شبكي يُفتح إطلاقًا (أقصر من "localhost فقط").
  - لا shell، لا subprocess، لا عمليات ملف، لا cloud fallback.
  - لا يُقرأ محتوى أي ملف؛ الميتاداتا التي يرسلها العميل فقط.
  - ``record_user_correction`` يُنشئ feedback + مرشحًا للمراجعة؛ التطبيق
    الفعلي يتطلب ``user_confirmed=true`` صريحًا من الإنسان عبر العميل —
    بلا هذا العلم تبقى الملاحظة pending_review ولا تتعلم.
  - سجل عمليات مُجرَّد (اختياري عبر IFM_ADAPTER_OPS_LOG): الوقت/الأداة/
    النتيجة فقط — بلا حقول payload.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.config import CATEGORIES, Config
from src.core.feedback_engine import FeedbackEngine, fingerprint_path
from src.core.preference_engine import PreferenceEngine, Suggestion
from src.core.preference_store import PreferenceStore

logger = logging.getLogger(__name__)

MAX_SESSION_LEN = 128
MAX_CATEGORY_LEN = 100
MAX_METADATA_KEYS = 32
MAX_METADATA_VALUE_LEN = 200

_PREFERENCE_TOOL_NAMES = (
    "intellifile.get_suggestion",
    "intellifile.record_user_correction",
    "intellifile.confirm_feedback",
    "intellifile.dismiss_feedback",
    "intellifile.explain_rule",
    "intellifile.list_applicable_rules",
    "intellifile.confirm_rule",
    "intellifile.disable_rule",
    "intellifile.enable_rule",
)


class PreferenceIntegrationError(ValueError):
    """خطأ آمن قابل للعرض للعميل."""


def _default_store_path() -> Path:
    raw = os.environ.get("IFM_PREFERENCES_JSON", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".intellifile" / "preferences.json"


def _default_feedback_path(store_path: Path) -> Path:
    raw = os.environ.get("IFM_FEEDBACK_JSONL", "").strip()
    if raw:
        return Path(raw).expanduser()
    return store_path.parent / "feedback_log.jsonl"


def _ops_log_path() -> Optional[Path]:
    raw = os.environ.get("IFM_ADAPTER_OPS_LOG", "").strip()
    return Path(raw).expanduser() if raw else None


def _ops_log(tool: str, ok: bool, error_kind: str = "") -> None:
    """سجل عمليات مُجرَّد — لا حقول payload إطلاقًا (خصوصية)."""
    path = _ops_log_path()
    if path is None:
        return
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": tool,
        "ok": bool(ok),
    }
    if error_kind:
        entry["error_kind"] = error_kind[:80]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:  # لا يُسمح لفشل السجل بكسر الأداة
        logger.debug("ops log فشل: %s", exc)


def _clean_metadata(metadata: Any) -> Dict[str, Any]:
    """تنقية ميتاداتا العميل: حقول محدودة، قيم قصيرة، بلا مسارات كاملة."""
    if not isinstance(metadata, dict):
        raise PreferenceIntegrationError("metadata must be an object")
    if len(metadata) > MAX_METADATA_KEYS:
        raise PreferenceIntegrationError("metadata has too many keys")
    cleaned: Dict[str, Any] = {}
    allowed = {"name", "extension", "mime_type", "content_type", "category"}
    for key, value in metadata.items():
        if key not in allowed:
            continue  # يُسقط بصمت — العميل قد يرسل حقولاً إضافية حساسة
        if isinstance(value, str):
            cleaned[key] = value[:MAX_METADATA_VALUE_LEN]
        elif isinstance(value, (int, float)) :
            cleaned[key] = value
    if not cleaned:
        raise PreferenceIntegrationError(
            "metadata needs at least one usable field (name/extension/mime_type)")
    return cleaned


def _require_session(args: Dict[str, Any]) -> str:
    session = args.get("source_session")
    if not isinstance(session, str):
        raise PreferenceIntegrationError("source_session is required")
    session = session.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", session):
        raise PreferenceIntegrationError("source_session must be an opaque token")
    return session


def _require_rule_id(args: Dict[str, Any]) -> str:
    rule_id = args.get("rule_id")
    if not isinstance(rule_id, str) or not rule_id.strip():
        raise PreferenceIntegrationError("rule_id is required")
    return rule_id.strip()


class PreferenceToolkit:
    """جسر بين أدوات MCP ومحرك التفضيلات — بلا أي عملية ملف."""

    def __init__(self, store_path: Optional[Path] = None,
                 feedback_path: Optional[Path] = None,
                 allowed_categories: Optional[list[str]] = None):
        self.store_path = store_path or _default_store_path()
        self.feedback_path = feedback_path or _default_feedback_path(self.store_path)
        if allowed_categories is None:
            try:
                allowed_categories = Config.load().categories
            except Exception:
                allowed_categories = CATEGORIES
        self.allowed_categories = tuple(
            dict.fromkeys(item.strip() for item in allowed_categories
                          if isinstance(item, str) and item.strip())
        )
        self._engine: Optional[PreferenceEngine] = None
        self._feedback: Optional[FeedbackEngine] = None

    @property
    def engine(self) -> PreferenceEngine:
        if self._engine is None:
            self._engine = PreferenceEngine(PreferenceStore(self.store_path))
        return self._engine

    @property
    def feedback(self) -> FeedbackEngine:
        if self._feedback is None:
            self._feedback = FeedbackEngine(
                self.engine, self.feedback_path,
                allowed_categories=list(self.allowed_categories),
            )
        return self._feedback

    # ─── المعالجات ─────────────────────────────────────────────────────────

    def handle(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """يوزّع أداة تفضيل إلى معالجها ويسجل العملية مُجرَّدة."""
        try:
            result = self._dispatch(tool_name, args)
            _ops_log(tool_name, True)
            return result
        except PreferenceIntegrationError as exc:
            _ops_log(tool_name, False, "invalid_payload")
            raise
        except (ValueError, OSError, RuntimeError) as exc:
            _ops_log(tool_name, False, type(exc).__name__)
            raise PreferenceIntegrationError(str(exc)[:300]) from exc

    def _dispatch(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "intellifile.get_suggestion":
            return self._get_suggestion(args)
        if tool_name == "intellifile.record_user_correction":
            return self._record_user_correction(args)
        if tool_name == "intellifile.confirm_feedback":
            return self._confirm_feedback(args)
        if tool_name == "intellifile.dismiss_feedback":
            return self._dismiss_feedback(args)
        if tool_name == "intellifile.explain_rule":
            return self._explain_rule(args)
        if tool_name == "intellifile.list_applicable_rules":
            return self._list_applicable_rules(args)
        if tool_name == "intellifile.confirm_rule":
            return self._confirm_rule(args)
        if tool_name == "intellifile.disable_rule":
            return self._set_rule_status(args, "disable")
        if tool_name == "intellifile.enable_rule":
            return self._set_rule_status(args, "enable")
        raise PreferenceIntegrationError(f"Unknown preference tool: {tool_name}")

    def _fingerprint(self, args: Dict[str, Any]) -> str:
        fp = args.get("file_fingerprint")
        if isinstance(fp, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}", fp.strip()):
            return fp.strip()
        path = args.get("file_path")
        if isinstance(path, str) and path.strip():
            return fingerprint_path(path)  # تجزئة — المسار نفسه لا يُخزَّن
        raise PreferenceIntegrationError("file_fingerprint or file_path is required")

    def _get_suggestion(self, args: Dict[str, Any]) -> Dict[str, Any]:
        metadata = _clean_metadata(args.get("metadata"))
        fingerprint = self._fingerprint(args)
        current_path = args.get("current_path")
        suggestion = self.engine.predict(
            metadata,
            current_path=current_path if isinstance(current_path, str) else None,
            file_fingerprint=fingerprint,
        )
        if suggestion is None:
            return {"suggestion": None, "preferences_active": self.engine.active}
        return {
            "suggestion": suggestion.to_dict(),
            "preferences_active": True,
            "note": "اقتراح فقط — لا ينفّذ أي عملية ملف",
        }

    def _record_user_correction(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a pending preview only; a separate call is required to apply."""
        metadata = _clean_metadata(args.get("metadata"))
        session = _require_session(args)
        fingerprint = self._fingerprint(args)
        original = args.get("original_prediction")
        if not isinstance(original, str):
            original = ""
        corrected = args.get("corrected_value")
        if not isinstance(corrected, str) or not corrected.strip():
            raise PreferenceIntegrationError("corrected_value is required")
        corrected = corrected.strip()[:MAX_CATEGORY_LEN]

        safe_metadata = {
            "extension": metadata.get("extension"),
            "mime_type": metadata.get("mime_type") or metadata.get("content_type"),
        }
        safe_metadata = {key: value for key, value in safe_metadata.items()
                         if isinstance(value, str) and value.strip()}
        if not safe_metadata:
            raise PreferenceIntegrationError(
                "a safe extension or MIME type is required for learning"
            )

        record = self.feedback.capture(
            user_action="correct",
            original_prediction=original,
            session_id=f"alphacode:{session}",
            file_fingerprint=fingerprint,
            corrected_value=corrected,
            evidence=safe_metadata,
            source_rule_id=args.get("source_rule_id"),
        )
        candidate = record.get("candidate") or {}
        return {
            "feedback_id": record["feedback_id"],
            "review_status": record["review_status"],
            "applied": None,
            "preview": {
                "original_category": original or None,
                "corrected_category": corrected,
                "match": candidate.get("match"),
                "conflict": bool(candidate.get("conflict_with_existing", False)),
                "requires_explicit_confirmation": True,
                "file_operations": False,
            },
            "note": "لم تُطبّق القاعدة؛ راجع المعاينة ثم استدعِ confirm_feedback بموافقة صريحة",
        }

    def _confirm_feedback(self, args: Dict[str, Any]) -> Dict[str, Any]:
        feedback_id = args.get("feedback_id")
        if not isinstance(feedback_id, str) or not feedback_id.strip():
            raise PreferenceIntegrationError("feedback_id is required")
        if args.get("user_confirmed") is not True:
            raise PreferenceIntegrationError("explicit_user_confirmation_required")
        self.feedback.confirm(feedback_id.strip())
        applied = self.feedback.apply_confirmed(feedback_id.strip())
        return {
            "feedback_id": feedback_id.strip(),
            "review_status": applied["review_status"],
            "applied": applied,
            "note": "تم تطبيق قاعدة تفضيل محلية بعد موافقة منفصلة؛ لم تُنفّذ أي عملية ملف",
        }

    def _dismiss_feedback(self, args: Dict[str, Any]) -> Dict[str, Any]:
        feedback_id = args.get("feedback_id")
        if not isinstance(feedback_id, str) or not feedback_id.strip():
            raise PreferenceIntegrationError("feedback_id is required")
        return self.feedback.dismiss(feedback_id.strip())

    def _explain_rule(self, args: Dict[str, Any]) -> Dict[str, Any]:
        rule_id = _require_rule_id(args)
        rule = self.engine.get_rule(rule_id)
        if rule is None:
            raise PreferenceIntegrationError(f"rule not found: {rule_id}")
        explanation = self.engine.explain_suggestion(
            Suggestion(
                category=rule["destination"]["category"],
                rule_id=rule["rule_id"],
                rule_status=rule["status"],
                confidence_score=rule["confidence"]["score"],
                independent_confirmations=rule["confidence"]["independent_sessions"],
                reason="",
            )
        )
        return {"rule": rule, "explanation": explanation}

    def _list_applicable_rules(self, args: Dict[str, Any]) -> Dict[str, Any]:
        metadata = _clean_metadata(args.get("metadata"))
        from src.core.preference_engine import _rule_matches_metadata
        applicable = []
        for rule in self.engine.list_rules():
            if _rule_matches_metadata(rule, metadata):
                applicable.append({
                    "rule_id": rule["rule_id"],
                    "status": rule["status"],
                    "match": rule["match"],
                    "scope": rule["scope"],
                    "destination": rule["destination"]["category"],
                    "independent_sessions": rule["confidence"]["independent_sessions"],
                    "conflicts": rule.get("conflicts", []),
                })
        return {"applicable": applicable, "count": len(applicable)}

    def _confirm_rule(self, args: Dict[str, Any]) -> Dict[str, Any]:
        rule_id = _require_rule_id(args)
        session = _require_session(args)
        fingerprint = self._fingerprint(args)
        result = self.engine.confirm_rule(rule_id, session_id=f"alphacode:{session}",
                                          file_fingerprint=fingerprint)
        return {"rule_id": rule_id, **result}

    def _set_rule_status(self, args: Dict[str, Any], mode: str) -> Dict[str, Any]:
        rule_id = _require_rule_id(args)
        rule = (self.engine.disable_rule(rule_id) if mode == "disable"
                else self.engine.enable_rule(rule_id))
        return {"rule_id": rule_id, "status": rule["status"]}


# ─── تعريفات الأدوات (MCP) ──────────────────────────────────────────────────

_PREF_METADATA_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "extension": {"type": "string"},
        "mime_type": {"type": "string"},
        "content_type": {"type": "string"},
        "category": {"type": "string"},
    },
    "additionalProperties": False,
}

PREFERENCE_TOOLS = [
    {
        "name": "intellifile.get_suggestion",
        "description": "Return the learned classification suggestion for file metadata, or null. Read-only; never performs file operations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "metadata": _PREF_METADATA_SCHEMA,
                "file_fingerprint": {"type": "string"},
                "file_path": {"type": "string",
                              "description": "hashed locally; the raw path is never stored"},
                "current_path": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "intellifile.record_user_correction",
        "description": "Record a human classification correction and return a safe preview. Never applies a rule in this call; use confirm_feedback as a separate explicit approval step. Mutates local feedback only, never files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "metadata": _PREF_METADATA_SCHEMA,
                "original_prediction": {"type": "string"},
                "corrected_value": {
                    "type": "string",
                    "description": "Must match a configured category; this call creates a pending preview only.",
                },
                "source_session": {"type": "string"},
                "file_fingerprint": {"type": "string"},
                "file_path": {"type": "string"},
            },
            "required": ["metadata", "corrected_value", "source_session"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "intellifile.explain_rule",
        "description": "Explain a stored preference rule (status, confidence, conflicts, origin). Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {"rule_id": {"type": "string"}},
            "required": ["rule_id"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "intellifile.list_applicable_rules",
        "description": "List stored preference rules matching the given metadata. Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {"metadata": _PREF_METADATA_SCHEMA},
            "required": ["metadata"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "intellifile.confirm_rule",
        "description": "Explicitly confirm an existing preference rule (raises independent confirmations, may promote to stable). Mutates the local preference store, never files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rule_id": {"type": "string"},
                "source_session": {"type": "string"},
                "file_fingerprint": {"type": "string"},
                "file_path": {"type": "string"},
            },
            "required": ["rule_id", "source_session"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "intellifile.disable_rule",
        "description": "Disable a preference rule (previous status kept for re-enable). Mutates the local preference store, never files.",
        "inputSchema": {
            "type": "object",
            "properties": {"rule_id": {"type": "string"}},
            "required": ["rule_id"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "intellifile.enable_rule",
        "description": "Re-enable a disabled preference rule restoring its previous status. Mutates the local preference store, never files.",
        "inputSchema": {
            "type": "object",
            "properties": {"rule_id": {"type": "string"}},
            "required": ["rule_id"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "intellifile.confirm_feedback",
        "description": "Apply one previously previewed feedback candidate only after a separate explicit human approval. Mutates local preferences, never files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "feedback_id": {"type": "string"},
                "user_confirmed": {"type": "boolean"},
            },
            "required": ["feedback_id", "user_confirmed"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "intellifile.dismiss_feedback",
        "description": "Dismiss a pending feedback candidate without changing learned preferences.",
        "inputSchema": {
            "type": "object",
            "properties": {"feedback_id": {"type": "string"}},
            "required": ["feedback_id"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
]


def is_preference_tool(name: Any) -> bool:
    return isinstance(name, str) and name in _PREFERENCE_TOOL_NAMES


def create_toolkit() -> PreferenceToolkit:
    """مصنع واحد لكل عملية خادم — المسارات من البيئة أو الافتراضي المحلي."""
    return PreferenceToolkit()
