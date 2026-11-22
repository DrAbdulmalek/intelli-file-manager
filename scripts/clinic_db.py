#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""أداة سطر الأوامر لقاعدة بيانات العيادة المحلية (SQLite — stdlib فقط).

أمثلة:
    python scripts/clinic_db.py init --db clinic.db
    python scripts/clinic_db.py add-patient --db clinic.db --name "..." --age 34 --sex m
    python scripts/clinic_db.py add-record  --db clinic.db --patient P-0001 --date 2026-11-22 \
        --type report --summary "تقرير صدر" --findings '{"impression":"طبيعي"}'
    python scripts/clinic_db.py register-file --db clinic.db --path "/scans/IMG_0001.jpg" --patient P-0001
    python scripts/clinic_db.py list-records --db clinic.db --patient P-0001
    python scripts/clinic_db.py search --db clinic.db --query "الصدر"
    python scripts/clinic_db.py export-deidentified --db clinic.db --out publish.db
    python scripts/clinic_db.py stats --db clinic.db

ملاحظة الخصوصية: لتشغيل المعالجة المحلية على ملفات العيادة الطبية فعّل:
    INTELLIFILE_MEDICAL_MODE=local
الأسرار (مفاتيح/اعتماديات) تبقى محجوبة في كل الأوضاع، والإرسال الخارجي
للمحتوى الطبي يبقى محكوماً بالحكم الصارم مهما كان الوضع.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.medical_db import RECORD_TYPES, MedicalDB  # noqa: E402


def _add_db_arg(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--db", default="clinic.db", help="مسار قاعدة البيانات (افتراضي: clinic.db)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="قاعدة البيانات الطبية المحلية للعيادة")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="إنشاء القاعدة والمخطط")
    _add_db_arg(sp)

    sp = sub.add_parser("add-patient", help="إضافة مريض (الحقول الشخصية اختيارية)")
    _add_db_arg(sp)
    sp.add_argument("--name", default=None, help="الاسم — اختياري (بلاه = معرّف مستعار فقط)")
    sp.add_argument("--age", default=None)
    sp.add_argument("--sex", default=None, choices=["m", "f", "other"])
    sp.add_argument("--notes", default=None)
    sp.add_argument("--id", dest="patient_id", default=None, help="معرّف مخصص (P-0001)")

    sp = sub.add_parser("add-record", help="إضافة سجل طبي")
    _add_db_arg(sp)
    sp.add_argument("--patient", default=None, help="معرّف المريض")
    sp.add_argument("--date", required=True, help="ISO: 2026-11-22")
    sp.add_argument("--type", dest="record_type", required=True, choices=RECORD_TYPES)
    sp.add_argument("--source", default=None, help="مسار الملف الأصلي")
    sp.add_argument("--summary", default=None)
    sp.add_argument("--findings", default=None, help='JSON مثل \'{"impression":"طبيعي"}\'')

    sp = sub.add_parser("register-file", help="تسجيل ملف مع تصنيف الحاجز (بصمة فقط إن سُمحت القراءة)")
    _add_db_arg(sp)
    sp.add_argument("--path", required=True)
    sp.add_argument("--patient", default=None)

    sp = sub.add_parser("list-patients", help="عرض المرضى")
    _add_db_arg(sp)

    sp = sub.add_parser("list-records", help="عرض السجلات (اختياري: --patient و--type)")
    _add_db_arg(sp)
    sp.add_argument("--patient", default=None)
    sp.add_argument("--type", dest="record_type", default=None)

    sp = sub.add_parser("search", help="بحث نصي في السجلات")
    _add_db_arg(sp)
    sp.add_argument("--query", required=True)

    sp = sub.add_parser("export-deidentified", help="تصدير نسخة نشر بلا حقول شخصية")
    _add_db_arg(sp)
    sp.add_argument("--out", required=True)

    sp = sub.add_parser("stats", help="إحصاءات القاعدة")
    _add_db_arg(sp)

    args = ap.parse_args(argv)

    if args.cmd == "init":
        db = MedicalDB(args.db).init()
        print(f"جاهزة: {db.stats()}")
        return 0

    db = MedicalDB(args.db).init()
    try:
        if args.cmd == "add-patient":
            pid = db.add_patient(name=args.name, age=args.age, sex=args.sex,
                                 notes=args.notes, patient_id=args.patient_id)
            print(json.dumps({"patient_id": pid}, ensure_ascii=False))
        elif args.cmd == "add-record":
            findings = json.loads(args.findings) if args.findings else None
            rid = db.add_record(args.patient, args.date, args.record_type,
                                source_path=args.source, summary=args.summary,
                                findings=findings)
            print(json.dumps({"record_id": rid}, ensure_ascii=False))
        elif args.cmd == "register-file":
            print(json.dumps(db.register_file(args.path, patient_id=args.patient), ensure_ascii=False))
        elif args.cmd == "list-patients":
            print(json.dumps(db.list_patients(), ensure_ascii=False, indent=2))
        elif args.cmd == "list-records":
            print(json.dumps(db.list_records(args.patient, args.record_type),
                             ensure_ascii=False, indent=2))
        elif args.cmd == "search":
            print(json.dumps(db.search_records(args.query), ensure_ascii=False, indent=2))
        elif args.cmd == "export-deidentified":
            print(json.dumps(db.export_deidentified(args.out), ensure_ascii=False))
        elif args.cmd == "stats":
            print(json.dumps(db.stats(), ensure_ascii=False))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
