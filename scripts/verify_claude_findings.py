# -*- coding: utf-8 -*-
"""وثيقة تاريخية: إعادة إنتاج عيوب P0 الثمانية من مراجعة PR #63 (feat/p0-safety-hardening).

كل تجربة تطبع REPRODUCED (العيب موجود) أو NOT REPRODUCED مع الأدلة القياسية.
تعمل فقط ضد شجرة PR #63 القبل-الإصلاح (فرع feat/p0-safety-hardening) حيث كانت
src/core/sensitive_guard.py ودالتها الداخلية _claim_destination موجودة.
على السلسلة الحالية (fix/p0-*) العيوب مُصلَحة والوحدة أصبحت sensitive_barrier —
لذا التحقق على الشجرة الحالية يكون بأوامر pytest الموثقة في
docs/alpha-session-2026-11-20/CHATGPT_REVIEW_LOG_2026-11-20.md.
يكتشف جذر المستودع من موقعه تلقائياً (لا مسارات مطلقة).
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

if not (REPO_ROOT / "src" / "core" / "sensitive_guard.py").exists():
    print("⚠ هذا السكربت وثيقة تاريخية: يعمل فقط ضد شجرة PR #63 قبل الإصلاح"
          " (فرع feat/p0-safety-hardening) حيث كانت src/core/sensitive_guard.py موجودة.")
    print("  الشجرة الحالية تحتوي الإصلاحات — التحقق عليها بأوامر pytest في"
          " docs/alpha-session-2026-11-20/CHATGPT_REVIEW_LOG_2026-11-20.md")
    sys.exit(2)

import src.core.safe_mover as sm
from src.core.safe_mover import SafeMover
from src.core.sensitive_guard import classify_sensitivity
from src.core.file_handler import FileHandler

orig_claim = sm._claim_destination
orig_atomic_move = sm._atomic_move
orig_resolve = sm._resolve_collision

results = []


def record(cid, title, reproduced, evidence):
    results.append((cid, title, reproduced, evidence))
    print(f"\n{'='*72}\n[{cid}] {title}\n    النتيجة: {'REPRODUCED ✓' if reproduced else 'NOT REPRODUCED ✗'}")
    for line in evidence:
        print(f"    • {line}")


# ─── التجربة A: التصنيف بالاسم فقط ────────────────────────────────────────────
print("\n" + "#"*72 + "\n# التجربة A: التصنيف بالاسم/المسار فقط (sensitive_guard)\n" + "#"*72)
names = ["IMG_0001.jpg", "scan_0231.pdf", "xray_ortho_4411.png",
         "tokenizer.py", "patient_education_handbook.pdf", "Amrita_Notes.docx"]
cls = {}
for n in names:
    lvl = classify_sensitivity(n)
    cls[n] = lvl
    print(f"  {n:38s} -> {lvl}")
a_ok = (cls["IMG_0001.jpg"] == "NON_SENSITIVE" and cls["scan_0231.pdf"] == "NON_SENSITIVE"
        and cls["xray_ortho_4411.png"] == "NON_SENSITIVE")
a_fp = cls["tokenizer.py"] == "SECURITY_SECRETS" and cls["patient_education_handbook.pdf"] == "SENSITIVE_MEDICAL"
record("A1", "أشعة مرضى بأسماء عامة => NON_SENSITIVE (تصنيف بالاسم فقط)", a_ok,
       [f"{k} -> {cls[k]}" for k in names[:3]])
record("A2", "إنذارات كاذبة بالاسم (tokenizer / patient_education)", a_fp,
       [f"{k} -> {cls[k]}" for k in names[3:]])

# ─── التجربة P1: استبدال ملف الحجز بين الحجز والنقل ───────────────────────────
tmp = Path(tempfile.mkdtemp(prefix="p1_"))
src = tmp / "src.txt"; src.write_text("NEW-DATA")
dst = tmp / "dst.txt"
victim = tmp / "victim.txt"; victim.write_text("VICTIM-CONFIDENTIAL")


def attacking_claim(d):
    orig_claim(d)  # الحجز الطبيعي (ملف 0 بايت)
    # المهاجم يستبدل الحجز بملف حقيقي عبر os.replace داخل نافذة السباق
    os.replace(str(victim), str(d))


sm._claim_destination = attacking_claim
r = SafeMover().move(src, dst)
sm._claim_destination = orig_claim
p1_ok = r.success and dst.read_text() == "NEW-DATA"
record("P1", "استبدال الحجز داخل النافذة => SafeMover يستبدل البيانات بصمت",
       p1_ok, [f"success={r.success}", f"محتوى dst بعد النقل: '{dst.read_text()}'",
               f"بيانات المهاجم (VICTIM-CONFIDENTIAL) دُمرت: {dst.read_text() == 'NEW-DATA'}"])

# ─── التجربة P2: .bak متروكة من انهيار سابق تُمحى بصمت ────────────────────────
tmp = Path(tempfile.mkdtemp(prefix="p2_"))
stale = tmp / ".ifm_overwrite_d.txt.bak"; stale.write_text("STALE-BACKUP-ONLY-COPY")
src = tmp / "s.txt"; src.write_text("SRC")
dst = tmp / "d.txt"; dst.write_text("OLD")
r = SafeMover(overwrite=True).move(src, dst)
p2_ok = r.success and not stale.exists()
record("P2", "الـ.bak المتروكة من انهيار سابق تُمحى بصمت عند overwrite جديد",
       p2_ok, [f"success={r.success}", f"الـ.bak القديمة (النسخة الوحيدة) موجودة بعد العملية: {stale.exists()}"])

# ─── التجربة P3: استثناء غير OSError أثناء overwrite ─────────────────────────
tmp = Path(tempfile.mkdtemp(prefix="p3_"))
src = tmp / "s.txt"; src.write_text("SRC")
dst = tmp / "d.txt"; dst.write_text("OLD-DEST-CONTENT")


def raise_non_oserror(s, d):
    raise RuntimeError("boom — استثناء غير متوقع (ليس OSError)")


sm._atomic_move = raise_non_oserror
escaped = None
try:
    r = SafeMover(overwrite=True).move(src, dst)
except RuntimeError as e:
    escaped = str(e)  # الاستثناء انتشر خارج move() دون تنظيف — هذا بحد ذاته إثبات
sm._atomic_move = orig_atomic_move
baks = list(tmp.glob(".ifm_overwrite_*.bak"))
p3_ok = (escaped is not None and dst.exists() and dst.stat().st_size == 0 and baks
         and baks[0].read_text() == "OLD-DEST-CONTENT" and src.read_text() == "SRC")
record("P3", "استثناء غير OSError في overwrite => الاستثناء ينتشر، dst حجمه 0 والأصل مخفي في .bak",
       p3_ok, [f"الاستثناء انتشر خارج move() دون أي تنظيف: RuntimeError('{escaped}')",
               f"dst موجودة: {dst.exists()} بحجم: {dst.stat().st_size if dst.exists() else '—'} بايت (تبدو للنظام ملفاً فارغاً تالفاً)",
               f"المحتوى الأصلي مخفي في: {[b.name for b in baks]} (المستخدم يرى ملفاً فارغاً ولا يعلم أن بياناته في المخفي)",
               f"المصدر سليم: {src.read_text() == 'SRC'}"])

# ─── التجربة P4: KeyboardInterrupt يترك ملفاً فارغاً ──────────────────────────
tmp = Path(tempfile.mkdtemp(prefix="p4_"))
src = tmp / "s.txt"; src.write_text("SRC")
dst = tmp / "d.txt"


def interrupt_midway(s, d):
    d.write_bytes(b"")  # كتابة جزئية ثم مقاطعة
    raise KeyboardInterrupt()


sm._atomic_move = interrupt_midway
interrupted = False
try:
    SafeMover().move(src, dst)
except KeyboardInterrupt:
    interrupted = True
sm._atomic_move = orig_atomic_move
placeholder_remains = dst.exists() and dst.stat().st_size == 0
r2 = SafeMover().move(src, dst)
p4_ok = interrupted and placeholder_remains and r2.success and r2.final_path.endswith("d_1.txt")
record("P4", "KeyboardInterrupt => ملف فارغ يبقى، والنقل التالي يذهب إلى d_1.txt",
       p4_ok, [f"المقاطعة انتشرت خارج move() دون تنظيف: {interrupted}",
               f"الوجهة تبقى ملفاً فارغاً: {placeholder_remains}",
               f"النقل التالي ذهب إلى: {Path(r2.final_path).name} (renamed_due_to_collision={r2.renamed_due_to_collision})"])

# ─── التجربة P5: overwrite=True فوق مجلد ─────────────────────────────────────
tmp = Path(tempfile.mkdtemp(prefix="p5_"))
src = tmp / "s.txt"; src.write_text("FILE-CONTENT")
dstdir = tmp / "target"; dstdir.mkdir()
(dstdir / "inner.txt").write_text("DIR-INNER")
r = SafeMover(overwrite=True).move(src, dstdir)
baks = list(tmp.glob(".ifm_overwrite_*"))
p5_ok = (r.success and r.replaced_existing and (tmp / "target").is_file() and baks
         and baks[0].is_dir())
record("P5", "overwrite=True فوق مجلد => المجلد يُخفى في .bak ويُعلن النجاح",
       p5_ok, [f"success={r.success} replaced_existing={r.replaced_existing}",
               f"الوجهة الآن ملف: {(tmp/'target').is_file()} | المجلد اختفى من مكانه: {not dstdir.exists()}",
               f"المجلد المخفي: {[b.name + '/' for b in baks]}"])

# ─── التجربة U: التراجع يستبدل الملف الجديد بصمت ─────────────────────────────
tmp = Path(tempfile.mkdtemp(prefix="u_"))
base = tmp / "home"; (base / "downloads").mkdir(parents=True)
orig = base / "downloads" / "report.txt"; orig.write_text("ORIGINAL-REPORT")
fh = FileHandler()
r = fh.move_file(str(orig), "documents", str(base))
moved_to = Path(r["dest"])
newfile = base / "downloads" / "report.txt"; newfile.write_text("NEW-FILE-CREATED-AFTER-MOVE")
undo = fh.undo_last_action()
u_ok = (undo.get("success") and orig.exists()
        and orig.read_text() == "ORIGINAL-REPORT")
record("U", "التراجع (undo) يستبدل بصمت ملفاً جديداً أُنشئ بالاسم الأصلي",
       u_ok, [f"نقل عبر FileHandler: success={r.get('success')}",
              f"أنشأنا ملفاً جديداً بالاسم الأصلي بمحتوى NEW-FILE-CREATED-AFTER-MOVE",
              f"undo: {undo}",
              f"الملف الجديد دُمر واستُبدل بالقديم: {orig.read_text() == 'ORIGINAL-REPORT'}",
              "الآلية: shutil.move(dest, src) في undo_last_action يستبدل الوجهة صمتاً على POSIX"])

# ─── الخلاصة ─────────────────────────────────────────────────────────────────
print("\n" + "#"*72 + "\n# الخلاصة\n" + "#"*72)
for cid, title, ok, _ in results:
    print(f"  [{cid}] {'REPRODUCED' if ok else 'NOT REPRODUCED':14s} — {title}")
