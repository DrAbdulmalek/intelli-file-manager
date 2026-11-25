# -*- coding: utf-8 -*-
"""FeedbackEngine — حلقة ملاحظات المستخدم لتعلم التفضيلات (P1)

دورة العمل الموثقة (متطلب المهمة §5):

    User Action → Feedback Capture → Feedback Classification →
    Source Attribution → Duplicate Detection → Rule Candidate
    Generation → User Review → Explicit Confirmation →
    Preference Engine Update

مبادئ ثابتة:
  - سجل الـfeedback **ملف JSONL منفصل append-only** عن ملف قواعد التفضيل
    (لا يُعاد كتابته أبدًا؛ تحديث الحالة يُلحق كسطر جديد والأحدث يفوز).
  - الرفض (reject) لا يولّد قاعدة تعلم إطلاقًا.
  - التصحيح (correct) يولّد **مرشحًا للمراجعة** فقط — لا يُطبَّق على
    محرك التفضيلات إلا عبر ``apply_confirmed`` بعد موافقة صريحة.
  - التصحيح المؤقت (temp_override) لا يرقّى لقاعدة أبديًا.
  - كشف التكرار: تكرار غير مستقل (نفس الجلسة/الملف/الفعل/القيمة) لا يرفع
    الاستقلالية عند التطبيق.
  - التعارض: قيمة مصححة تخالف وجهة قاعدة قائمة على نفس المفتاح →
    راية تعارض في السجل.
  - خصوصية الأدلة: ``_sanitize_evidence`` قائمة بيضاء — أي حقل مسار/اسم/
    محتوى يُسقط؛ لا يُسجل محتوى الملفات الطبية أو الشخصية أبدًا.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import CATEGORIES
from .preference_engine import PreferenceEngine

logger = logging.getLogger(__name__)

USER_ACTIONS = (
    "accept",             # قبول التصنيف (يقوي القاعدة المسؤولة إن وجدت)
    "reject",             # رفض التصنيف — لا تعلم إطلاقًا
    "correct",            # تصحيح التصنيف — مرشح للمراجعة
    "set_destination",    # تغيير وجهة الملف — مرشح للمراجعة
    "file_exception",     # استثناء خاص بهذا الملف فقط — مرشح بنطاق file
    "temp_override",      # تصحيح مؤقت — لا قاعدة أبدية
    "general_preference", # تفضيل عام — مرشح بنطاق global
)

REVIEW_STATUSES = ("pending_review", "confirmed", "applied", "dismissed")

_EVIDENCE_WHITELIST = {"extension", "mime_type", "size_bucket", "is_dir"}
_SENSITIVE_EVIDENCE_KEYS = {"path", "name", "file_name", "content", "text",
                            "preview", "parent_dir", "file_path"}
_SAFE_SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAFE_FINGERPRINT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_SAFE_EXTENSION_RE = re.compile(r"^\.[a-z0-9][a-z0-9._+-]{0,15}$")
_SAFE_MIME_RE = re.compile(
    r"^[a-z0-9][a-z0-9!#$&^_.+-]{0,63}/[a-z0-9][a-z0-9!#$&^_.+-]{0,63}$"
)

APP_VERSION = "unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_feedback_id() -> str:
    return uuid.uuid4().hex


def sanitize_evidence(evidence: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Keep only bounded, machine-readable file-type evidence."""
    if not isinstance(evidence, dict):
        return {}
    clean: Dict[str, Any] = {}
    for key in _EVIDENCE_WHITELIST:
        if key not in evidence:
            continue
        value = evidence[key]
        if key == "extension":
            if not isinstance(value, str):
                continue
            value = value.strip().lower()
            if value and not value.startswith("."):
                value = "." + value
            if value and _SAFE_EXTENSION_RE.fullmatch(value):
                clean[key] = value
        elif key == "mime_type":
            if not isinstance(value, str):
                continue
            value = value.strip().lower()
            if _SAFE_MIME_RE.fullmatch(value):
                clean[key] = value
        elif key == "size_bucket":
            if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 10:
                clean[key] = value
            elif isinstance(value, str) and value in {"tiny", "small", "medium", "large", "unknown"}:
                clean[key] = value
        elif key == "is_dir" and isinstance(value, bool):
            clean[key] = value
    return clean

