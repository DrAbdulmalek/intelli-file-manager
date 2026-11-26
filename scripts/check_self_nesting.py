#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_self_nesting.py (v2) — كشف التداخل الذاتي (self-nesting) قبل التنفيذ.

الغرض: قبل أي عملية فرز، التأكد أن جذر المسح ليس على وشك أن يُنقل
داخل نفسه (نفس اسم قاعدة الوجهة). فحص قراءة فقط — لا يعدّل أي بايت.

المواصفات (Phase 0 / P0.1):
  - مسح واحد os.walk(topdown=True, onerror=..., followlinks=False).
  - لا resolve() على الجذر. جذر symlink مرفوض افتراضيًا (exit 4)؛
    يُقبل بـ --allow-symlink-root فقط.
  - تُجمع كل أخطاء الوصول؛ أي خطأ = exit 3 (لا تُعلن "clean").
  - عدّ الملفات/المجلدات داخل نفس المسح.
  - لا يطبع أي مسار (خصوصية) — أسماء/أعداد فقط عند الحاجة.
  - حارس التشغيل if __name__ == "__main__".

رموز الخروج:
  0 = نظيف (لا تداخل، لا أخطاء)
  1 = تداخل ذاتي مُكتشف
  2 = جذر غير صالح (غير موجود / ليس مجلدًا)
  3 = مسح غير مكتمل (أخطاء وصول)
  4 = الجذر symlink (رفض افتراضيًا)
"""
from __future__ import annotations

import argparse
import os
import sys

EXIT_CLEAN = 0
EXIT_NESTING = 1
EXIT_BAD_ROOT = 2
EXIT_INCOMPLETE = 3
EXIT_SYMLINK_ROOT = 4


def scan(root: str, *, allow_symlink_root: bool = False):
    """يمسح الشجرة مرة واحدة ويُرجع (exit_code, stats).

    لا يطبع أي مسار. stats قاموس بالأعداد فقط.
    """
    stats = {
        "files": 0,
        "dirs": 0,
        "errors": 0,
        "nesting_hits": 0,
    }

    # فحص الجذر: يجب أن يكون مجلدًا موجودًا (لا resolve).
    if not os.path.exists(root):
        return EXIT_BAD_ROOT, stats
    if os.path.islink(root) and not allow_symlink_root:
        return EXIT_SYMLINK_ROOT, stats
    if not os.path.isdir(root):
        return EXIT_BAD_ROOT, stats

    # اسم المجلد الجذر (باسم واحد فقط — لا مسار كامل).
    root_name = os.path.basename(os.path.normpath(root))

    def onerror(_err):
        # أي خطأ وصول أثناء المسح = مسح غير مكتمل.
        stats["errors"] += 1

    # مسح واحد topdown، بلا متابعة روابط.
    for dirpath, dirnames, filenames in os.walk(
        root, topdown=True, onerror=onerror, followlinks=False
    ):
        # عدّ المجلدات الفرعية (بلا أسماء).
        stats["dirs"] += len(dirnames)
        stats["files"] += len(filenames)

        # كشف التداخل الذاتي: هل يوجد مجلد فرعي بنفس اسم الجذر؟
        # (هذا بالضبط ما حدث في وسائط/ — المجلد نُقل داخل نفسه).
        for d in dirnames:
            if d == root_name:
                stats["nesting_hits"] += 1

    if stats["errors"] > 0:
        return EXIT_INCOMPLETE, stats
    if stats["nesting_hits"] > 0:
        return EXIT_NESTING, stats
    return EXIT_CLEAN, stats


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="كشف التداخل الذاتي (self-nesting) — قراءة فقط.",
    )
    parser.add_argument("root", help="الجذر المراد فحصه")
    parser.add_argument(
        "--allow-symlink-root",
        action="store_true",
        help="قبول جذر symlink (الافتراضي: رفض بـ exit 4)",
    )
    args = parser.parse_args(argv)

    code, stats = scan(args.root, allow_symlink_root=args.allow_symlink_root)

    # مخرجات بأعداد فقط — لا مسارات.
    labels = {
        EXIT_CLEAN: "نظيف",
        EXIT_NESTING: "تداخل ذاتي",
        EXIT_BAD_ROOT: "جذر غير صالح",
        EXIT_INCOMPLETE: "مسح غير مكتمل",
        EXIT_SYMLINK_ROOT: "جذر symlink",
    }
    print(f"result={labels[code]} exit={code}")
    print(
        f"files={stats['files']} dirs={stats['dirs']} "
        f"errors={stats['errors']} nesting_hits={stats['nesting_hits']}"
    )
    return code


if __name__ == "__main__":
    sys.exit(main())