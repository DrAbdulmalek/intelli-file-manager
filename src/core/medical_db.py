# -*- coding: utf-8 -*-
"""قاعدة البيانات الطبية المحلية للعيادة — SQLite عبر مكتبة stdlib فقط.

قرار المالك (2026-11-22): التعامل مع بيانات العيادة محلياً مسموح؛ النشر العام
لاحقاً يتطلب إزالة بيانات المرضى الشخصية. التصميم يخدم المسارَين من اليوم الأول:

  1. محلياً: الأسماء والحقول الشخصية اختيارية، وسجل الملفات يربط الملفات
     بالمرضى مع تصنيف الحاجز الأمني.
  2. النشر لاحقاً: ``export_deidentified`` ينشئ نسخة بلا أي حقل شخصي أو
     مسار ملف قد يحوي هوية — جاهزة للنشر العام.

تكامل الحاجز الأمني:
  - بصمة SHA-256 تُحسب فقط للملفات المسموح قراءتها في وضع القراءة الحالي
    (``readable_in_current_mode``) — ملفات الأسرار تُسجَّل بياناتها الوصفية
    (حجم/وقت/تصنيف) بلا قراءة محتوى إطلاقاً.
  - الملفات الطبية في الوضع الافتراضي الصارم تُسجَّل بلا بصمة أيضاً؛ فعّل
    ``INTELLIFILE_MEDICAL_MODE=local`` لتتضمن البصمة والمعالجة المحلية.

الاستخدام:
    from src.core.medical_db import MedicalDB
    db = MedicalDB("clinic.db"); db.init()
    pid = db.add_patient(name="...", age="34", sex="m")
    db.register_file("/path/report.pdf", patient_id=pid)
    db.export_deidentified("publish.db")
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Iterable, Optional

from .sensitive_barrier import (
    SensitiveFileBlockedError,
    classify_sensitivity,
    open_checked,
    verify_open_identity,
)

logger = logging.getLogger(__name__)

RECORD_TYPES = ("imaging", "lab", "report", "visit", "prescription", "other")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id          TEXT PRIMARY KEY,
    name        TEXT,
    age         TEXT,
    sex         TEXT,
    notes       TEXT,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS records (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id   TEXT REFERENCES patients(id),
    date         TEXT NOT NULL,
    record_type  TEXT NOT NULL,
    source_path  TEXT,
    sha256       TEXT,
    summary      TEXT,
    findings     TEXT,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
    path            TEXT PRIMARY KEY,
    sha256          TEXT,
    size            INTEGER,
    mtime           REAL,
    patient_id      TEXT REFERENCES patients(id),
    classification  TEXT,
    medical_content INTEGER,
    readable        INTEGER,
    added_at        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS processing_log (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     TEXT NOT NULL,
    action TEXT NOT NULL,
    path   TEXT,
    detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_records_patient ON records(patient_id);
CREATE INDEX IF NOT EXISTS idx_records_date ON records(date);
CREATE INDEX IF NOT EXISTS idx_files_patient ON files(patient_id);
"""


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


class ExportError(RuntimeError):
    """خطأ تصدير آمن: تطابق مسار المصدر/الوجهة، أو No-Clobber، أو سباق نشر."""


