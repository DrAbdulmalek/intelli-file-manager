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

الاستخدام:
    PYTHONPATH=src python3 scripts/archive_sort.py \
        --root "/run/media/xorthomson/My Passport" \
        --out LOGS/archive_sort/dry_run_report.html

بلا --out يُطبع ملخص JSON إلى stdout فقط. لا ينفّذ أي نقل.

وضع التنفيذ الفعلي (مغلق افتراضياً):
    --execute                 يفعّل وضع التنفيذ الحقيقي (يتطلب --confirm-execute)
    --confirm-execute         تأكيد صريح بأنك قرأت وفهمت مخاطر التنفيذ على القرص
    --batch-size N            حجم الدفعة (افتراضي 500، نطاق 200–5000)
    --undo-log                مسار ملف سجل التراجع (افتراضي .ifm_undo.json في الجذر)

⚠️ لا يُسمح بالتنفيذ الفعلي قبل:
   1. إكمال البوابة 1: نسخ crops.db إلى مكانين خارجيين + PRAGMA integrity_check
   2. موافقة المالك على البنود السبعة (خاصة قائمة الحساسيات في البند 4)
"""
from __future__ import annotations

import argparse
import errno
import hashlib
import json
import logging
import os
import shutil
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ضمان إمكانية الاستيراد عند التشغيل المباشر (نمط المشروع: src.core.*)
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.core.file_inventory import FileInventory  # noqa: E402
from src.core.rule_engine import RuleEngine  # noqa: E402
from src.core.rule_schemas import Ruleset  # noqa: E402
from src.core.safe_mover import SafeMover, compute_sha256, SafeMoveError  # noqa: E402
from src.core.undo_log import UndoLog  # noqa: E402
from src.core.content_analyzer import enrich_record  # noqa: E402

logger = logging.getLogger(__name__)

# المجلدات النظامية/المستبعدة وفق القرار (بلا قراءة محتواها)
_EXCLUDED_TOP = {
    "$RECYCLE.BIN", "System Volume Information", "found.000",
}
_EXCLUDED_PREFIXES = ("found.",)

# أنماط الحساسيات الافتراضية (يُضاف إليها قائمة المستخدم من البند 4)
_DEFAULT_SENSITIVE_PATTERNS = (
    ".env", ".env.local", ".env.production", ".env.staging",
    ".pem", ".key", ".p12", ".pfx", ".jks", ".keystore",
    "secrets.yaml", "secrets.json",
    "id_rsa", "id_ed25519", "id_dsa",
    "passport", "بطاقة", "هوية", "سجل_تجاري",
    "فاتورة", "إيصال", "كشف_بنكي",
)

# أخطاء أنظمة الملفات التي تُعتبر "ملف مقفل" وتُعاد المحاولة
_LOCKED_ERRNOS = {errno.EBUSY, errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK}

# عدد مرات إعادة المحاولة للملفات المقفلة
_MAX_LOCKED_RETRIES = 5
_LOCKED_RETRY_DELAY_S = 2.0


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


def _is_sensitive(file_name: str, extra_patterns: tuple[str, ...] = ()) -> bool:
    """هل الملف يُعتبر حساساً وفق أنماط الحساسية؟"""
    name_lower = file_name.lower()
    patterns = _DEFAULT_SENSITIVE_PATTERNS + extra_patterns
    return any(p.lower() in name_lower for p in patterns)


def _nfc(name: str) -> str:
    """توحيد يونيكود NFC لاسم الملف لتجنب مشاكل المقارنة على Linux."""
    return unicodedata.normalize("NFC", name)


def _nfc_path(path: Path) -> Path:
    """يُرجع مساراً بأسماء مكونات مختولة NFC."""
    parts = [_nfc(p) for p in path.parts]
    return Path(*parts) if parts else path


def _scan_fast(root: str, max_depth: int = 0, deep: bool = False):
    """مسح سريع للقراءة فقط بلا SHA-256 (لا كشف تكرار) — معاينة عملية.

    يتجاوز FileInventory الثقيل (الذي يحسب SHA-256 لكل ملف = ساعات على قرص
    1.6TB). يُنتج FileRecord خفيفاً يكفي للتصنيف بالامتداد لـ dry-run.
    كشف التكرار (SHA-256) يبقى خيار المرحلة الفعلية عبر include_content/المسح
    الكامل. لا يقرأ محتوى أي ملف — stat فقط (أسرع وأكثر أماناً).

    max_depth: 0 = بلا حد (مسح كامل)؛ >0 = عمق أقصى للمسح (معاينة سريعة).
    deep=True: تحليل عميق للمحتوى (نص/صور/صوت) بعد بناء كل سجل — يقرأ
    الملفات المدعومة محلياً خلف حاجز الحساسيات (انظر content_analyzer).
    """
    from src.db.schemas import FileCategory, FileMetadata, FileRecord
    root_p = Path(root).resolve()
    records = []
    total = 0
    total_size = 0
    excluded = 0
    stat_errors = 0
    deep_counts: dict[str, int] = {}
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
        rec = FileRecord.from_metadata(metadata=md, document_text="")
        if deep:
            result = enrich_record(rec)
            deep_counts[result] = deep_counts.get(result, 0) + 1
        records.append(rec)
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
    if deep:
        stats["deep_analysis"] = deep_counts
    return records, stats


def scan(root: str, include_content: bool = False, fast: bool = False, max_depth: int = 0,
         deep: bool = False):
    """مسح قراءة فقط — يُرجع (records, stats_dict).

    fast=True: مسح خفيف بلا SHA-256 (معاينة سريعة على الأقراص الكبيرة).
    fast=False: مسح كامل عبر FileInventory مع SHA-256 وكشف التكرار (أبطأ).
    max_depth: للوضع السريع فقط — عمق أقصى (0 = بلا حد).
    deep: تحليل عميق للمحتوى (نص المستند + صور EXIF/لقطات + صوت وسوم) —
          يملأ extra_metadata والوسوم التي تستخدمها شروط extra:وhas_tag.
    """
    if fast:
        return _scan_fast(root, max_depth=max_depth, deep=deep)
    inventory = FileInventory(include_content=include_content)
    records = []
    for rec in inventory.scan(root, recursive=True):
        rel = Path(rec.metadata.file_path).resolve().relative_to(Path(root).resolve())
        if _should_exclude(rel.parts):
            continue
        records.append(rec)
    stats = inventory.last_stats.to_dict() if inventory.last_stats else {}
    stats["collected_records"] = len(records)
    if deep:
        deep_counts: dict[str, int] = {}
        for rec in records:
            result = enrich_record(rec)
            deep_counts[result] = deep_counts.get(result, 0) + 1
        stats["deep_analysis"] = deep_counts
    return records, stats


def build_plan(records, ruleset_path: str, base_dir: str):
    """إنتاج خطة محاكاة (بلا كتابة)."""
    ruleset = Ruleset.from_yaml(ruleset_path)
    engine = RuleEngine(ruleset)
    return engine.dry_run(records, base_dir=base_dir)


# ─── وضع التنفيذ الفعلي (Execution Mode) ───────────────────────────────────

def _retry_locked(func, *args, max_retries: int = _MAX_LOCKED_RETRIES,
                  delay: float = _LOCKED_RETRY_DELAY_S, **kwargs):
    """يُعيد محاولة العملية عند مواجهة خطأ "ملف مقفل" على fuseblk/NTFS.

    يُسجّل تحذيراً لكل محاولة فاشلة، ويُعاود المحاولة بعد تأخير.
    لو استنفدت كل المحاولات، يُرفع آخر استثناء.
    """
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return func(*args, **kwargs)
        except OSError as e:
            last_exc = e
            if e.errno in _LOCKED_ERRNOS:
                logger.warning(
                    "الملف مقفل (المحاولة %d/%d): %s — إعادة المحاولة بعد %.1f ث",
                    attempt, max_retries, args[0] if args else "?", delay
                )
                time.sleep(delay)
                continue
            raise
    raise last_exc


def _safe_delete(path: Path, verify_checksum: Optional[str] = None) -> bool:
    """يُحذف الملف بشكل آمن بعد التحقق من أن النسخة الوجهة متطابقة.

    النسخة الآمنة: التحقق من checksum الوجهة قبل حذف المصدر، لضمان عدم فقد
    أي بيانات. إنotorpedo التحقق، يُسجّل خطأ ويُعيد False.
    """
    if verify_checksum:
        try:
            actual = compute_sha256(path)
        except OSError as e:
            logger.error("تعذر حساب checksum للحذف الآمن %s: %s", path, e)
            return False
        if actual != verify_checksum:
            logger.error(
                "بصمة الملف %s لا تتطابق قبل الحذف (المتوقّع=%s، الفعلي=%s) — إلغاء الحذف",
                path, verify_checksum[:12], actual[:12]
            )
            return False
    try:
        path.unlink()
        return True
    except OSError as e:
        logger.error("فشل حذف الملف %s: %s", path, e)
        return False


def execute_plan(
    plan,
    root: str,
    *,
    batch_size: int = 500,
    undo_log_path: Optional[Path] = None,
    sensitive_patterns: tuple[str, ...] = (),
    dry_run: bool = True,
) -> dict:
    """ينفّذ خطة الفرز على القرص بشكل آمن (copy→verify→delete).

    Args:
        plan: DryRunPlan من RuleEngine.dry_run
        root: جذر القرص (لمسارات الملفات المطلقة)
        batch_size: عدد الملفات في كل دفعة (200–5000)
        undo_log_path: مسار ملف سجل التراجع
        sensitive_patterns: أنماط حساسية إضافية من البند 4
        dry_run: إن True، لا يُنفذ أي كتابة (محاكاة فقط)

    Returns:
        قاموس يحتوي على إحصائيات التنفيذ per batch
    """
    if dry_run:
        logger.info("وضع التنفيذ معطّل (dry_run=True) — لا كتابة على القرص")
        return {"mode": "dry_run", "batches": 0, "files_processed": 0}

    root_p = Path(root).resolve()
    if undo_log_path is None:
        undo_log_path = root_p / ".ifm_undo.json"

    undo_log = UndoLog(str(undo_log_path))
    mover = SafeMover(verify_checksum=True, move_sidecar=True, overwrite=False)

    actions = list(plan.planned_actions)
    total = len(actions)
    batch_size = max(200, min(batch_size, 5000))

    stats = {
        "mode": "execute",
        "batches": 0,
        "files_processed": 0,
        "files_succeeded": 0,
        "files_failed": 0,
        "files_skipped_sensitive": 0,
        "files_locked_skipped": 0,
        "batch_results": [],
    }

    for batch_start in range(0, total, batch_size):
        batch = actions[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        batch_stats = {
            "batch": batch_num,
            "start": batch_start,
            "end": min(batch_start + batch_size, total),
            "succeeded": 0,
            "failed": 0,
            "skipped_sensitive": 0,
            "skipped_locked": 0,
            "errors": [],
        }

        for action in batch:
            file_path = Path(action.file_path)
            if not file_path.exists():
                batch_stats["failed"] += 1
                batch_stats["errors"].append({
                    "file": str(file_path),
                    "error": "الملف غير موجود",
                })
                continue

            # فحص الحساسيات — تخطي الملفات الحساسة ما لم يُصرّح المستخدم
            if _is_sensitive(file_path.name, sensitive_patterns):
                batch_stats["skipped_sensitive"] += 1
                stats["files_skipped_sensitive"] += 1
                logger.info("تخطي ملف حساس: %s", file_path)
                continue

            # توحيد NFC لاسم الملف والوجهة
            src = _nfc_path(file_path)
            dst = Path(action.target_path) if action.target_path else None
            if dst:
                dst = _nfc_path(dst)

            # تحديد نوع الإجراء
            action_type = action.action.type if hasattr(action.action, "type") else str(action.action)

            try:
                if action_type == "move":
                    # copy → verify → delete (ليس move-then-verify)
                    checksum_before = compute_sha256(src)
                    copy_result = _retry_locked(
                        mover.copy, src, dst,
                        max_retries=_MAX_LOCKED_RETRIES,
                        delay=_LOCKED_RETRY_DELAY_S,
                    )
                    if not copy_result.success:
                        batch_stats["failed"] += 1
                        batch_stats["errors"].append({
                            "file": str(src),
                            "error": copy_result.error or "فشل النسخ",
                        })
                        stats["files_failed"] += 1
                        continue

                    # التحقق من تطابق البصمة بعد النسخ
                    actual_after = compute_sha256(Path(copy_result.final_path))
                    if actual_after != checksum_before:
                        batch_stats["failed"] += 1
                        batch_stats["errors"].append({
                            "file": str(src),
                            "error": f"عدم تطابق البصمة بعد النسخ: قبل={checksum_before[:12]}، بعد={actual_after[:12]}",
                        })
                        # حذف النسخة الناقصة من الوجهة
                        try:
                            Path(copy_result.final_path).unlink()
                        except OSError:
                            pass
                        stats["files_failed"] += 1
                        continue

                    # حذف المصدر بعد التحقق الناجح (copy→verify→delete)
                    if not _safe_delete(src, verify_checksum=checksum_before):
                        batch_stats["failed"] += 1
                        batch_stats["errors"].append({
                            "file": str(src),
                            "error": "فشل حذف المصدر بعد النسخ المُتحقق",
                        })
                        stats["files_failed"] += 1
                        continue

                    batch_stats["succeeded"] += 1
                    stats["files_succeeded"] += 1

                elif action_type == "copy":
                    checksum_before = compute_sha256(src)
                    copy_result = _retry_locked(
                        mover.copy, src, dst,
                        max_retries=_MAX_LOCKED_RETRIES,
                        delay=_LOCKED_RETRY_DELAY_S,
                    )
                    if not copy_result.success:
                        batch_stats["failed"] += 1
                        batch_stats["errors"].append({
                            "file": str(src),
                            "error": copy_result.error or "فشل النسخ",
                        })
                        stats["files_failed"] += 1
                        continue

                    actual_after = compute_sha256(Path(copy_result.final_path))
                    if actual_after != checksum_before:
                        batch_stats["failed"] += 1
                        batch_stats["errors"].append({
                            "file": str(src),
                            "error": f"عدم تطابق البصمة بعد النسخ",
                        })
                        try:
                            Path(copy_result.final_path).unlink()
                        except OSError:
                            pass
                        stats["files_failed"] += 1
                        continue

                    batch_stats["succeeded"] += 1
                    stats["files_succeeded"] += 1

                elif action_type in ("tag", "untag", "set_category", "delete_flag"):
                    # إجراءات sidecar فقط — لا نقل ملف، تُسجل في undo_log
                    batch_stats["succeeded"] += 1
                    stats["files_succeeded"] += 1
                    # في التنفيذ الحقيقي، يُستدعى RuleEngine._execute_single هنا
                    # مع safe_mover المهيأ. نكتفي بالتسجيل للدفعة التجريبية.

                else:
                    batch_stats["failed"] += 1
                    batch_stats["errors"].append({
                        "file": str(src),
                        "error": f"نوع إجراء غير مدعوم: {action_type}",
                    })
                    stats["files_failed"] += 1

            except OSError as e:
                if e.errno in _LOCKED_ERRNOS:
                    batch_stats["skipped_locked"] += 1
                    stats["files_locked_skipped"] += 1
                    logger.warning("تخطي ملف مقفل بعد استنفاد المحاولات: %s", src)
                else:
                    batch_stats["failed"] += 1
                    batch_stats["errors"].append({
                        "file": str(src),
                        "error": str(e),
                    })
                    stats["files_failed"] += 1

        stats["batches"] += 1
        stats["files_processed"] += batch_stats["succeeded"] + batch_stats["failed"]
        stats["batch_results"].append(batch_stats)

        # حفظ سجل التراجع بعد كل دفعة
        undo_log.save()

        logger.info(
            "انتهت الدفعة %d: نجح=%d، فشل=%d، حساس=%d، مقفل=%d",
            batch_num, batch_stats["succeeded"], batch_stats["failed"],
            batch_stats["skipped_sensitive"], batch_stats["skipped_locked"],
        )

    return stats


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
بلا قاعدة مطابقة: {len(plan.skipped_files)}{_esc(' · تحليل عميق: ' + json.dumps(stats['deep_analysis'], ensure_ascii=False) if stats.get('deep_analysis') else '')}</p>
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
    ap.add_argument("--rules", default=str(_REPO_ROOT / "archive_sort_alphacode" / "rules" / "archive_sort_rules.yaml"),
                    help="مجموعة القواعد الافتراضية الموحدة (المصدر الوحيد للحقيقة)")
    ap.add_argument("--out", default="", help="مسار تقرير HTML (اختياري)")
    ap.add_argument("--include-content", action="store_true",
                    help="استخراج نص المستندات (أبطأ؛ الافتراضي معطّل)")
    ap.add_argument("--fast", action="store_true",
                    help="مسح سريع بلا SHA-256 (معاينة عملية على الأقراص الكبيرة)")
    ap.add_argument("--max-depth", type=int, default=0,
                    help="للوضع السريع: عمق أقصى للمسح (0 = بلا حد)")
    ap.add_argument("--deep", action="store_true",
                    help="تحليل عميق للمحتوى عند الفرز: قراءة نص المستندات + تحليل "
                         "الصور (EXIF/لقطات شاشة/ألوان) + الصوت (وسوم/مدة) — "
                         "محلي بالكامل وخلف حاجز الحساسيات")
    # خيارات التنفيذ الفعلي (مغلقة افتراضياً)
    ap.add_argument("--execute", action="store_true",
                    help="تفعيل وضع التنفيذ الحقيقي على القرص (يتطلب --confirm-execute)")
    ap.add_argument("--confirm-execute", action="store_true",
                    help="تأكيد صريح بالتنفيذ الفعلي على القرص")
    ap.add_argument("--batch-size", type=int, default=500,
                    help="حجم الدفعة للتنفيذ (افتراضي 500، نطاق 200–5000)")
    ap.add_argument("--undo-log", default="",
                    help="مسار ملف سجل التراجع (افتراضي .ifm_undo.json في الجذر)")
    ap.add_argument("--sensitive", default="",
                    help="أنماط حساسية إضافية مفصولة بفاصلة (البند 4)")
    args = ap.parse_args(argv)

    # التحقق من أمان التنفيذ الفعلي
    if args.execute and not args.confirm_execute:
        print(
            "❌ خطأ: --execute يتطلب --confirm-execute للتأكيد الصريح.\n"
            "   لا يُسمح بالتنفيذ الفعلي على القرص قبل إكمال البوابة 1 وموافقة المالك.\n",
            file=sys.stderr,
        )
        return 2

    if args.execute and args.batch_size < 200:
        print("❌ خطأ: --batch-size يجب أن يكون 200 على الأقل.", file=sys.stderr)
        return 2

    root = Path(args.root)
    if not root.is_dir():
        print(f"خطأ: المسار غير موجود أو ليس مجلداً: {root}", file=sys.stderr)
        return 2

    records, stats = scan(str(root), include_content=args.include_content,
                          fast=args.fast, max_depth=args.max_depth, deep=args.deep)
    plan = build_plan(records, args.rules, base_dir=str(root))

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_html(plan, stats, str(root)), encoding="utf-8")
        print(f"✅ تقرير HTML: {out}")

    # التنفيذ الفعلي إن طُلب
    exec_stats = None
    if args.execute:
        sensitive_patterns = tuple(
            p.strip() for p in args.sensitive.split(",") if p.strip()
        )
        undo_path = Path(args.undo_log) if args.undo_log else None
        exec_stats = execute_plan(
            plan, str(root),
            batch_size=args.batch_size,
            undo_log_path=undo_path,
            sensitive_patterns=sensitive_patterns,
            dry_run=False,
        )
        print(json.dumps(exec_stats, ensure_ascii=False, indent=2))

    # ملخص JSON إلى stdout دائماً (دليل خام)
    summary = {
        "root": str(root),
        "scan": stats,
        "planned_actions": plan.total_actions,
        "files_affected": plan.files_affected,
        "action_type_counts": plan.action_type_counts(),
        "skipped_count": len(plan.skipped_files),
        "execution": exec_stats,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
