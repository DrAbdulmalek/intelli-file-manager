# -*- coding: utf-8 -*-
"""PreferenceEngine — محرك تفضيلات التصنيف (P1)

يحوّل تصحيحات المستخدم إلى قواعد تعلم آمنة، ويقترح وجهات بناءً عليها.
منفصل تمامًا عن التنفيذ: لا يستدعي SafeMover أو FileHandler ولا ينفّذ
أي عملية ملف — مخرجه «اقتراح» للموافقة البشرية فقط (متطلب المهمة §6).

قواعد التعلم الموثقة:
  - كل قاعدة تبدأ ``provisional``.
  - الترقية إلى ``stable`` تتطلب 3 جلسات مستقلة (جلسة مختلفة + ملف مختلف)
    — التكرار على نفس الملف/الجلسة لا يرفع الاستقلالية.
  - مصدر كل تصحيح مسجَّل (origin + feedback_ids).
  - التعارضات (نفس المفتاح، وجهات مختلفة) تُكشف وتُعرض، ولا تُحلّ تلقائيًا.
  - لا تطبيق تلقائي: ``predict`` لا يلمس الملفات؛ قرار النقل عبر بوابة
    الموافقة الحالية في التطبيق.

نطاق القاعدة (scope) بأسبقية صريحة: file (0) > directory (1) > global (2).
عند التساوي: تأكيدات مستقلة أكثر، ثم score أعلى، ثم rule_id قاموسيًا
(حتمي وقابل للاختبار).
"""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .preference_store import (
    InvalidRuleError,
    PreferenceStore,
    StoreReadOnlyError,
    new_rule_id,
)

logger = logging.getLogger(__name__)

STABLE_AFTER_INDEPENDENT_SESSIONS = 3
SCORE_PROVISIONAL = 0.5
SCORE_STABLE = 0.9

SCOPE_RANK = {"file": 0, "directory": 1, "global": 2}


@dataclass
class Suggestion:
    """اقتراح منفصل عن التنفيذ — لا يمس الملفات إطلاقًا."""
    category: str
    rule_id: str
    rule_status: str
    confidence_score: float
    independent_confirmations: int
    reason: str
    conflicts: List[str] = field(default_factory=list)
    source: str = "user_correction"
    scope_kind: str = "global"
    match_kind: str = "extension"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "rule_id": self.rule_id,
            "rule_status": self.rule_status,
            "confidence_score": self.confidence_score,
            "independent_confirmations": self.independent_confirmations,
            "reason": self.reason,
            "conflicts": list(self.conflicts),
            "source": self.source,
            "scope_kind": self.scope_kind,
            "match_kind": self.match_kind,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_extension(value: str) -> str:
    value = value.strip().lower()
    if value and not value.startswith("."):
        value = "." + value
    return value


