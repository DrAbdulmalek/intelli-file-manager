#!/usr/bin/env python3
"""CLI لتصدير القصاصات التدريبية المعتمدة (JSONL) — ورفعها اختياريًا إلى HuggingFace.

Examples:
    python scripts/export_training_data.py                    # export only
    python scripts/export_training_data.py --include-unchanged
    python scripts/export_training_data.py --push --token hf_xxx
    python scripts/export_training_data.py --stats            # counts only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.db.snippet_db import SnippetDB  # noqa: E402
from src.services.hf_exporter import HFExporter  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="تصدير القصاصات التدريبية")
    parser.add_argument("--db", default=None, help="مسار قاعدة SQLite (اختياري)")
    parser.add_argument("--out", default=None, help="مجلد التصدير (افتراضي: data/hf_export)")
    parser.add_argument("--include-unchanged", action="store_true",
                        help="تصدير القصاصات التي لم يتغير نصها عن OCR الخام")
    parser.add_argument("--min-confidence", type=float, default=0.0,
                        help="حد أدنى للثقة (0 = الكل بما فيها غير المعروفة)")
    parser.add_argument("--push", action="store_true", help="رفع إلى HuggingFace بعد التصدير")
    parser.add_argument("--token", default="", help="توكن HuggingFace (للرفع الصريح فقط)")
    parser.add_argument("--stats", action="store_true", help="عرض الإحصائيات فقط")
    args = parser.parse_args()

    db = SnippetDB(args.db) if args.db else SnippetDB()
    stats = db.stats()
    print("الإحصائيات:", stats)
    if args.stats:
        return 0

    exporter = HFExporter(db, export_dir=args.out)
    out = exporter.export(
        min_confidence=args.min_confidence,
        include_unchanged=args.include_unchanged,
    )
    print(f"تم التصدير: {out}")

    if args.push:
        if not args.token:
            print("خطأ: --push يتطلب --token صريحًا", file=sys.stderr)
            return 2
        url = exporter.push_to_hf(args.token)
        print(f"تم الرفع: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
