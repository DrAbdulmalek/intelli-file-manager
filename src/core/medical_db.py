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
class IdentityMismatchError(RuntimeError):
    """فشل التحقق من هوية الملف أثناء التسجيل (مضاد TOCTOU — fail-closed)."""


def _sha256_with_identity_check(p: Path, expected_stat: os.stat_result) -> str:
    """يحسب SHA-256 عبر الحاجز مع تحقق هوية ثلاثي (P1 — مضاد TOCTOU، مكتمل F8).

    تسلسل fstat-الأساس:
      1. فتح عبر open_checked (حاجز + O_NOFOLLOW + فحص ملف عادي).
      2. fstat على الواصف المفتوح ومقارنته بstat المسار قبل أي قراءة —
         الآن شاملًا (st_dev, st_ino, st_size, st_mtime_ns, st_ctime_ns).
      3. القراءة ثم fstat جديد: كشف استبدال، تغيّر حجم، أو **تغيّر محتوى
         حتى مع بقاء الحجم و inode ثابتين** (F8) — أي كتابة تُغيّر
         mtime_ns؛ وctime_ns لا يمكن لعملية مستخدم إعادة ضبطه، فلا يمكن
         التخفي بإعادة ضبط الوقت بعد تعديل المحتوى بنفس الحجم.
      4. بعد الإغلاق: **lstat** المسار (لا يتبع الروابط الرمزية — F8):
         يجب أن يشير إلى نفس (st_dev, st_ino) وأن يبقى ملفاً عادياً —
         استبدال المسار برابط رمزي **حتى إلى نفس الملف** يُرفض.

    أي فشل في أي خطوة يرفع IdentityMismatchError — لا بصمة جزئية ولا
    تُخزَّن بصمة لم تتأكد هويتها. لا تدّعية متانة بعد انقطاع الطاقة هنا.

    حدود الإثبات (موثقة، لا تُخفى): الفحص يثبت أن الهوية لم تتغير وأن
    المحتوى المقروء مرتين متطابق عبر نافذة القراءة على هذا النظام المحلي؛
    لا يثبت استحالة جميع هجمات TOCTOU (تلاعب على مستوى النواة/نظام ملفات
    شبكي، أو سباق خارج نافذة الفحص) — الدفاع بالعمق يبقى عبر الحاجز و
    O_NOFOLLOW والتحقق بعد الإغلاق. الكلفة: قراءة الملف مرتين (دقيقة
    المحتوى تتطلب ذلك — الطوابع الزمنية وحدها بدقة خشنة على بعض أنظمة
    الملفات لا تكشف تعديلاً بقي في نافذة نفس النبضة).
    """
    import stat as _stat

    expected = (expected_stat.st_dev, expected_stat.st_ino)
    expected_size = expected_stat.st_size
    expected_times = (expected_stat.st_mtime_ns, expected_stat.st_ctime_ns)
    h = hashlib.sha256()
    h2 = hashlib.sha256()
    with open_checked(p, "rb", operation="حساب بصمة تسجيل الملف") as f:
        st_open = os.fstat(f.fileno())
        if (st_open.st_dev, st_open.st_ino) != expected:
            raise IdentityMismatchError(
                f"الملف المفتوح لا يطابق الملف المطلوب (فحص قبل القراءة): {p}"
            )
        if (st_open.st_size, st_open.st_mtime_ns, st_open.st_ctime_ns) != (
                expected_size, expected_times[0], expected_times[1]):
            raise IdentityMismatchError(
                f"تغيّر الملف بين فحص المسار والفتح (حجم/وقت/حالة): {p}"
            )
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
        st_after = os.fstat(f.fileno())
        if (st_after.st_dev, st_after.st_ino) != expected:
            raise IdentityMismatchError(f"اُستبدل الملف أثناء القراءة: {p}")
        # F8: مقارنة الحجم والأوقات — خط أول سريع لكشف التعديل (mtime_ns
        # يتغير مع أي كتابة، وctime_ns لا يُعاد ضبطه من فضاء المستخدم).
        if (st_after.st_size, st_after.st_mtime_ns, st_after.st_ctime_ns) != (
                st_open.st_size, st_open.st_mtime_ns, st_open.st_ctime_ns):
            raise IdentityMismatchError(
                f"تغيّر الملف أثناء القراءة (حجم/وقت تعديل/وقت تغيير الحالة): {p}"
            )
        # F8: إعادة قراءة كاملة ومقارنة بصمة المحتوى — الإثبات الحتمي
        # المستقل عن دقة الطوابع الزمنية: أي تعديل محتوى بحجم/inode ثابت
        # بين القراءتين يُنتج بصمتين مختلفتين → رفض، لا بصمة تُخزَّن.
        f.seek(0)
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h2.update(chunk)
        st_final = os.fstat(f.fileno())
        if (st_final.st_dev, st_final.st_ino) != expected:
            raise IdentityMismatchError(f"اُستبدل الملف أثناء إعادة القراءة: {p}")
        if (st_final.st_size, st_final.st_mtime_ns, st_final.st_ctime_ns) != (
                st_after.st_size, st_after.st_mtime_ns, st_after.st_ctime_ns):
            raise IdentityMismatchError(
                f"تغيّر الملف أثناء إعادة القراءة: {p}"
            )
    if h.digest() != h2.digest():
        raise IdentityMismatchError(
            f"تغيّر محتوى الملف أثناء القراءة (بصمتا قراءتين مختلفتان —"
            f" فحص مزدوج F8): {p}"
        )
    try:
        st_path = os.lstat(p)  # F8: lstat لا يتبع الروابط الرمزية
    except OSError as e:
        raise IdentityMismatchError(
            f"المسار لم يعد يشير إلى ملف بعد القراءة: {p} — {e}"
        ) from e
    if (st_path.st_dev, st_path.st_ino) != expected:
        raise IdentityMismatchError(
            f"المسار لم يعد يشير إلى نفس الملف بعد القراءة"
            f" (استبدال/نقل/رابط رمزي): {p}"
        )
    if not _stat.S_ISREG(st_path.st_mode):
        raise IdentityMismatchError(
            f"المسار لم يعد ملفاً عادياً بعد القراءة (رابط رمزي/جهاز): {p}"
        )
    return h.hexdigest()



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
                # تحقق ثلاثي (قبل/أثناء/بعد القراءة) — أي فشل يمنع خزن البصمة
                sha = _sha256_with_identity_check(p, expected_stat)
            except (SensitiveFileBlockedError, OSError, RuntimeError) as e:
                logger.warning(
                    "فشل التحقق الآمن — تسجيل وصفي بلا بصمة (fail-closed): %s (%s)",
                    p, e,
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
        try:
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".ifm_export_{out.name}_", suffix=".part", dir=str(out.parent)
            )
        except OSError as e:
            raise ExportError(f"فشل إنشاء قاعدة البيانات المؤقتة: {e}") from e
        os.close(fd)
        tmp_file = Path(tmp_name)
        published = False
        try:
            # الكتابة في دالة قابلة للفحص — فشلها يُنظّف المؤقت في finally
            n_rec = self._write_deidentified_copy(tmp_file)
            # fsync على واصف مستقل بعد إغلاق اتصال SQLite المؤقت: النشر
            # لا يبدأ إلا بعد اكتمال الكتابة وتدفقها للقرص.
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
            # fsync للمجلد (الأفضل جهدًا) — لا تدّعية متانة بعد انقطاع
            # الطاقة دون اختبار على نظام الملفات المعني (قيد موثق).
            try:
                dir_fd = os.open(str(out.parent), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError as e:
                logger.warning("تعذر fsync لمجلد النشر %s: %s", out.parent, e)
        finally:
            # تنظيف الملف المؤقت في كل المسارات بما فيها النجاح عبر
            # os.link (الرابط المؤقت يبقى ما لم يُحذف صراحةً). أخطاء
            # التنظيف تُسجَّل ولا تُخفي نتيجة التصدير الأساسية؛ الوجهة
            # المنشورة لا تُمس عند فشل التنظيف.
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except OSError as e:
                    logger.warning("تعذر إزالة الملف المؤقت %s: %s", tmp_file, e)
        # تتبع العملية خارج قاعدة المصدر (Finding 1): التصدير لا يكتب
        # أي شيء في processing_log الخاص بالمصدر — التتبع عبر القيمة
        # المرجعة هنا، وعلى المتصل تسجيلها في سجل خارجي (مثل ActionLog).
        return {
            "out": str(out),
            "patients": len(self.list_patients()),
            "records": n_rec,
            "free_text_policy": "verbatim",
            "logged_in_source_db": False,
        }

    def _write_deidentified_copy(self, tmp_file: Path) -> int:
        """يكتب نسخة مجردة كاملة إلى الملف المؤقت (قبل النشر الذري).

        استُخرجت كدالة قابلة للفحص: اختبارات حقن الفشل (commit/كتابة)
        تلتقطها عبر monkeypatch وتتحقق من تنظيف المؤقت وسلامة المصدر.
        المنهجية: أبني قاعدة SQLite جديدة بدل نسخ المصدر وقصّ الحقول —
        هكذا لا تسرب أي بيانات هيكلية غير مقصودة.
        """
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
        return n_rec

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
