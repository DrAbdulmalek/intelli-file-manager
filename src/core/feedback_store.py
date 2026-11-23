"""Privacy-minimal structured feedback events for IntelliFile.

Only bounded categorical tokens are accepted. Free-form details, paths,
document text, prompts, patient data, and caller-supplied digests are not
part of this API or persisted schema.
"""
from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path
from typing import Any

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
_ALLOWED_SEVERITIES = {"info", "warning", "error", "critical"}
_ALLOWED_STATES = {"observed", "reviewed", "accepted", "rejected", "resolved"}


def _token(value: str, field: str) -> str:
    if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
        raise ValueError(f"{field} must be a short non-empty token")
    return value


class FeedbackStore:
    """Append-oriented local SQLite store for categorical feedback metadata."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path).expanduser()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    component TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    expected_code TEXT,
                    observed_code TEXT,
                    evidence_status TEXT NOT NULL,
                    reproduction_token TEXT,
                    decision TEXT NOT NULL DEFAULT 'unreviewed',
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_feedback_component ON feedback_events(component, created_at)"
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.database_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def record(
        self,
        *,
        component: str,
        event_type: str,
        severity: str,
        evidence_status: str,
        expected_code: str | None = None,
        observed_code: str | None = None,
        reproduction_token: str | None = None,
    ) -> int:
        component = _token(component, "component")
        event_type = _token(event_type, "event_type")
        evidence_status = _token(evidence_status, "evidence_status")
        if severity not in _ALLOWED_SEVERITIES:
            raise ValueError("unsupported severity")
        for name, value in (
            ("expected_code", expected_code),
            ("observed_code", observed_code),
            ("reproduction_token", reproduction_token),
        ):
            if value is not None:
                _token(value, name)
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO feedback_events
                   (component, event_type, severity, expected_code, observed_code,
                    evidence_status, reproduction_token, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    component,
                    event_type,
                    severity,
                    expected_code,
                    observed_code,
                    evidence_status,
                    reproduction_token,
                    time.time(),
                ),
            )
            return int(cursor.lastrowid)

    def set_decision(self, event_id: int, decision: str) -> bool:
        if decision not in _ALLOWED_STATES:
            raise ValueError("unsupported decision")
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE feedback_events SET decision=? WHERE id=?",
                (decision, event_id),
            )
            return cursor.rowcount == 1

    def list_events(self, limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    """SELECT id, component, event_type, severity, expected_code,
                              observed_code, evidence_status, reproduction_token,
                              decision, created_at
                       FROM feedback_events ORDER BY id DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
            ]
