# -*- coding: utf-8 -*-
"""مخزن Feedback ومتعلم التفضيلات — حلقة التعلم المحلية (بلا شبكة، بلا تدريب).

التصميم وفق مقترح DeepSeek (2026-11-20) مع تصحيحات الموثق:
  - إشارات: negative / positive_implicit / positive_explicit / outcome
  - جدول تكرار: (context, condition, preferred_action) → support
  - ترقية إلى قاعدة دائمة بعد 3 تصحيحات متطابقة (kind='rule')
  - وزن النجاح 1.5× (مسار النجاح أندر وأثمن)
  - تقادم FSRS-مستوحى: القابلية R = exp(-أيام / S)، S تنمو عند الاستخدام
    (استبدال لاحق بمعاملات FSRS-6 الكاملة ممكن — موثق هنا بلا مبالغة)
  - حد الأمان: preferred_action='overwrite' **يرفض** — قرارات الأمان
    خارج التعلم (OverwriteForbiddenError عقود ثابتة).
"""
from __future__ import annotations

import logging
import math
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# إشارات مسموحة — أي شيء آخر يرفض (لا حقن تعسفي)
ALLOWED_SIGNALS = {"negative", "positive_implicit", "positive_explicit", "outcome"}
# أفعال التفضيل المسموح تعلمها — الأمان (overwrite) مستبعد بالتصميم
ALLOWED_PREFERRED_ACTIONS = {"suffix", "reject", "ask_user"}
# عتبة الترقية إلى قاعدة دائمة (مقترح DeepSeek §4ب)
PROMOTION_THRESHOLD = 3
SUCCESS_WEIGHT = 1.5

# بذرة قوة الاستقرار بالأيام (نصف عمر افتراضي)
_INITIAL_STABILITY_DAYS = 14.0


_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")


def _require_safe_token(value: str, field: str, *, allow_empty: bool = False) -> str:
    """Accept bounded identifiers only; reject paths, free text, and contact data."""
    if allow_empty and value == "":
        return value
    if not isinstance(value, str) or not _SAFE_TOKEN_RE.fullmatch(value):
        raise ValueError(f"{field} must be a bounded categorical token")
    return value


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _days_between(iso_a: str, iso_b: str) -> float:
    try:
        a = datetime.fromisoformat(iso_a)
        b = datetime.fromisoformat(iso_b)
        return max(0.0, (b - a).total_seconds() / 86400.0)
    except ValueError:
        return 0.0


@dataclass
class Preference:
    """تفضيل مستخرج من الإشارات — سياقي ومتقادم."""
    context: str          # اسم الأداة مثل safe_move_file
    condition: str        # الشرط مثل destination_exists
    preferred_action: str  # suffix / reject / ask_user
    support: int          # عدد الإشارات الداعمة
    strength: float       # قابلية الاسترجاع R ∈ [0,1] بعد التقادم
    kind: str             # preference / rule (القاعدة دائمة بعد 3x)
    last_used: str        # ISO UTC

    def to_dict(self) -> dict:
        return {
            "context": self.context,
            "condition": self.condition,
            "preferred_action": self.preferred_action,
            "support": self.support,
            "strength": round(self.strength, 4),
            "kind": self.kind,
            "last_used": self.last_used,
        }


