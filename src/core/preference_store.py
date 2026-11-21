# -*- coding: utf-8 -*-
"""PreferenceStore — تخزين تفضيلات التصنيف بأمان (P0 data safety)

طبقة التخزين الوحيدة لقواعد تفضيلات التصنيف. تتعامل مع ملف JSON واحد
(افتراضيًا ``~/.intellifile/preferences.json``) ولا تعرف شيئًا عن
AlphaCode أو ملفاته الشخصية (انظر docs/PREFERENCE_STORE.md).

ضمانات السلامة المنفذة هنا (متطلب المهمة §3):
  1. مخطط موثق (schema_version=2) مع تحقق صارم للحقول المعروفة.
  2. ترحيل إصدارات (v1 → v2) لا يفقد أقسامًا أو حقولًا غير معروفة.
  3. رفض المخططات غير المعروفة: يدخل النظام SAFE READ-STATE ولا يكتب فوق
     الملف الأصلي إطلاقًا.
  4. كتابة ذرّية: ملف مؤقت في نفس المجلد ثم ``os.replace``.
  5. نسخة احتياطية ``.bak`` قبل كل كتابة + بصمة ``sha256`` للنسخة الاحتياطية،
     والتحقق من البصمة قبل أي استعادة (نسخة تالفة تُرفض ويُوثَّق الرفض).
  6. قفل ملف (flock) يمنع الكتابة المتزامنة غير الآمنة.
  7. فشل التحميل لا يتحول إلى مستند فارغ قابل للحفظ — الحفظ ممنوع في
     الحالة غير الآمنة، ولا تُنشأ قواعد جديدة.
  8. سجل تغييرات داخل المستند مع لقطة «قبل» لكل تعديل (قابل للتتبع والاستعادة).

لا يستورد هذا الملف أي وحدة نقل ملفات (SafeMover/FileHandler) — طبقة
البيانات منفصلة تمامًا عن التنفيذ.
"""
from __future__ import annotations

import contextlib
import copy
import fcntl  # noqa: F401  (Linux/macOS؛ يُستورد دائمًا والبيئة المستهدفة POSIX)
import hashlib
import json
import logging
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = (1, 2)
CHANGE_LOG_MAX = 500

RULE_STATUSES = ("provisional", "stable", "disabled", "deleted")
MATCH_KINDS = ("extension", "mime", "name_contains")
SCOPE_KINDS = ("global", "directory", "file")
ORIGINS = ("user_correction", "alphacode", "import")

REQUIRED_RULE_KEYS = ("rule_id", "created_at", "updated_at", "status", "match",
                      "scope", "destination", "confidence")


class PreferenceStoreError(RuntimeError):
    """أساس أخطاء المخزن."""


class StoreReadOnlyError(PreferenceStoreError):
    """المخزن في SAFE READ-ONLY — الحفظ والتعديل ممنوعان."""


class InvalidRuleError(PreferenceStoreError):
    """قاعدة تخالف المخطط."""


