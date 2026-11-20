"""نموذج القصاصة التدريبية — يدعم كلمة/سطر/فقرة/حرف (SQLite).

Training snippets are human-verified OCR training units: a crop (bbox) of a
source image plus the corrected text. This is the storage layer for the
"قصاصات قابلة للتدريب مع تحرير المربعات" feature:

  - bbox is stored as four ints (x1, y1, x2, y2 — corner coordinates) so the
    web BBoxEditor can round-trip without conversion.
  - ``update_bbox`` is the core user-edit operation (drag/resize in the UI).
  - ``approve``/``reject`` drive the review workflow feeding HF export.

Privacy-first: everything stays in a local SQLite file; export to
HuggingFace is an explicit, separate, user-invoked action.
"""
from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

SnippetLevel = Literal["word", "line", "block", "character"]
SnippetStatus = Literal["pending", "approved", "rejected"]

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "training_snippets.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TrainingSnippet:
    """قصاصة تدريب واحدة — صورة + نص + إحداثيات + حالة."""

    id: Optional[int] = None
    source_image: str = ""  # مسار الصورة الأصلية
    level: SnippetLevel = "word"
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)  # x1, y1, x2, y2 (قابل للتعديل)
    text: str = ""  # النص الصحيح (يحرره المستخدم)
    ocr_text: str = ""  # النص الأصلي من OCR
    confidence: float = 0.0  # ثقة OCR — 0.0 = غير معروفة (سياسة ocr-core)
    language: str = "ar"
    status: SnippetStatus = "pending"
    category: str = "general"  # medical, general, formula, table
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    verified_by: str = ""  # من راجع القصاصة
    notes: str = ""