def fingerprint_path(path: str) -> str:
    """بصمة المسار (sha256) — يسمح بالتفرد دون تسجيل المسار نفسه."""
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()


class FeedbackEngine:
    """محرّك الملاحظات — تسجيل وتصنيف وترشيح، بلا أي عملية ملف."""

    def __init__(self, engine: PreferenceEngine,
                 log_path: Optional[str | Path] = None, *,
                 allowed_categories: Optional[List[str]] = None):
        self.engine = engine
        self.log_path = Path(log_path) if log_path else \
            engine.store.path.parent / "feedback_log.jsonl"
        source_categories = CATEGORIES if allowed_categories is None else allowed_categories
        self.allowed_categories = tuple(dict.fromkeys(
            " ".join(item.split()).strip()
            for item in source_categories
            if isinstance(item, str) and item.strip()
        ))
        self._thread_lock = threading.RLock()
        self._dup_signatures: set = set()
        self._index: Dict[str, Dict[str, Any]] = {}
        self._load_index()

    def _validated_category(self, label: Optional[str]) -> Optional[str]:
        if label is None or label == "":
            return None
        normalized = " ".join(label.split()).strip() if isinstance(label, str) else ""
        if normalized not in self.allowed_categories:
            raise ValueError("category_not_in_configured_catalog")
        return normalized

    def category_label(self, category_id: Optional[str]) -> Optional[str>:
        if not category_id:
            return None
        return self.engine.store.get_category_label(category_id)

    # ─── الفهرسة من السجل ──────────────────────────────────────────────────

    def _load_index(self) -> None:
        if not self.log_path.exists():
            return
        try:
            with open(self.log_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    self._absorb(record)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("feedback log غير مقروء كاملاً (تُستأنف السجلات الجديدة فقط): %s",
                           exc)

    def _absorb(self, record: Dict[str, Any]) -> None:
        kind = record.get("type", "feedback")
        if kind == "feedback":
            fid = record.get("feedback_id", "")
            if fid:
                self._index[fid] = record
                self._dup_signatures.add(self._signature(record))
        elif kind == "review_update" and record.get("feedback_id"):
            fid = record["feedback_id"]
            if fid in self._index:
                self._index[fid]["review_status"] = record.get(
                    "review_status", self._index[fid]["review_status"])
                if record.get("rule_id"):
                    self._index[fid]["applied_rule_id"] = record["rule_id"]

    @staticmethod
    def _signature(record: Dict[str, Any]) -> tuple:
        return (
            record.get("source_session", ""),
            record.get("file_fingerprint", ""),
            record.get("user_action", ""),
            record.get("corrected_category_id", record.get("corrected_value", "")),
        )

    # ─── الالتقاط ──────────────────────────────────────────────────────────

    def capture(self, *, user_action: str, original_prediction: str,
                session_id: str, file_fingerprint: str,
                corrected_value: Optional[str] = None,
                source_rule_id: Optional[str] = None,
                evidence: Optional[Dict[str, Any]] = None,
                application_version: str = APP_VERSION) -> Dict[str, Any]:
        """Capture categorical feedback without persisting display labels or payloads."""
        if user_action not in USER_ACTIONS:
            raise ValueError("unknown_user_action")
        if not isinstance(session_id, str) or not _SAFE_SESSION_RE.fullmatch(session_id):
            raise ValueError("source_session_must_be_opaque_token")
        if not isinstance(file_fingerprint, str) or not _SAFE_FINGERPRINT_RE.fullmatch(file_fingerprint):
            raise ValueError("file_fingerprint_must_be_opaque_token")
        if source_rule_id is not None and (
            not isinstance(source_rule_id, str)
            or not _SAFE_SESSION_RE.fullmatch(source_rule_id)
        ):
            raise ValueError("source_rule_id_invalid")

        original_label = self._validated_category(original_prediction)
        corrected_label = self._validated_category(corrected_value)
        original_category_id = (
            self.engine.store.register_category(original_label) if original_label else None
        )
        corrected_category_id = (
            self.engine.store.register_category(corrected_label) if corrected_label else None
        )
        safe_evidence = sanitize_evidence(evidence)
        safe_version = (
            application_version if isinstance(application_version, str)
            and _SAFE_SESSION_RE.fullmatch(application_version) else APP_VERSION
        )
        record: Dict[str, Any] = {
            "type": "feedback",
            "feedback_id": new_feedback_id(),
            "timestamp": _now_iso(),
            "source_session": session_id,
            "file_fingerprint": file_fingerprint,
            "original_category_id": original_category_id,
            "user_action": user_action,
            "corrected_category_id": corrected_category_id,
            "source_rule_id": source_rule_id,
            "application_version": safe_version,
            "evidence": safe_evidence,
            "review_status": "pending_review",
            "duplicate": False,
            "conflict": False,
            "candidate": None,
        }

        signature = self._signature(record)
        with self._thread_lock:
            if signature in self._dup_signatures:
                record["duplicate"] = True

        if user_action == "reject":
            record["review_status"] = "dismissed"
        elif user_action == "temp_override":
            record["review_status"] = "dismissed"
        elif user_action == "accept":
            if source_rule_id:
                record["review_status"] = "confirmed"
            else:
                record["review_status"] = "dismissed"
        else:
            if corrected_category_id is None:
                record["review_status"] = "dismissed"
                record["candidate_note"] = "corrected_category_required"
            else:
                candidate = self._candidate_from(record)
                if candidate is None:
                    record["review_status"] = "dismissed"
                    record["candidate_note"] = "safe_extension_or_mime_evidence_required"
                else:
                    record["candidate"] = candidate

        with self._thread_lock:
            self._append(record)
            self._absorb(record)
        return copy.deepcopy(record)

    def _candidate_from(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Build a review candidate from safe extension/MIME evidence only."""
        category_id = record.get("corrected_category_id")
        category_label = self.engine.store.get_category_label(category_id)
        if not category_id or not category_label:
            return None
        evidence = record["evidence"]
        ext = evidence.get("extension")
        mime = evidence.get("mime_type")
        if ext:
            match: Dict[str, Any] = {"kind": "extension", "value": ext,
                                     "case_insensitive": True}
        elif mime:
            match = {"kind": "mime", "value": mime, "case_insensitive": True}
        else:
            return None

        conflict = False
        if self.engine.active:
            for rule in self.engine.list_rules(include_disabled=True):
                if rule["status"] != "deleted" and rule["match"] == match \
                        and rule["destination"]["category"] != category_label:
                    conflict = True
                    break
        scope_kind = "file" if record["user_action"] == "file_exception" else "global"
        return {
            "match": match,
            "scope_kind": scope_kind,
            "scope_value": record["file_fingerprint"] if scope_kind == "file" else None,
            "destination_category_id": category_id,
            "requires_explicit_confirmation": True,
            "conflict_with_existing": conflict,
            "duplicate": record["duplicate"],
        }

    def _append(self, record: Dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            import os
            os.fsync(fh.fileno())

    # ─── المراجعة والتطبيق ─────────────────────────────────────────────────

    def confirm(self, feedback_id: str) -> Dict[str, Any]:
        """Explicitly approve a pending candidate; no rule is written here."""
        with self._thread_lock:
            base = self._index.get(feedback_id)
            if not base:
                raise ValueError("feedback_not_found")
            if base.get("review_status") != "pending_review" or not base.get("candidate"):
                raise ValueError("feedback_not_approvable")
            update = {
                "type": "review_update",
                "feedback_id": feedback_id,
                "review_status": "confirmed",
                "ts": _now_iso(),
            }
            self._append(update)
            self._absorb(update)
            return {"feedback_id": feedback_id, "review_status": "confirmed"}

    def dismiss(self, feedback_id: str) -> Dict[str, Any]:
        """Dismiss a pending candidate without changing learned preferences."""
        with self._thread_lock:
            base = self._index.get(feedback_id)
            if not base:
                raise ValueError("feedback_not_found")
            if base.get("review_status") != "pending_review":
                raise ValueError("feedback_not_dismissible")
            update = {
                "type": "review_update",
                "feedback_id": feedback_id,
                "review_status": "dismissed",
                "ts": _now_iso(),
            }
            self._append(update)
            self._absorb(update)
            return {"feedback_id": feedback_id, "review_status": "dismissed"}

    def apply_confirmed(self, feedback_id: str, *,
                        metadata: Optional[Dict[str, Any]] = None,
                        original_category: Optional[str] = None,
                        session_id: Optional[str] = None,
                        file_fingerprint: Optional[str] = None) -> Dict[str, Any]:
        """Apply a confirmed candidate using only stored categorical evidence."""
        with self._thread_lock:
            record = self._index.get(feedback_id)
            if not record:
                raise ValueError("feedback_not_found")
            if record.get("review_status") != "confirmed":
                raise ValueError("explicit_confirmation_required")
            if not record.get("candidate"):
                raise ValueError("safe_candidate_required")

            corrected_category = self.engine.store.get_category_label(
                record.get("corrected_category_id")
            )
            if corrected_category is None:
                # Read compatibility only for pre-v2 local records.
                corrected_category = record.get("corrected_value")
            if not isinstance(corrected_category, str) or not corrected_category:
                raise ValueError("corrected_category_unavailable")

            safe_metadata: Dict[str, Any] = {}
            for key in ("extension", "mime_type"):
                value = record.get("evidence", {}).get(key)
                if isinstance(value, str) and value:
                    safe_metadata[key] = value
            if isinstance(metadata, dict):
                for key in ("extension", "mime_type", "content_type"):
                    value = metadata.get(key)
                    if isinstance(value, str) and value:
                        safe_metadata["mime_type" if key == "content_type" else key] = value
            if not safe_metadata:
                raise ValueError("safe_extension_or_mime_evidence_required")

            if original_category is None:
                original_category = self.engine.store.get_category_label(
                    record.get("original_category_id")
                ) or record.get("original_prediction")
            if not isinstance(original_category, str) or not original_category:
                raise ValueError("original_category_unavailable")
            session_id = session_id or record.get("source_session")
            file_fingerprint = file_fingerprint or record.get("file_fingerprint")
            if not isinstance(session_id, str) or not _SAFE_SESSION_RE.fullmatch(session_id):
                raise ValueError("source_session_invalid")
            if not isinstance(file_fingerprint, str) or not _SAFE_FINGERPRINT_RE.fullmatch(file_fingerprint):
                raise ValueError("file_fingerprint_invalid")

            result = self.engine.record_correction(
                metadata=safe_metadata,
                original_category=original_category,
                corrected_category=corrected_category,
                session_id=session_id,
                file_fingerprint=file_fingerprint,
                origin="alphacode" if record.get("source_session", "").startswith("alphacode:")
                else "user_correction",
                feedback_id=feedback_id,
            )
            update = {
                "type": "review_update",
                "feedback_id": feedback_id,
                "review_status": "applied",
                "ts": _now_iso(),
                "rule_id": result.get("rule_id"),
            }
            self._append(update)
            self._absorb(update)
            return {"feedback_id": feedback_id, "review_status": "applied",
                    "engine_result": result}

    # ─── القراءة ───────────────────────────────────────────────────────────

    @staticmethod
    def _public_record(record: Dict[str, Any]) -> Dict[str, Any]:
        public = copy.deepcopy(record)
        legacy_fields = False
        for key in ("original_prediction", "corrected_value"):
            if key in public:
                public.pop(key, None)
                legacy_fields = True
        candidate = public.get("candidate")
        if isinstance(candidate, dict) and "destination_category" in candidate:
            candidate.pop("destination_category", None)
            legacy_fields = True
        if legacy_fields:
            public["legacy_category_values_redacted"] = True
        return public

    def get_feedback(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        with self._thread_lock:
            record = self._index.get(feedback_id)
            return self._public_record(record) if record else None

    def list_feedback(self, *, review_status: Optional[str] = None,
                      limit: int = 200) -> List[Dict[str, Any]]:
        with self._thread_lock:
            records = list(self._index.values())
        if review_status:
            records = [r for r in records if r["review_status"] == review_status]
        records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
        return [self._public_record(record) for record in records[:limit]]