class MedicalDB:
    """قاعدة بيانات SQLite محلية للعيادة — بلا أي اعتماد خارجي."""

    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "MedicalDB":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ─── التهيئة ──────────────────────────────────────────────────────────
    def init(self) -> "MedicalDB":
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self.log("init", detail=f"schema ready at {self.path}")
        return self

    # ─── المرضى ───────────────────────────────────────────────────────────
    def next_patient_id(self) -> str:
        row = self._conn.execute(
            "SELECT id FROM patients WHERE id LIKE 'P-%' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        n = int(row["id"].split("-", 1)[1]) + 1 if row else 1
        return f"P-{n:04d}"

    def add_patient(
        self,
        name: Optional[str] = None,
        age: Optional[str] = None,
        sex: Optional[str] = None,
        notes: Optional[str] = None,
        patient_id: Optional[str] = None,
    ) -> str:
        """يضيف مريضاً. الاسم والحقول الشخصية اختيارية — بلاها يكون المعرّف مستعاراً."""
        pid = patient_id or self.next_patient_id()
        self._conn.execute(
            "INSERT INTO patients (id, name, age, sex, notes, created_at) VALUES (?,?,?,?,?,?)",
            (pid, name, age, sex, notes, _now()),
        )
        self._conn.commit()
        self.log("add_patient", detail=pid)
        return pid

    def get_patient(self, patient_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_patients(self) -> list[dict]:
        rows = self._conn.execute("SELECT * FROM patients ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    # ─── السجلات ──────────────────────────────────────────────────────────
    def add_record(
        self,
        patient_id: Optional[str],
        date: str,
        record_type: str,
        source_path: Optional[str] = None,
        sha256: Optional[str] = None,
        summary: Optional[str] = None,
        findings: Optional[dict[str, Any]] = None,
    ) -> int:
        """يضيف سجلاً طبياً. findings قاموس يُخزَّن JSON نصياً."""
        if record_type not in RECORD_TYPES:
            raise ValueError(f"record_type غير معروف: {record_type} — المتاح: {RECORD_TYPES}")
        _dt.date.fromisoformat(date)  # تحقق صيغة ISO
        if patient_id and not self.get_patient(patient_id):
            raise ValueError(f"المريض غير موجود: {patient_id}")
        cur = self._conn.execute(
            "INSERT INTO records (patient_id, date, record_type, source_path, sha256,"
            " summary, findings, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                patient_id,
                date,
                record_type,
                source_path,
                sha256,
                summary,
                json.dumps(findings, ensure_ascii=False) if findings else None,
                _now(),
            ),
        )
        self._conn.commit()
        self.log("add_record", path=source_path, detail=f"{record_type} for {patient_id}")
        return int(cur.lastrowid)

    def list_records(
        self,
        patient_id: Optional[str] = None,
        record_type: Optional[str] = None,
    ) -> list[dict]:
        q = "SELECT * FROM records WHERE 1=1"
        args: list[Any] = []
        if patient_id:
            q += " AND patient_id = ?"
            args.append(patient_id)
        if record_type:
            q += " AND record_type = ?"
            args.append(record_type)
        q += " ORDER BY date DESC, id DESC"
        return [dict(r) for r in self._conn.execute(q, args).fetchall()]

    def search_records(self, query: str) -> list[dict]:
        """بحث نصي بسيط في الملخصات والنتائج."""
        like = f"%{query}%"
        rows = self._conn.execute(
            "SELECT * FROM records WHERE summary LIKE ? OR findings LIKE ?"
            " ORDER BY date DESC, id DESC",
            (like, like),
        ).fetchall()
        return [dict(r) for r in rows]

    # ─── الملفات ──────────────────────────────────────────────────────────
    def register_file(
        self,
        file_path: str | Path,
        patient_id: Optional[str] = None,
    ) -> dict:
        """يسجل ملفاً مع تصنيف الحاجز. القراءة (البصمة) فقط إن كان مسموحاً في الوضع الحالي."""
        p = Path(file_path)
        st = p.stat()
        info = classify_sensitivity(p)
        readable = bool(info.get("readable_in_current_mode"))
        sha = None
        if readable and p.is_file():
            # قراءة آمنة عبر الحاجز (P1): block_if_sensitive + O_NOFOLLOW +
            # فحص ملف عادي، ثم إعادة التحقق من الهوية (st_dev/st_ino) بعد
            # القراءة — إن اُستبدل الملف بآخر أثناء القراءة تُرفض البصمة
            # كلياً ولا يُسجَّل باسم ملف آخر (مضاد TOCTOU).
            expected_stat = p.stat()
            try:
                h = hashlib.sha256()
                with open_checked(p, "rb", operation="حساب بصمة تسجيل الملف") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
                    if not verify_open_identity(f, expected_stat):
                        raise RuntimeError(
                            f"تغيّر/اُستبدل الملف أثناء حساب البصمة: {p}"
                        )
                sha = h.hexdigest()
            except (SensitiveFileBlockedError, OSError, RuntimeError) as e:
                logger.warning(
                    "تعذّرت القراءة الآمنة — تسجيل وصفي بلا بصمة: %s (%s)", p, e
                )
                sha = None
        elif not readable:
            logger.warning(
                "ملف محجوب عن القراءة في الوضع الحالي — تسجيل وصفي بلا بصمة: %s", p
            )
        self._conn.execute(
            "INSERT INTO files (path, sha256, size, mtime, patient_id, classification,"
            " medical_content, readable, added_at) VALUES (?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(path) DO UPDATE SET sha256=excluded.sha256,"
            " size=excluded.size, mtime=excluded.mtime, patient_id=excluded.patient_id,"
            " classification=excluded.classification,"
            " medical_content=excluded.medical_content, readable=excluded.readable",
            (
                str(p),
                sha,
                st.st_size,
                st.st_mtime,
                patient_id,
                "medical" if info.get("medical_content") else (
                    "secret" if info.get("is_sensitive") else "plain"
                ),
                int(bool(info.get("medical_content"))),
                int(readable),
                _now(),
            ),
        )
        self._conn.commit()
        self.log("register_file", path=str(p), detail=f"class={info.get('is_sensitive')} readable={readable}")
        return {"path": str(p), "sha256": sha, "size": st.st_size,
                "classification": "medical" if info.get("medical_content") else (
                    "secret" if info.get("is_sensitive") else "plain"),
                "readable_in_current_mode": readable}

    def list_files(self, patient_id: Optional[str] = None) -> list[dict]:
        q = "SELECT * FROM files"
        args: list[Any] = []
        if patient_id:
            q += " WHERE patient_id = ?"
            args.append(patient_id)
        q += " ORDER BY added_at DESC"
        return [dict(r) for r in self._conn.execute(q, args).fetchall()]

    # ─── التصدير المجرّد (للنشر العام لاحقاً) ─────────────────────────────
    def export_deidentified(
        self,
        out_path: str | Path,
        *,
        overwrite: bool = False,
    ) -> dict:
        """ينشئ نسخة نشر بلا أي حقل شخصي أو مسار قد يحوي هوية.

        يُجرَّد من patients: الاسم والعمر والجنس والملاحظات. ومن records:
        المسار الأصلي والبصمة. وجدول files يُحذف كلياً (مسارات/هويات).

        سياسة الوجهة (P1 — أولوية قصوى):
          - No-Clobber افتراضياً: يُرفض التصدير إن وُجلت الوجهة مسبقاً
            (لا حذف ولا استبدال صامت)؛ الاستبدال يتطلب overwrite=True صراحةً.
          - يُمنع تطابق المصدر والوجهة بعد حل الروابط الرمزية والمسارات النسبية.
          - تُبنى النسخة في ملف مؤقت ثم تُنشر ذرياً: os.link ذري no-clobber،
            أو os.replace فقط عند overwrite صريح. قاعدة المصدر لا تُمس إطلاقاً،
            وفشل أي خطوة لا يمس الوجهة الموجودة مسبقاً.

        حدود تنقية النصوص الحرة (موثقة، لا تُخفى):
          - الحقول المنظمة تُصفّر (انظر أعلاه)؛ أما حقول summary/findings
            الحرة فتُنسخ نصياً (free_text_policy="verbatim") وقد تحوي
            معرّفات ضمن النص. أي نشر عام للنسخة الناتجة يتطلب مراجعة
            بشرية موثقة — لا تنقية نصية مدمرة تلقائية.
        """
        out = Path(out_path).expanduser().resolve()
        src_resolved = self.path.expanduser().resolve()
        if out == src_resolved:
            raise ExportError(
                "مسار الوجهة يطابق قاعدة المصدر بعد حل الروابط الرمزية"
                f" والمسارات النسبية: {out}"
            )
        if out.exists() and out.is_dir():
            raise ExportError(f"الوجهة مجلد وليست ملفاً: {out}")
        if out.exists() and not overwrite:
            raise ExportError(
                f"الوجهة موجودة (No-Clobber) ولن تُستبدل: {out} — "
                "مرر overwrite=True صراحةً إن أردت الاستبدال."
            )

        out.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".ifm_export_{out.name}_", suffix=".part", dir=str(out.parent)
        )
        os.close(fd)
        tmp_file = Path(tmp_name)
        published = False
        try:
            with MedicalDB(tmp_file) as dst:
                dst.init()
                for pid_row in self.list_patients():
                    dst._conn.execute(
                        "INSERT INTO patients (id, name, age, sex, notes, created_at)"
                        " VALUES (?,?,?,?,?,?)",
                        (pid_row["id"], None, None, None, None, pid_row["created_at"]),
                    )
                n_rec = 0
                for r in self.list_records():
                    dst._conn.execute(
                        "INSERT INTO records (patient_id, date, record_type, source_path,"
                        " sha256, summary, findings, created_at) VALUES (?,?,?,?,?,?,?,?)",
                        (r["patient_id"], r["date"], r["record_type"], None, None,
                         r["summary"], r["findings"], r["created_at"]),
                    )
                    n_rec += 1
                dst._conn.commit()
            # تدفق النسخة المكتملة على القرص قبل النشر الذري
            with open(tmp_file, "rb") as f:
                os.fsync(f.fileno())
            if overwrite and out.exists():
                os.replace(tmp_file, out)
            else:
                # نشر ذري no-clobber: os.link يفشل إن شُغلت الوجهة في سباق
                # متزامن — يُرفض، ولا استبدال ولا حذف لأي شيء
                try:
                    os.link(tmp_file, out)
                except FileExistsError as e:
                    raise ExportError(
                        f"شُغلت الوجهة أثناء التصدير (سباق) — رُفض النشر: {out}"
                    ) from e
            published = True
        finally:
            if not published and tmp_file.exists():
                try:
                    tmp_file.unlink()
                except OSError as e:
                    logger.warning("تعذر إزالة الملف المؤقت %s: %s", tmp_file, e)
        self.log("export_deidentified", detail=str(out))
        return {
            "out": str(out),
            "patients": len(self.list_patients()),
            "records": n_rec,
            "free_text_policy": "verbatim",
        }

    # ─── السجل والإحصاء ───────────────────────────────────────────────────
    def log(self, action: str, path: Optional[str] = None, detail: Optional[str] = None) -> None:
        self._conn.execute(
            "INSERT INTO processing_log (ts, action, path, detail) VALUES (?,?,?,?)",
            (_now(), action, path, detail),
        )
        self._conn.commit()

    def stats(self) -> dict:
        def count(table: str) -> int:
            return int(self._conn.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"])

        return {
            "db": str(self.path),
            "patients": count("patients"),
            "records": count("records"),
            "files": count("files"),
            "log_entries": count("processing_log"),
        }