class FeedbackStore:
    """مخزن SQLite للإشارات والتفضيلات — كل شيء محلي."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else None
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        if self.db_path is not None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS feedback_events (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       token TEXT NOT NULL,
                       tool TEXT NOT NULL,
                       signal TEXT NOT NULL,
                       context TEXT DEFAULT '',
                       condition_key TEXT DEFAULT '',
                       preferred_action TEXT DEFAULT '',
                       ts TEXT NOT NULL
                   )"""
            )
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS preferences (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       context TEXT NOT NULL,
                       condition_key TEXT NOT NULL,
                       preferred_action TEXT NOT NULL,
                       support INTEGER NOT NULL DEFAULT 0,
                       stability_days REAL NOT NULL,
                       last_used TEXT NOT NULL,
                       kind TEXT NOT NULL DEFAULT 'preference',
                       UNIQUE(context, condition_key, preferred_action)
                   )"""
            )
            self._conn.commit()

    # ─── الإشارات ───────────────────────────────────────────────────────

    def record(
        self,
        token: str,
        tool: str,
        signal: str,
        note: str = "",
        context: str = "",
        condition_key: str = "",
        preferred_action: str = "",
        inputs: Optional[dict] = None,
        outcome: Optional[dict] = None,
    ) -> dict:
        """Store bounded categorical feedback only; legacy free-form fields fail closed."""
        if note not in ("", None) or inputs not in (None, {}) or outcome not in (None, {}):
            raise ValueError("free-form feedback payloads are disabled")
        token = _require_safe_token(token, "token")
        tool = _require_safe_token(tool, "tool")
        context = _require_safe_token(context, "context", allow_empty=True)
        condition_key = _require_safe_token(
            condition_key, "condition_key", allow_empty=True
        )
        if not isinstance(signal, str) or signal not in ALLOWED_SIGNALS:
            raise ValueError(
                f"إشارة ممنوعة: {signal} — المسموح: {sorted(ALLOWED_SIGNALS)}"
            )
        if not isinstance(preferred_action, str):
            raise ValueError("preferred_action must be a categorical token")
        if preferred_action and preferred_action not in ALLOWED_PREFERRED_ACTIONS:
            raise ValueError(
                f"preferred_action ممنوع: {preferred_action} — قرارات الأمان "
                f"(مثل overwrite) خارج التعلم؛ المسموح: {sorted(ALLOWED_PREFERRED_ACTIONS)}"
            )
        if preferred_action and (not context or not condition_key):
            raise ValueError("context and condition_key are required for a learned preference")
        with self._lock:
            if self._conn is None:
                logger.info("إشارة بلا مخزن (ذاكرة فقط): token=%s signal=%s", token, signal)
                return {"stored": False, "reason": "no_db_path"}
            self._conn.execute(
                "INSERT INTO feedback_events (token, tool, signal, context, "
                "condition_key, preferred_action, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    token,
                    tool,
                    signal,
                    context,
                    condition_key,
                    preferred_action,
                    _now_iso(),
                ),
            )
            self._conn.commit()
        if preferred_action:
            self.update_preference(context, condition_key, preferred_action, signal)
        return {"stored": True}

    def events_for_token(self, token: str) -> List[dict]:
        token = _require_safe_token(token, "token")
        if self._conn is None:
            return []
        with self._lock:
            rows = self._conn.execute(
                "SELECT token, tool, signal, ts FROM feedback_events "
                "WHERE token = ? ORDER BY id",
                (token,),
            ).fetchall()
        return [
            {"token": r[0], "tool": r[1], "signal": r[2], "ts": r[3]}
            for r in rows
        ]

    # ─── جدول التكرار + الترقية + التقادم ──────────────────────────────

    def update_preference(
        self, context: str, condition_key: str, preferred_action: str, signal: str
    ) -> None:
        """يحدّث تفضيلاً: دعم +1 (وزن النجاح 1.5 يظهر في strength)، وتقادم، وترقية 3x."""
        if not context or not condition_key or not preferred_action:
            return
        context = _require_safe_token(context, "context")
        condition_key = _require_safe_token(condition_key, "condition_key")
        if not isinstance(signal, str) or signal not in ALLOWED_SIGNALS:
            raise ValueError("signal is not allowed")
        if preferred_action not in ALLOWED_PREFERRED_ACTIONS:
            raise ValueError(f"preferred_action ممنوع: {preferred_action}")
        now = _now_iso()
        with self._lock:
            if self._conn is None:
                return
            row = self._conn.execute(
                "SELECT id, support, stability_days, last_used, kind FROM preferences "
                "WHERE context=? AND condition_key=? AND preferred_action=?",
                (context, condition_key, preferred_action),
            ).fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO preferences (context, condition_key, preferred_action, "
                    "support, stability_days, last_used, kind) VALUES (?, ?, ?, 1, ?, ?, 'preference')",
                    (context, condition_key, preferred_action, _INITIAL_STABILITY_DAYS, now),
                )
                self._conn.commit()
                return
            pid, support, stability, last_used, kind = row
            support += 1
            # التقادم: S تنمو مع الاستخدام (النصيف عند التكرار: نمو 35%،
            # سقف 365 يوم)، والإهمال يُظهر نفسه في strength المحسوبة وقت القراءة
            days_idle = _days_between(last_used, now)
            growth = 1.0 + (0.35 if days_idle > 7 else 0.15)
            stability = min(_INITIAL_STABILITY_DAYS * 26.0, stability * growth)
            new_kind = "rule" if (kind == "rule" or support >= PROMOTION_THRESHOLD) else kind
            self._conn.execute(
                "UPDATE preferences SET support=?, stability_days=?, last_used=?, kind=? WHERE id=?",
                (support, stability, now, new_kind, pid),
            )
            self._conn.commit()
            if new_kind == "rule" and kind != "rule":
                logger.info("ترقية تفضيل إلى قاعدة دائمة: %s/%s → %s", context, condition_key, preferred_action)

    def query(self, context: str, limit: int = 5) -> List[Preference]:
        """يسترجع تفضيلات سياق محدد بمعرّف تصنيفي محدود."""
        context = _require_safe_token(context, "context")
        if not isinstance(limit, int) or not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        if self._conn is None:
            return []
        now = _now_iso()
        with self._lock:
            rows = self._conn.execute(
                "SELECT context, condition_key, preferred_action, support, "
                "stability_days, last_used, kind FROM preferences "
                "WHERE context=? ORDER BY support DESC LIMIT 50",
                (context,),
            ).fetchall()
        out: List[Preference] = []
        for r in rows:
            ctx, cond, act, support, stability, last_used, kind = r
            days = _days_between(last_used, now)
            retrievability = math.exp(-days / max(stability, 0.5))
            # القواعد الدائمة لا تُهجر بالتقادم وحده — أرضية 0.25
            if kind == "rule":
                retrievability = max(retrievability, 0.25)
            if retrievability < 0.05:
                continue  # أُهمل فعلياً — لا يُحقن في الـprompt
            out.append(Preference(ctx, cond, act, support, retrievability, kind, last_used))
        out.sort(key=lambda p: (-p.strength, -p.support))
        return out[:limit]

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