class BackupCorruptedError(PreferenceStoreError):
    """النسخة الاحتياطية لا تطابق بصمتها — الاستعادة مرفوضة."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def new_rule_id() -> str:
    return uuid.uuid4().hex


def validate_rule(rule: Any) -> List[str]:
    """يتحقق من قاعدة واحدة ضد المخطط. يُرجع قائمة أخطاء (فارغة = صالحة).

    الحقول غير المعروفة داخل القاعدة مسموحة وتُحفظ كما هي (لا فقدان بيانات).
    """
    errors: List[str] = []
    if not isinstance(rule, dict):
        return ["rule_not_object"]
    for key in REQUIRED_RULE_KEYS:
        if key not in rule:
            errors.append(f"missing:{key}")
    if "rule_id" in rule and (not isinstance(rule["rule_id"], str) or not rule["rule_id"]):
        errors.append("bad:rule_id")
    if "status" in rule and rule["status"] not in RULE_STATUSES:
        errors.append(f"bad:status:{rule['status']!r}")
    match = rule.get("match")
    if not isinstance(match, dict) or match.get("kind") not in MATCH_KINDS:
        errors.append("bad:match")
    elif not isinstance(match.get("value"), str) or not match["value"]:
        errors.append("bad:match.value")
    scope = rule.get("scope")
    if not isinstance(scope, dict) or scope.get("kind") not in SCOPE_KINDS:
        errors.append("bad:scope")
    elif scope.get("kind") in ("directory", "file") and (
        not isinstance(scope.get("value"), str) or not scope["value"]
    ):
        errors.append("bad:scope.value")
    destination = rule.get("destination")
    if not isinstance(destination, dict) or not isinstance(destination.get("category"), str) \
            or not destination["category"]:
        errors.append("bad:destination")
    confidence = rule.get("confidence")
    if not isinstance(confidence, dict) or not isinstance(confidence.get("independent_sessions"), int) \
            or not isinstance(confidence.get("total_confirmations"), int):
        errors.append("bad:confidence")
    if "source" in rule:
        source = rule["source"]
        if not isinstance(source, dict) or (
            "origin" in source and source["origin"] not in ORIGINS
        ):
            errors.append("bad:source")
    if "history" in rule and not isinstance(rule["history"], list):
        errors.append("bad:history")
    return errors


class PreferenceStore:
    """مخزن JSON ذرّي آمن لقواعد تفضيلات التصنيف."""

    def __init__(self, path: Optional[str | os.PathLike[str]] = None):
        self.path = Path(path) if path else Path.home() / ".intellifile" / "preferences.json"
        self.backup_path = self.path.with_suffix(self.path.suffix + ".bak")
        self.backup_hash_path = self.path.with_suffix(self.path.suffix + ".bak.sha256")
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.restore_log_path = self.path.with_suffix(self.path.suffix + ".restore.log.jsonl")
        self._thread_lock = threading.RLock()
        self._document: Optional[Dict[str, Any]] = None
        self._read_only = False
        self._load_errors: List[str] = []

    # ─── الحالة ────────────────────────────────────────────────────────────

    @property
    def read_only(self) -> bool:
        return self._read_only

    @property
    def load_errors(self) -> List[str]:
        return list(self._load_errors)

    @property
    def ok(self) -> bool:
        return self._document is not None and not self._read_only

    # ─── الترحيل ───────────────────────────────────────────────────────────

    @staticmethod
    def migrate(document: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[int]]:
        """يرقيّ المستند إلى SCHEMA_VERSION دون فقدان أي حقل غير معروف.

        v1: {"schema_version": 1, "rules": [...]}  (بلا history)
        v2: {"schema_version": 2, "preferences": {"rules": [...]}, "change_log": []}

        Returns:
            (المستند المرقّى، الإصدار الأصلي إن حدث ترحيل وإلا None).
        Raises:
            PreferenceStoreError: إصدار غير مدعوم (يُرفض ولا يُلمس الملف).
        """
        version = document.get("schema_version")
        if not isinstance(version, int):
            raise PreferenceStoreError(f"schema_version مفقود أو غير رقمي: {version!r}")
        if version not in SUPPORTED_SCHEMA_VERSIONS:
            raise PreferenceStoreError(
                f"إصدار مخطط غير مدعوم: {version} — المدعوم: {SUPPORTED_SCHEMA_VERSIONS}. "
                "الملف الأصلي لن يُعدَّل (SAFE READ-ONLY)."
            )
        if version == SCHEMA_VERSION:
            return document, None

        migrated = copy.deepcopy(document)
        rules = migrated.pop("rules", [])
        migrated["preferences"] = {"rules": rules}
        migrated.setdefault("change_log", [])
        migrated["schema_version"] = SCHEMA_VERSION
        migrated.setdefault("migrations_applied", []).append(
            {"from": version, "to": SCHEMA_VERSION, "at": _now_iso()}
        )
        return migrated, version

    # ─── التحقق من المستند ─────────────────────────────────────────────────

    @staticmethod
    def validate_document(document: Dict[str, Any]) -> List[str]:
        """تحقق صارم من الأجزاء المعروفة؛ الأقسام غير المعروفة مسموحة وتُحفظ."""
        errors: List[str] = []
        version = document.get("schema_version")
        if version != SCHEMA_VERSION:
            errors.append(f"bad:schema_version:{version!r}")
            return errors
        prefs = document.get("preferences")
        if not isinstance(prefs, dict) or not isinstance(prefs.get("rules"), list):
            errors.append("bad:preferences.rules")
            return errors
        for index, rule in enumerate(prefs["rules"]):
            for err in validate_rule(rule):
                errors.append(f"rule[{index}].{err}")
        if "change_log" in document and not isinstance(document["change_log"], list):
            errors.append("bad:change_log")
        return errors

    # ─── القفل ─────────────────────────────────────────────────────────────

    @contextlib.contextmanager
    def _file_lock(self):
        """قفل استئناري على ملف جانبي (flock). يُحمل فقط أثناء I/O."""
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.lock_path, "a+", encoding="utf-8") as lock_fh:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)

    # ─── التحميل ───────────────────────────────────────────────────────────

    def load(self) -> Dict[str, Any]:
        """يحمّل المستند (مع ترحيل في الذاكرة عند الحاجة).

        عند أي فشل: SAFE READ-ONLY — لا يُكتب فوق الملف الأصلي ولا يُرجع
        مستند فارغ قابل للحفظ.
        """
        with self._thread_lock:
            self._read_only = False
            self._load_errors = []
            self._document = None
            if not self.path.exists():
                self._document = {
                    "schema_version": SCHEMA_VERSION,
                    "preferences": {"rules": []},
                    "change_log": [],
                }
                return self.load_report(ok=True)
            try:
                raw = self.path.read_bytes()
                document = json.loads(raw.decode("utf-8"))
                if not isinstance(document, dict):
                    raise ValueError("المستند الجذري ليس كائن JSON")
                migrated, migrated_from = self.migrate(document)
                errors = self.validate_document(migrated)
                if errors:
                    self._read_only = True
                    self._load_errors = errors
                    logger.error(
                        "PreferenceStore: مخطط غير صالح في %s — SAFE READ-ONLY: %s",
                        self.path, errors,
                    )
                    return self.load_report(ok=False)
                self._document = migrated
                return self.load_report(ok=True, migrated_from=migrated_from)
            except (json.JSONDecodeError, ValueError, PreferenceStoreError, OSError) as exc:
                self._read_only = True
                self._load_errors = [f"load_failed:{type(exc).__name__}:{exc}"]
                logger.error("PreferenceStore: فشل التحميل — SAFE READ-ONLY: %s", exc)
                return self.load_report(ok=False)

    def load_report(self, ok: bool, migrated_from: Optional[int] = None) -> Dict[str, Any]:
        report = {
            "ok": ok,
            "read_only": self._read_only,
            "errors": list(self._load_errors),
            "path": str(self.path),
            "schema_version": SCHEMA_VERSION if ok else None,
            "rule_count": len(self._document["preferences"]["rules"]) if self._document else 0,
        }
        if migrated_from is not None:
            report["migrated_from"] = migrated_from
        return report

    # ─── الحفظ الذرّي ──────────────────────────────────────────────────────

    def save(self) -> None:
        """كتابة ذرّية مع نسخة احتياطية موثّقة، تحت قفل ملف.

        ممنوع تمامًا في الحالة غير الآمنة (read-only).
        """
        with self._thread_lock:
            if self._read_only or self._document is None:
                raise StoreReadOnlyError(
                    "المخزن في SAFE READ-ONLY — الحفظ فوق الملف الأصلي ممنوع. "
                    f"الأخطاء: {self._load_errors}"
                )
            errors = self.validate_document(self._document)
            if errors:
                raise InvalidRuleError(f"المستند لا يجتاز التحقق: {errors}")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(self._document, ensure_ascii=False, indent=1) + "\n"
            with self._file_lock():
                if self.path.exists():
                    backup_bytes = self.path.read_bytes()
                    self.backup_path.write_bytes(backup_bytes)
                    self.backup_hash_path.write_text(
                        _sha256_bytes(backup_bytes) + "\n", encoding="utf-8"
                    )
                fd, tmp_name = tempfile.mkstemp(
                    prefix=self.path.name + ".tmp-", dir=str(self.path.parent)
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as tmp_fh:
                        tmp_fh.write(payload)
                        tmp_fh.flush()
                        os.fsync(tmp_fh.fileno())
                    os.replace(tmp_name, self.path)
                finally:
                    if os.path.exists(tmp_name):  # فشل الاستبدال — لا بقايا
                        with contextlib.suppress(OSError):
                            os.unlink(tmp_name)

    # ─── النسخ الاحتياطي والاستعادة ────────────────────────────────────────

    def restore_backup(self) -> Dict[str, Any]:
        """يستعيد ``.bak`` بعد التحقق من بصمة sha256.

        نسخة تالفة → رفض + توثيق القرار في ``.restore.log.jsonl`` محليًا.
        """
        decision: Dict[str, Any] = {"ts": _now_iso(), "backup": str(self.backup_path)}
        if not self.backup_path.exists():
            decision.update({"restored": False, "reason": "no_backup"})
            return decision
        stored_hash = ""
        if self.backup_hash_path.exists():
            stored_hash = self.backup_hash_path.read_text(encoding="utf-8").strip()
        backup_bytes = self.backup_path.read_bytes()
        actual_hash = _sha256_bytes(backup_bytes)
        if not stored_hash or actual_hash != stored_hash:
            decision.update({
                "restored": False,
                "reason": "backup_corrupted_refused",
                "hash_match": False,
            })
            logger.error("PreferenceStore: نسخة احتياطية تالفة — الاستعادة مرفوضة: %s",
                         self.backup_path)
            with open(self.restore_log_path, "a", encoding="utf-8") as log_fh:
                log_fh.write(json.dumps(decision, ensure_ascii=False) + "\n")
            raise BackupCorruptedError(
                f"النسخة الاحتياطية لا تطابق بصمتها — رُفضت الاستعادة ووُثّق القرار: "
                f"{self.backup_path}"
            )
        json.loads(backup_bytes.decode("utf-8"))  # يرفض JSON تالفًا قبل الاستبدال
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=self.path.name + ".rst-", dir=str(self.path.parent)
        )
        with os.fdopen(fd, "wb") as tmp_fh:
            tmp_fh.write(backup_bytes)
            tmp_fh.flush()
            os.fsync(tmp_fh.fileno())
        os.replace(tmp_name, self.path)
        decision.update({"restored": True, "hash_match": True})
        return decision

    # ─── الوصول للقواعد والتعديل ───────────────────────────────────────────

    def _require_writable(self) -> Dict[str, Any]:
        if self._read_only or self._document is None:
            raise StoreReadOnlyError("المخزن غير قابل للكتابة — أنشئ قواعد جديدة ممنوع")
        return self._document

    def list_rules(self, *, include_disabled: bool = False,
                   include_deleted: bool = False) -> List[Dict[str, Any]]:
        """نسخ عميقة من القواعد؛ المحذوفة وغير المفعّلة مستثناة افتراضيًا."""
        if self._document is None:
            return []
        hidden = set() if include_disabled else {"disabled"}
        if include_deleted:
            hidden = set()
        else:
            hidden.add("deleted")
        return [
            copy.deepcopy(r) for r in self._document["preferences"]["rules"]
            if r.get("status") not in hidden
        ]

    def add_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """يضيف قاعدة جديدة متحقَّق منها (نسخة عميقة تُخزَّن)."""
        doc = self._require_writable()
        rule = copy.deepcopy(rule)
        if not rule.get("rule_id"):
            rule["rule_id"] = new_rule_id()
        errors = validate_rule(rule)
        if errors:
            raise InvalidRuleError(f"قاعدة غير صالحة: {errors}")
        if any(r["rule_id"] == rule["rule_id"] for r in doc["preferences"]["rules"]):
            raise InvalidRuleError(f"rule_id مكرر: {rule['rule_id']}")
        rule.setdefault("history", []).append(
            {"ts": _now_iso(), "event": "created", "details": ""}
        )
        doc["preferences"]["rules"].append(rule)
        self._append_change("rule_created", {"rule_id": rule["rule_id"]})
        self.save()
        return copy.deepcopy(rule)

    def update_rule(
        self, rule_id: str, mutator: Callable[[Dict[str, Any]], None], *,
        change_action: str = "rule_updated",
    ) -> Dict[str, Any]:
        """يطبّق mutator على نسخة من القاعدة ثم يتحقق ويحفظ مع لقطة «قبل».

        اللقطة القديمة تُخزَّن في change_log — أساس revert_last_change.
        """
        doc = self._require_writable()
        index = self._find_index(rule_id)
        before = copy.deepcopy(doc["preferences"]["rules"][index])
        updated = copy.deepcopy(before)
        mutator(updated)
        updated["rule_id"] = rule_id  # لا سرقة هوية
        updated["updated_at"] = _now_iso()
        errors = validate_rule(updated)
        if errors:
            raise InvalidRuleError(f"التعديل يخالف المخطط: {errors}")
        doc["preferences"]["rules"][index] = updated
        self._append_change(change_action, {"rule_id": rule_id, "before": before})
        self.save()
        return copy.deepcopy(updated)

    def _find_index(self, rule_id: str) -> int:
        doc = self._require_writable()
        for index, rule in enumerate(doc["preferences"]["rules"]):
            if rule.get("rule_id") == rule_id:
                return index
        raise InvalidRuleError(f"قاعدة غير موجودة: {rule_id}")

    def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        if self._document is None:
            return None
        for rule in self._document["preferences"]["rules"]:
            if rule.get("rule_id") == rule_id:
                return copy.deepcopy(rule)
        return None

    def _append_change(self, action: str, details: Dict[str, Any]) -> None:
        doc = self._require_writable()
        doc.setdefault("change_log", []).append(
            {"ts": _now_iso(), "action": action, "details": details}
        )
        if len(doc["change_log"]) > CHANGE_LOG_MAX:
            doc["change_log"] = doc["change_log"][-CHANGE_LOG_MAX:]

    def revert_last_change(self) -> Optional[Dict[str, Any]]:
        """يرجع آخر تعديل قاعدة من لقطة «قبل» في change_log.

        كل إدخال مستعاد سابقًا يُعلَّم ``reverted=True`` فلا يُستعاد منه
        مرتين (مع بقائه للسجل التتبعي). لا يسترجع الإنشاء (لا حالة سابقة
        له) — يُرجع None عندها.
        """
        doc = self._require_writable()
        log = doc.get("change_log", [])
        for entry in reversed(log):
            if entry.get("action") not in ("rule_created", "rule_updated"):
                continue
            if entry.get("reverted"):
                continue
            rule_id = entry["details"].get("rule_id")
            before = entry["details"].get("before")
            if before is None:  # إنشاء — لا حالة سابقة للاستعادة
                return None
            try:
                index = self._find_index(rule_id)
            except InvalidRuleError:
                return None
            restored = copy.deepcopy(before)
            restored["updated_at"] = _now_iso()
            errors = validate_rule(restored)
            if errors:
                raise InvalidRuleError(f"اللقطة المخزنة تالفة: {errors}")
            doc["preferences"]["rules"][index] = restored
            entry["reverted"] = True
            self._append_change("rule_reverted", {"rule_id": rule_id})
            self.save()
            return copy.deepcopy(restored)
        return None
