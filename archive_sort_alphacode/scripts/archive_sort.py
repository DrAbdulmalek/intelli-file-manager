#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""archive_sort.py — سكريبت فرز الأرشيف (قراءة فقط — dry-run إلزامي).

هذا السكريبت يطبّق أحكام "القرار الموحد لفرز الأرشيف" (2026-11-24) على
قرص My Passport باستخدام محرك قواعد intelli-file-manager. وهو آمن بطبيعته:
  - يمسح القرص للقراءة فقط عبر FileInventory (لا يعدّل أي بايت).
  - يولّد خطة محاكاة (DryRunPlan) عبر RuleEngine.dry_run — لا نقل ولا حذف.
  - ينتج تقرير HTML بفلاتر حسب الفئة لمراجعة المالك بندياً.
  - تنفيذ فعلي غير متاح هنا إطلاقاً؛ التنفيذ مرحلة منفصلة معتمدة يدوياً.

المراحل التي يغطيها (0,2,3 من القرار):
  المرحلة 0 (تجميد القرص للقراءة): ini مشروط — السكريبت لا يكتب للقرص أصلاً.
  المرحلة 2 (مسح قراءة كامل): FileInventory مع استبعاد النظامي والحساسيات.
  المرحلة 3 (dry-run HTML بفلاتر): DryRunPlan + تقرير HTML.

الاستخدام (من جذر المستودع — لا حاجة لـPYTHONPATH، المسار يُحل تلقائياً):
    python3 archive_sort_alphacode/scripts/archive_sort.py \
        --root "/run/media/xorthomson/My Passport" \
        --out archive_sort_alphacode/LOGS/dry_run_report.html

