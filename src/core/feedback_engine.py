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
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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

APP_VERSION = "unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_feedback_id() -> str:
    return uuid.uuid4().hex


def sanitize_evidence(evidence: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """قائمة بيضاء صارمة: الحقول غير المدرجة (أي مسار/اسم/محتوى) تُسقط."""
    if not isinstance(evidence, dict):
        return {}
    clean: Dict[str, Any] = {}
    for key in _EVIDENCE_WHITELIST:
        if key in evidence:
            value = evidence[key]
            if key == "extension":
                value = str(value).lower()
                if value and not value.startswith("."):
                    value = "." + value
            if isinstance(value, (str, int, float, bool)) or value is None:
                clean[key] = value
    return clean


def fingerprint_path(path: str) -> str:
    """بصمة المسار (sha256) — يسمح بالتفرد دون تسجيل المسار نفسه."""
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()


class FeedbackEngine:
    """محرّك الملاحظات — تسجيل وتصنيف وترشيح، بلا أي عملية ملف."""

    def __init__(self, engine: PreferenceEngine,
                 log_path: Optional[str | Path] = None):
        self.engine = engine
        self.log_path = Path(log_path) if log_path else \
            engine.store.path.parent / "feedback_log.jsonl"
        self._thread_lock = threading.RLock()
        self._dup_signatures: set = set()
        self._index: Dict[str, Dict[str, Any]] = {}
        self._load_index()

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
                self._index[fid]["review_status"] = record.get("review_status",
                                                               self._index[fid]["review_status"])

    @staticmethod
    def _signature(record: Dict[str, Any]) -> tuple:
        return (
            record.get("source_session", ""),
            record.get("file_fingerprint", ""),
            record.get("user_action", ""),
            record.get("corrected_value", ""),
        )

    # ─── الالتقاط ──────────────────────────────────────────────────────────

    def capture(self, *, user_action: str, original_prediction: str,
                session_id: str, file_fingerprint: str,
                corrected_value: Optional[str] = None,
                source_rule_id: Optional[str] = None,
                evidence: Optional[Dict[str, Any]] = None,
                application_version: str = APP_VERSION) -> Dict[str, Any]:
        """يلتقط ملاحظة، يصنفها، يكشف التكرار، ويرجع حالة المرشح.

        لا يعدّل محرك التفضيلات هنا — التطبيق عبر apply_confirmed فقط.
        """
        if user_action not in USER_ACTIONS:
            raise ValueError(f"user_action غير معروف: {user_action} — المسموح: {USER_ACTIONS}")
        if not session_id or not file_fingerprint:
            raise ValueError("source_session وfile_fingerprint مطلوبان")
        record: Dict[str, Any] = {
            "type": "feedback",
            "feedback_id": new_feedback_id(),
            "timestamp": _now_iso(),
            "source_session": str(session_id),
            "file_fingerprint": file_fingerprint,
            "original_prediction": str(original_prediction or ""),
            "user_action": user_action,
            "corrected_value": str(corrected_value) if corrected_value else None,
            "source_rule_id": source_rule_id,
            "application_version": str(application_version),
            "evidence": sanitize_evidence(evidence),
            "review_status": "pending_review",
            "duplicate": False,
            "conflict": False,
            "candidate": None,
        }

        signature = self._signature(record)
        with self._thread_lock:
            if signature in self._dup_signatures:
                record["duplicate"] = True

        # تصنيف الفعل → حالة المراجعة والمرشح
        if user_action == "reject":
            record["review_status"] = "dismissed"
            record["candidate"] = None  # الرفض لا تعلم
        elif user_action == "temp_override":
            record["review_status"] = "dismissed"
            record["candidate"] = None  # مؤقت — لا قاعدة أبدية
        elif user_action == "accept":
            if source_rule_id:
                record["review_status"] = "confirmed"  # تأكيد صريح للقاعدة المسؤولة
            else:
                record["review_status"] = "dismissed"  # قبول بلا قاعدة — لا شيء نتعلمه
        else:  # correct / set_destination / file_exception / general_preference
            if not corrected_value:
                record["review_status"] = "dismissed"
                record["candidate_note"] = "لا قيمة مصححة — لا مرشح"
            else:
                record["candidate"] = self._candidate_from(record)

        with self._thread_lock:
            self._append(record)
            self._absorb(record)
        return copy.deepcopy(record)

    def _candidate_from(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """مرشح قاعدة للمراجعة البشرية — بلا تطبيق."""
        scope_kind = "file" if record["user_action"] == "file_exception" else "global"
        evidence = record["evidence"]
        match: Dict[str, Any]
        ext = evidence.get("extension")
        if ext:
            match = {"kind": "extension", "value": ext, "case_insensitive": True}
        elif evidence.get("mime_type"):
            match = {"kind": "mime", "value": evidence["mime_type"], "case_insensitive": True}
        else:
            match = {"kind": "name_contains", "value": "", "case_insensitive": True}
        conflict = False
        if self.engine.active:
            for rule in self.engine.list_rules(include_disabled=True):
                if rule["status"] != "deleted" and rule["match"] == match \
                        and rule["destination"]["category"] != record["corrected_value"]:
                    conflict = True
                    break
        return {
            "match": match,
            "scope_kind": scope_kind,
            "scope_value": record["file_fingerprint"] if scope_kind == "file" else None,
            "destination_category": record["corrected_value"],
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
        """موافقة صريحة من المستخدم على مرشح — يرفع الحالة إلى confirmed."""
        with self._thread_lock:
            base = self._index.get(feedback_id)
            if not base:
                raise ValueError(f"feedback غير موجود: {feedback_id}")
            if base["review_status"] not in ("pending_review",):
                raise ValueError(
                    f"لا يمكن تأكيد feedback بحالة {base['review_status']}")
            update = {
                "type": "review_update",
                "feedback_id": feedback_id,
                "review_status": "confirmed",
                "ts": _now_iso(),
            }
            self._append(update)
            self._absorb(update)
            return {"feedback_id": feedback_id, "review_status": "confirmed"}

    def apply_confirmed(self, feedback_id: str, *,
                        metadata: Dict[str, Any],
                        original_category: str,
                        session_id: str,
                        file_fingerprint: str) -> Dict[str, Any]:
        """يطبّق feedback مؤكَّدًا على محرك التفضيلات (الخطوة الأخيرة).

        يفشل صراحةً لو الحالة ليست confirmed — لا تطبيق دون مراجعة.
        """
        with self._thread_lock:
            record = self._index.get(feedback_id)
            if not record:
                raise ValueError(f"feedback غير موجود: {feedback_id}")
            if record["review_status"] != "confirmed":
                raise ValueError(
                    "الرفض/المؤقت/غير المراجَع لا يُطبَّق — الحالة الحالية: "
                    f"{record['review_status']}")
            result = self.engine.record_correction(
                metadata=metadata,
                original_category=original_category,
                corrected_category=record["corrected_value"],
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

    def get_feedback(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        with self._thread_lock:
            record = self._index.get(feedback_id)
            return copy.deepcopy(record) if record else None

    def list_feedback(self, *, review_status: Optional[str] = None,
                      limit: int = 200) -> List[Dict[str, Any]]:
        with self._thread_lock:
            records = list(self._index.values())
        if review_status:
            records = [r for r in records if r["review_status"] == review_status]
        records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
        return copy.deepcopy(records[:limit])