def derive_match(metadata: Dict[str, Any],
                 explicit_kind: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """يستخرج مفتاح المطابقة من ميتاداتا الملف (بلا قراءة محتوى).

    أسبقية الاستخراج: extension ثم mime ثم name_contains.
    """
    if explicit_kind:
        if explicit_kind == "extension":
            ext = _normalize_extension(str(metadata.get("extension") or ""))
            return {"kind": "extension", "value": ext, "case_insensitive": True} if ext else None
        if explicit_kind == "mime":
            mime = str(metadata.get("mime_type") or metadata.get("content_type") or "").strip()
            return {"kind": "mime", "value": mime, "case_insensitive": True} if mime else None
        if explicit_kind == "name_contains":
            name = str(metadata.get("name") or "").strip()
            return {"kind": "name_contains", "value": name, "case_insensitive": True} if name else None
        return None
    ext = _normalize_extension(str(metadata.get("extension") or ""))
    if ext:
        return {"kind": "extension", "value": ext, "case_insensitive": True}
    mime = str(metadata.get("mime_type") or metadata.get("content_type") or "").strip()
    if mime:
        return {"kind": "mime", "value": mime, "case_insensitive": True}
    name = str(metadata.get("name") or "").strip()
    if name:
        return {"kind": "name_contains", "value": name, "case_insensitive": True}
    return None


def _rule_matches_metadata(rule: Dict[str, Any], metadata: Dict[str, Any]) -> bool:
    match = rule["match"]
    value = match["value"]
    kind = match["kind"]
    case_insensitive = match.get("case_insensitive", True)
    if kind == "extension":
        ext = _normalize_extension(str(metadata.get("extension") or ""))
        return bool(ext) and (ext == value.lower() if case_insensitive else ext == value)
    if kind == "mime":
        actual = str(metadata.get("mime_type") or metadata.get("content_type") or "")
        if not actual:
            return False
        return (actual.lower() == value.lower()) if case_insensitive else (actual == value)
    if kind == "name_contains":
        name = str(metadata.get("name") or "")
        if not name:
            return False
        return (value.lower() in name.lower()) if case_insensitive else (value in name)
    return False


class PreferenceEngine:
    """محرك قواعد التفضيل فوق PreferenceStore — بلا أي عمليات ملف."""

    def __init__(self, store: PreferenceStore):
        self.store = store
        store.load()

    # ─── الحالة ────────────────────────────────────────────────────────────

    @property
    def active(self) -> bool:
        """متاح؟ (المخزن سليم وليس read-only)."""
        return self.store.ok

    def status_report(self) -> Dict[str, Any]:
        """حالة المحرك للعرض في الواجهة (تحذير واضح عند التعطل)."""
        if self.active:
            return {"active": True, "read_only": False, "errors": []}
        return {
            "active": False,
            "read_only": self.store.read_only,
            "errors": self.store.load_errors,
            "warning": "تفضيلات التصنيف معطلة — التصنيف التقليدي الآمن يعمل بلا تعلم",
        }

    # ─── التعلم ────────────────────────────────────────────────────────────

    def record_correction(
        self,
        *,
        metadata: Dict[str, Any],
        original_category: str,
        corrected_category: str,
        session_id: str,
        file_fingerprint: str,
        origin: str = "user_correction",
        feedback_id: Optional[str] = None,
        context_directory: Optional[str] = None,
        match_kind: Optional[str] = None,
    ) -> Dict[str, Any]:
        """يسجل تصحيحًا → قاعدة provisional أو تأكيدًا لقاعدة قائمة.

        Returns:
            {noop, created, rule_id, independent_sessions, promoted, conflicts}
        """
        if not self.active:
            raise StoreReadOnlyError("المحرك غير نشط — لا تعلم بلا مخزن سليم")
        if not corrected_category or not isinstance(corrected_category, str):
            raise ValueError("corrected_category مطلوب")
        if not session_id or not file_fingerprint:
            raise ValueError("session_id وfile_fingerprint مطلوبان للاستقلالية")
        if origin not in ("user_correction", "alphacode", "import"):
            raise ValueError(f"origin غير معروف: {origin}")
        if corrected_category == original_category:
            return {"noop": True, "reason": "no_difference_to_learn"}

        match = derive_match(metadata, match_kind)
        if match is None:
            raise ValueError("لا يمكن اشتقاق مفتاح مطابقة من الميتاداتا — تعلم مرفوض")
        scope_kind, scope_value = "global", None
        if context_directory:
            scope_kind, scope_value = "directory", str(context_directory)

        existing = self._find_rule(match=match, scope_kind=scope_kind,
                                   scope_value=scope_value, destination=corrected_category)
        conflicts = self._conflict_rule_ids(match=match, scope_kind=scope_kind,
                                            scope_value=scope_value,
                                            exclude_destination=corrected_category)
        is_independent = True
        if existing:
            def mutate(rule: Dict[str, Any]) -> None:
                nonlocal is_independent
                conf = rule["confidence"]
                conf["total_confirmations"] += 1
                pairs = rule.setdefault("independent_pairs", [])
                pair = [session_id, file_fingerprint]
                if pair not in pairs:
                    pairs.append(pair)
                    conf["independent_sessions"] = len(pairs)
                    is_independent = True
                else:
                    is_independent = False
                rule.setdefault("source", {}).setdefault("feedback_ids", [])
                if feedback_id and feedback_id not in rule["source"]["feedback_ids"]:
                    rule["source"]["feedback_ids"].append(feedback_id)
                rule.setdefault("conflicts", [])
                for cid in conflicts:
                    if cid not in rule["conflicts"]:
                        rule["conflicts"].append(cid)
                rule.setdefault("history", []).append(
                    {"ts": _now_iso(), "event": "confirmation",
                     "details": f"session={session_id[:32]}"}
                )
            rule = self.store.update_rule(existing["rule_id"], mutate,
                                          change_action="rule_confirmed")
            created = False
        else:
            rule = {
                "rule_id": new_rule_id(),
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "status": "provisional",
                "match": match,
                "scope": {"kind": scope_kind, "value": scope_value},
                "destination": {"category": corrected_category},
                "confidence": {"independent_sessions": 1, "total_confirmations": 1,
                               "score": SCORE_PROVISIONAL},
                "source": {"origin": origin, "feedback_ids": [feedback_id] if feedback_id else []},
                "conflicts": list(conflicts),
                "independent_pairs": [[session_id, file_fingerprint]],
                "history": [{"ts": _now_iso(), "event": "created",
                             "details": f"session={session_id[:32]}"}],
            }
            # سجّل التعارض بالاتجاه المعاكس على القواعد المتعارضة القائمة
            for other_id in conflicts:
                self.store.update_rule(
                    other_id,
                    lambda r, nid=rule["rule_id"]: r.setdefault("conflicts", []).append(nid)
                    if nid not in r["conflicts"] else None,
                )
            rule = self.store.add_rule(rule)
            created = True

        promoted = False
        if created or (rule["status"] == "provisional"):
            promoted = self._maybe_promote(rule["rule_id"])
            rule = self.store.get_rule(rule["rule_id"]) or rule
        return {
            "noop": False,
            "created": created,
            "independent": is_independent,
            "rule_id": rule["rule_id"],
            "independent_sessions": rule["confidence"]["independent_sessions"],
            "promoted": promoted,
            "conflicts": list(rule.get("conflicts", [])),
        }

    def _maybe_promote(self, rule_id: str) -> bool:
        def mutate(rule: Dict[str, Any]) -> None:
            if (rule["status"] == "provisional"
                    and rule["confidence"]["independent_sessions"]
                    >= STABLE_AFTER_INDEPENDENT_SESSIONS):
                rule["status"] = "stable"
                rule["confidence"]["score"] = SCORE_STABLE
                rule.setdefault("history", []).append(
                    {"ts": _now_iso(), "event": "promoted_to_stable",
                     "details": f"threshold={STABLE_AFTER_INDEPENDENT_SESSIONS}"}
                )
        rule = self.store.get_rule(rule_id)
        if rule and rule["status"] == "provisional" and \
                rule["confidence"]["independent_sessions"] >= STABLE_AFTER_INDEPENDENT_SESSIONS:
            updated = self.store.update_rule(rule_id, mutate, change_action="rule_promoted")
            return updated["status"] == "stable"
        return False

    def confirm_rule(self, rule_id: str, *, session_id: str,
                     file_fingerprint: str) -> Dict[str, Any]:
        """تأكيد صريح للمستخدم على قاعدة قائمة (عدّ الاستقلالية نفسه)."""
        result = self.store.update_rule(
            rule_id,
            lambda r: (
                r["confidence"].__setitem__(
                    "total_confirmations", r["confidence"]["total_confirmations"] + 1),
                r.setdefault("independent_pairs", []).append([session_id, file_fingerprint])
                if [session_id, file_fingerprint] not in r.get("independent_pairs", [])
                else None,
                r["confidence"].__setitem__(
                    "independent_sessions", len(r.get("independent_pairs", []))),
                r.setdefault("history", []).append(
                    {"ts": _now_iso(), "event": "explicit_confirmation"}),
            ),
            change_action="rule_explicitly_confirmed",
        )
        promoted = self._maybe_promote(rule_id)
        return {"rule_id": rule_id, "promoted": promoted,
                "independent_sessions": result["confidence"]["independent_sessions"]}

    # ─── إدارة القواعد ─────────────────────────────────────────────────────

    def disable_rule(self, rule_id: str) -> Dict[str, Any]:
        """تعطيل مع حفظ الحالة السابقة لاستعادتها عند enable (لا فقدان stable)."""
        def mutate(rule: Dict[str, Any]) -> None:
            if rule["status"] == "disabled":
                return
            rule["status_before_disable"] = rule["status"]
            rule["status"] = "disabled"
            rule.setdefault("history", []).append(
                {"ts": _now_iso(), "event": "disabled"})
        return self.store.update_rule(rule_id, mutate, change_action="rule_disabled")

    def enable_rule(self, rule_id: str) -> Dict[str, Any]:
        """إعادة تفعيل إلى نفس الحالة قبل التعطيل (provisional/stable)."""
        def mutate(rule: Dict[str, Any]) -> None:
            if rule["status"] != "disabled":
                return
            rule["status"] = rule.get("status_before_disable", "provisional")
            rule.pop("status_before_disable", None)
            rule.setdefault("history", []).append(
                {"ts": _now_iso(), "event": "enabled"})
        return self.store.update_rule(rule_id, mutate, change_action="rule_enabled")

    def delete_rule(self, rule_id: str) -> Dict[str, Any]:
        """حذف منطقي (status=deleted) — قابل للتراجع عبر revert_last_update."""
        def mutate(rule: Dict[str, Any]) -> None:
            rule["status"] = "deleted"
            rule.setdefault("history", []).append(
                {"ts": _now_iso(), "event": "deleted"})
        return self.store.update_rule(rule_id, mutate, change_action="rule_deleted")

    def revert_last_update(self) -> Optional[Dict[str, Any]]:
        """تراجع عن آخر تعديل (حذف/تعطيل/تأكيد...) — من لقطة change_log."""
        return self.store.revert_last_change()

    def list_rules(self, **kwargs) -> List[Dict[str, Any]]:
        return self.store.list_rules(**kwargs)

    def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        return self.store.get_rule(rule_id)

    # ─── التنبؤ ────────────────────────────────────────────────────────────

    def predict(self, metadata: Dict[str, Any], *,
                current_path: Optional[str] = None,
                file_fingerprint: Optional[str] = None) -> Optional[Suggestion]:
        """يُرجع اقتراحًا أو None (no-op آمن). لا يمس الملفات إطلاقًا.

        - محرك معطل/مخزن غير سليم → None دائمًا.
        - القاعدة المقترحة بوجهة تساوي التصنيف الحالي → None (لا إعادة
          اقتراح نفس الشيء — اتساق applied مع suggestion).
        """
        if not self.active:
            return None
        candidates = self._applicable_rules(metadata, current_path, file_fingerprint)
        if not candidates:
            return None
        candidates.sort(key=lambda r: (
            SCOPE_RANK.get(r["scope"]["kind"], 3),
            -r["confidence"]["independent_sessions"],
            -r["confidence"]["score"],
            r["rule_id"],
        ))
        best = candidates[0]
        destination = best["destination"]["category"]
        original = str(metadata.get("category") or "")
        if destination == original:
            return None
        conflicts = sorted({
            r["rule_id"] for r in candidates[1:]
            if r["destination"]["category"] != destination
            and r["match"]["kind"] == best["match"]["kind"]
            and r["match"]["value"] == best["match"]["value"]
        })
        status = best["status"]
        if status == "stable":
            strength = "قاعدة مستقرة"
        elif status == "provisional":
            strength = "قاعدة مبدئية تحتاج تأكيدًا"
        else:
            strength = status
        match_desc = f"{best['match']['kind']}={best['match']['value']}"
        reason = (
            f"مقترح من تفضيل مستفاد من تصحيحاتك السابقة ({strength}؛ "
            f"تأكيدات مستقلة: {best['confidence']['independent_sessions']}؛ "
            f"مطابقة: {match_desc})"
        )
        return Suggestion(
            category=destination,
            rule_id=best["rule_id"],
            rule_status=status,
            confidence_score=best["confidence"]["score"],
            independent_confirmations=best["confidence"]["independent_sessions"],
            reason=reason,
            conflicts=conflicts,
            source=best.get("source", {}).get("origin", "user_correction"),
            scope_kind=best["scope"]["kind"],
            match_kind=best["match"]["kind"],
        )

    def _applicable_rules(self, metadata: Dict[str, Any],
                          current_path: Optional[str],
                          file_fingerprint: Optional[str]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for rule in self.store.list_rules():
            if rule["status"] not in ("provisional", "stable"):
                continue
            scope = rule["scope"]
            if scope["kind"] == "file":
                if not file_fingerprint or scope["value"] != file_fingerprint:
                    continue
            elif scope["kind"] == "directory":
                if not current_path or scope["value"] != str(current_path):
                    continue
            if not _rule_matches_metadata(rule, metadata):
                continue
            out.append(rule)
        return out

    def _find_rule(self, *, match: Dict[str, Any], scope_kind: str,
                   scope_value: Optional[str],
                   destination: str) -> Optional[Dict[str, Any]]:
        for rule in self.store.list_rules(include_disabled=True):
            if rule["status"] == "deleted":
                continue
            if rule["match"] == match and rule["scope"]["kind"] == scope_kind \
                    and rule["scope"]["value"] == scope_value \
                    and rule["destination"]["category"] == destination:
                return rule
        return None

    def _conflict_rule_ids(self, *, match: Dict[str, Any], scope_kind: str,
                           scope_value: Optional[str],
                           exclude_destination: str) -> List[str]:
        return [
            r["rule_id"] for r in self.store.list_rules(include_disabled=True)
            if r["status"] != "deleted" and r["match"] == match
            and r["scope"]["kind"] == scope_kind
            and r["scope"]["value"] == scope_value
            and r["destination"]["category"] != exclude_destination
        ]

    # ─── الشرح ─────────────────────────────────────────────────────────────

    def explain_suggestion(self, suggestion: Suggestion) -> Dict[str, Any]:
        """شرح كامل للاقتراح للعرض في الواجهة/الـAdapter."""
        rule = self.get_rule(suggestion.rule_id) or {}
        history = rule.get("history", [])[-5:]
        return {
            "category": suggestion.category,
            "rule_id": suggestion.rule_id,
            "rule_status": suggestion.rule_status,
            "confidence_score": suggestion.confidence_score,
            "independent_confirmations": suggestion.independent_confirmations,
            "conflicts": suggestion.conflicts,
            "source": suggestion.source,
            "scope": rule.get("scope", {}),
            "match": rule.get("match", {}),
            "reason": suggestion.reason,
            "origin_feedback_ids": rule.get("source", {}).get("feedback_ids", []),
            "recent_history": history,
            "note": "الاقتراح لا ينفّذ أي عملية — النقل يحتاج موافقة صريحة",
        }