class SnippetDB:
    """مدير قاعدة بيانات القصاصات التدريبية (SQLite, WAL)."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ------------------------------------------------------------------
    # schema
    # ------------------------------------------------------------------
    def _init_schema(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS snippets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_image TEXT NOT NULL,
                level TEXT NOT NULL DEFAULT 'word',
                bbox_x1 INTEGER NOT NULL DEFAULT 0,
                bbox_y1 INTEGER NOT NULL DEFAULT 0,
                bbox_x2 INTEGER NOT NULL DEFAULT 0,
                bbox_y2 INTEGER NOT NULL DEFAULT 0,
                text TEXT NOT NULL DEFAULT '',
                ocr_text TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.0,
                language TEXT NOT NULL DEFAULT 'ar',
                status TEXT NOT NULL DEFAULT 'pending',
                category TEXT NOT NULL DEFAULT 'general',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                verified_by TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_snippets_status
                ON snippets(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_snippets_source
                ON snippets(source_image);
            """
        )
        conn.commit()
        conn.close()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    # ------------------------------------------------------------------
    # write operations
    # ------------------------------------------------------------------
    def insert(self, snippet: TrainingSnippet) -> int:
        conn = self._connect()
        cur = conn.execute(
            """INSERT INTO snippets
               (source_image, level, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                text, ocr_text, confidence, language, status, category,
                created_at, updated_at, verified_by, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                snippet.source_image, snippet.level,
                snippet.bbox[0], snippet.bbox[1], snippet.bbox[2], snippet.bbox[3],
                snippet.text, snippet.ocr_text, snippet.confidence,
                snippet.language, snippet.status, snippet.category,
                snippet.created_at, snippet.updated_at,
                snippet.verified_by, snippet.notes,
            ),
        )
        conn.commit()
        snippet_id = cur.lastrowid
        conn.close()
        return snippet_id

    def update_bbox(self, snippet_id: int, bbox: tuple[int, int, int, int]) -> bool:
        """تحديث المربع — الوظيفة الجوهرية لتحرير المستخدم."""
        if len(bbox) != 4:
            raise ValueError("bbox must be (x1, y1, x2, y2)")
        conn = self._connect()
        cur = conn.execute(
            """UPDATE snippets
               SET bbox_x1 = ?, bbox_y1 = ?, bbox_x2 = ?, bbox_y2 = ?,
                   updated_at = ?
               WHERE id = ?""",
            (*bbox, _now_iso(), snippet_id),
        )
        conn.commit()
        changed = cur.rowcount > 0
        conn.close()
        return changed

    def update_text(self, snippet_id: int, text: str) -> bool:
        conn = self._connect()
        cur = conn.execute(
            "UPDATE snippets SET text = ?, updated_at = ? WHERE id = ?",
            (text, _now_iso(), snippet_id),
        )
        conn.commit()
        changed = cur.rowcount > 0
        conn.close()
        return changed

    def update_category(self, snippet_id: int, category: str) -> bool:
        conn = self._connect()
        cur = conn.execute(
            "UPDATE snippets SET category = ?, updated_at = ? WHERE id = ?",
            (category, _now_iso(), snippet_id),
        )
        conn.commit()
        changed = cur.rowcount > 0
        conn.close()
        return changed

    def delete(self, snippet_id: int) -> bool:
        conn = self._connect()
        cur = conn.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
        conn.commit()
        changed = cur.rowcount > 0
        conn.close()
        return changed

    def approve(self, snippet_id: int, verified_by: str = "") -> bool:
        conn = self._connect()
        cur = conn.execute(
            """UPDATE snippets
               SET status = 'approved', verified_by = ?, updated_at = ?
               WHERE id = ?""",
            (verified_by, _now_iso(), snippet_id),
        )
        conn.commit()
        changed = cur.rowcount > 0
        conn.close()
        return changed

    def reject(self, snippet_id: int, reason: str = "") -> bool:
        conn = self._connect()
        cur = conn.execute(
            """UPDATE snippets
               SET status = 'rejected', notes = ?, updated_at = ?
               WHERE id = ?""",
            (reason, _now_iso(), snippet_id),
        )
        conn.commit()
        changed = cur.rowcount > 0
        conn.close()
        return changed

    # ------------------------------------------------------------------
    # read operations
    # ------------------------------------------------------------------
    def get(self, snippet_id: int) -> Optional[TrainingSnippet]:
        conn = self._connect()
        row = conn.execute("SELECT * FROM snippets WHERE id = ?", (snippet_id,)).fetchone()
        conn.close()
        return self._row_to_snippet(row) if row else None

    def get_by_source(self, source_image: str) -> list[TrainingSnippet]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM snippets WHERE source_image = ? ORDER BY bbox_y1, bbox_x1",
            (source_image,),
        ).fetchall()
        conn.close()
        return [self._row_to_snippet(r) for r in rows]

    def list_by_status(self, status: SnippetStatus, limit: int = 0) -> list[TrainingSnippet]:
        conn = self._connect()
        sql = "SELECT * FROM snippets WHERE status = ? ORDER BY id"
        params: list = [status]
        if limit > 0:
            sql += " LIMIT ?"
            params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [self._row_to_snippet(r) for r in rows]

    def get_approved(self, limit: int = 0) -> list[TrainingSnippet]:
        return self.list_by_status("approved", limit=limit)

    def stats(self) -> dict:
        conn = self._connect()
        rows = conn.execute(
            "SELECT status, COUNT(*) FROM snippets GROUP BY status"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM snippets").fetchone()[0]
        by_category = conn.execute(
            "SELECT category, COUNT(*) FROM snippets GROUP BY category"
        ).fetchall()
        conn.close()
        return {
            "total": total,
            "by_status": {r[0]: r[1] for r in rows},
            "by_category": {r[0]: r[1] for r in by_category},
        }

    # ------------------------------------------------------------------
    def to_dict(self, snippet: TrainingSnippet) -> dict:
        d = asdict(snippet)
        d["bbox"] = list(snippet.bbox)
        return d

    @staticmethod
    def _row_to_snippet(row) -> TrainingSnippet:
        return TrainingSnippet(
            id=row[0], source_image=row[1], level=row[2],
            bbox=(row[3], row[4], row[5], row[6]),
            text=row[7], ocr_text=row[8], confidence=row[9],
            language=row[10], status=row[11], category=row[12],
            created_at=row[13], updated_at=row[14],
            verified_by=row[15], notes=row[16],
        )