بلا --out يُطبع ملخص JSON إلى stdout فقط. لا ينفّذ أي نقل.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ضمان إمكانية الاستيراد عند التشغيل المباشر (نمط المشروع: src.core.*)
_REPO_ROOT = Path(__file__).resolve().parent.parent      # archive_sort_alphacode/
_SRC_ROOT = Path(__file__).resolve().parents[2]          # جذر المستودع (حيث src/)
for _p in (_SRC_ROOT, _REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from src.core.file_inventory import FileInventory  # noqa: E402
from src.core.rule_engine import RuleEngine  # noqa: E402
from src.core.rule_schemas import Ruleset  # noqa: E402

# المجلدات النظامية/المستبعدة وفق القرار (بلا قراءة محتواها)
_EXCLUDED_TOP = {
    "$RECYCLE.BIN", "System Volume Information", "found.000",
    "DuplicateCleanerPro",  # بند 6 المعتمد: الإبقاء خارج الخطة الآلية
}
_EXCLUDED_PREFIXES = ("found.",)


def _should_exclude(rel_parts: tuple[str, ...]) -> bool:
    """هل المسار النسبي ضمن المستبعدات النظامية؟"""
    if not rel_parts:
        return False
    head = rel_parts[0]
    if head in _EXCLUDED_TOP:
        return True
    if any(head.startswith(p) for p in _EXCLUDED_PREFIXES):
        return True
    return False


def _scan_fast(root: str, max_depth: int = 0):
    """مسح سريع للقراءة فقط بلا SHA-256 (لا كشف تكرار) — معاينة عملية.

    يتجاوز FileInventory الثقيل (الذي يحسب SHA-256 لكل ملف = ساعات على قرص
    1.6TB). يُنتج FileRecord خفيفاً يكفي للتصنيف بالامتداد لـ dry-run.
    كشف التكرار (SHA-256) يبقى خيار المرحلة الفعلية عبر include_content/المسح
    الكامل. لا يقرأ محتوى أي ملف — stat فقط (أسرع وأكثر أماناً).

    max_depth: 0 = بلا حد (مسح كامل)؛ >0 = عمق أقصى للمسح (معاينة سريعة).
    """
    from src.db.schemas import FileCategory, FileMetadata, FileRecord
    root_p = Path(root).resolve()
    records = []
    total = 0
    total_size = 0
    excluded = 0
    stat_errors = 0
    for p in root_p.rglob("*"):
        if p.is_symlink() or not p.is_file():
            continue
        try:
            rel = p.relative_to(root_p)
        except ValueError:
            continue
        if max_depth and len(rel.parts) > max_depth:
            continue
        if _should_exclude(rel.parts):
            excluded += 1
            continue
        try:
            st = p.stat()
        except OSError:
            stat_errors += 1
            continue
        total += 1
        total_size += st.st_size
        ext = p.suffix.lower().lstrip(".")
        cat = FileCategory.from_extension(ext).value
        md = FileMetadata(
            file_name=p.name, file_path=str(p), file_size=st.st_size,
            extension=ext, category=cat,
            modified_at=datetime.fromtimestamp(st.st_mtime).isoformat(),
        )
        records.append(FileRecord.from_metadata(metadata=md, document_text=""))
    size_h = f"{total_size/1e12:.2f} TB" if total_size >= 1e12 else f"{total_size/1e9:.2f} GB"
    stats = {
        "mode": "fast (no-sha256)",
        "total_files": total,
        "indexed_files": len(records),
        "skipped_files": excluded,
        "errors_count": stat_errors,
        "collected_records": len(records),
        "total_size_human": size_h,
        "note": "SHA-256 وكشف التكرار معطّلان في وضع المعاينة؛ فعّلهما في المسح الكامل.",
    }
    return records, stats


def scan(root: str, include_content: bool = False, fast: bool = False, max_depth: int = 0):
    """مسح قراءة فقط — يُرجع (records, stats_dict).

    fast=True: مسح خفيف بلا SHA-256 (معاينة سريعة على الأقراص الكبيرة).
    fast=False: مسح كامل عبر FileInventory مع SHA-256 وكشف التكرار (أبطأ).
    max_depth: للوضع السريع فقط — عمق أقصى (0 = بلا حد).
    """
    if fast:
        return _scan_fast(root, max_depth=max_depth)
    inventory = FileInventory(include_content=include_content)
    records = []
    for rec in inventory.scan(root, recursive=True):
        rel = Path(rec.metadata.file_path).resolve().relative_to(Path(root).resolve())
        if _should_exclude(rel.parts):
            continue
        records.append(rec)
    stats = inventory.last_stats.to_dict() if inventory.last_stats else {}
    stats["collected_records"] = len(records)
    return records, stats


def build_plan(records, ruleset_path: str, base_dir: str):
    """إنتاج خطة محاكاة (بلا كتابة)."""
    ruleset = Ruleset.from_yaml(ruleset_path)
    engine = RuleEngine(ruleset)
    return engine.dry_run(records, base_dir=base_dir)


def _esc(text: object) -> str:
    s = str(text)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_html(plan, stats: dict, root: str) -> str:
    """تقرير HTML بفلاتر حسب الفئة/الوجهة — لا JS خارجي."""
    # توزيع الوجهات حسب وجهة القاعدة (مجلد الوجهة) لإجراءات النقل فقط —
    # تصحيح مراجعة التقرير: كان يجمع target_path (مسار الملف الهدف) فتتحول
    # البطاقات إلى بطاقة لكل ملف ولا تصلح للمراجعة.
    cats: dict[str, int] = {}
    for a in plan.planned_actions:
        if a.action.type == "move":
            tgt = a.action.target or "?"
            cats[tgt] = cats.get(tgt, 0) + 1
    rows = []
    for a in plan.planned_actions:
        rows.append(
            "<tr>"
            f"<td>{_esc(a.rule_name)}</td>"
            f"<td>{_esc(Path(a.file_path).name)}</td>"
            f"<td>{_esc(a.action.type)}</td>"
            f"<td>{_esc(a.target_path or a.action.target or '')}</td>"
            f"<td class='path'>{_esc(a.file_path)}</td>"
            "</tr>"
        )
    skipped = "".join(
        f"<li>{_esc(s.get('file_name', s.get('file_path', '?')))} — {_esc(s.get('reason',''))}</li>"
        for s in plan.skipped_files[:500]
    )
    summary_cards = "".join(
        f"<div class='card'><b>{_esc(k)}</b><br><span class='big'>{v}</span></div>"
        for k, v in sorted(cats.items(), key=lambda kv: -kv[1])
    )
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>خطة فرز الأرشيف — محاكاة</title><style>
body{{font-family:'Noto Sans','Segoe UI',sans-serif;background:#f7f8fa;color:#1f2328;margin:0;padding:24px}}
h1{{font-size:22px;border-bottom:2px solid #0969da;padding-bottom:8px}}
.cards{{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}}
.card{{background:#fff;border:1px solid #d0d7de;border-radius:8px;padding:12px 16px;min-width:120px}}
.big{{font-size:20px;color:#0969da}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden}}
th,td{{border:1px solid #d0d7de;padding:6px 10px;text-align:right;font-size:13px}}
th{{background:#eaeef2;position:sticky;top:0}}
.path{{font-family:monospace;font-size:11px;color:#656d76;max-width:420px;overflow:hidden;text-overflow:ellipsis}}
.meta{{color:#656d76;font-size:13px}}
</style></head><body>
<h1>خطة فرز الأرشيف — تقرير محاكاة (dry-run)</h1>
<p class="meta">الجذر: {_esc(root)}<br>
المرحلة 3 من القرار الموحد — لا نقل ولا حذف. أُنشئ: {_esc(datetime.now(timezone.utc).isoformat())}</p>
<h2>ملخص المسح</h2>
<p class="meta">إجمالي الملفات: {stats.get('total_files','?')} ·
المفهرسة: {stats.get('indexed_files','?')} ·
المستبعدة نظامياً: {stats.get('skipped_files','?')} ·
الأخطاء: {stats.get('errors_count','?')} ·
الحجم الكلي: {_esc(stats.get('total_size_human','?'))} ·
الملفات المتأثرة بالخطة: {plan.files_affected} ·
بلا قاعدة مطابقة: {len(plan.skipped_files)}</p>
<h2>توزيع الوجهات (عدد الإجراءات)</h2>
<div class="cards">{summary_cards or '<div class=card>لا إجراءات</div>'}</div>
<h2>الإجراءات المخططة ({plan.total_actions})</h2>
<table><thead><tr><th>القاعدة</th><th>الملف</th><th>الإجراء</th><th>الوجهة</th><th>المسار</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<h2>ملفات متخطاة — لا قاعدة مطابقة (الإجمالي: {len(plan.skipped_files)}؛ معروض: أول {min(500, len(plan.skipped_files))})</h2><ul>{skipped or '<li>لا شيء</li>'}</ul>
</body></html>"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="فرز الأرشيف — قراءة فقط + محاكاة")
    ap.add_argument("--root", required=True, help="جذر القرص المراد مسحه")
    ap.add_argument("--rules", default=str(_REPO_ROOT / "rules" / "archive_sort_rules.yaml"))
    ap.add_argument("--out", default="", help="مسار تقرير HTML (اختياري)")
    ap.add_argument("--include-content", action="store_true",
                    help="استخراج نص المستندات (أبطأ؛ الافتراضي معطّل)")
    ap.add_argument("--fast", action="store_true",
                    help="مسح سريع بلا SHA-256 (معاينة عملية على الأقراص الكبيرة)")
    ap.add_argument("--max-depth", type=int, default=0,
                    help="للوضع السريع: عمق أقصى للمسح (0 = بلا حد)")
    args = ap.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"خطأ: المسار غير موجود أو ليس مجلداً: {root}", file=sys.stderr)
        return 2

    records, stats = scan(str(root), include_content=args.include_content,
                          fast=args.fast, max_depth=args.max_depth)
    plan = build_plan(records, args.rules, base_dir=str(root))

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_html(plan, stats, str(root)), encoding="utf-8")
        print(f"✅ تقرير HTML: {out}")
    # ملخص JSON إلى stdout دائماً (دليل خام)
    summary = {
        "root": str(root),
        "scan": stats,
        "planned_actions": plan.total_actions,
        "files_affected": plan.files_affected,
        "action_type_counts": plan.action_type_counts(),
        "skipped_count": len(plan.skipped_files),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())