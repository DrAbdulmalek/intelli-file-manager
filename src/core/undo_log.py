"""UndoLog — سجل التراجع عن الإجراءات

يخزّن UndoEntry لكل إجراء نُفّذ. يدعم:
  - append(entry): إضافة سجل جديد
  - rollback_last(): تراجع عن آخر إجراء (يرجع الملف/الوسوم لحالتها الأصلية)
  - rollback_all(): تراجع عن كل الإجراءات (بترتيب عكسي)
  - save() / load(): حفظ/تحميل JSON
  - list_entries(): عرض السجلات

ملاحظات:
  - rollback ينفّذ العملية العكسية فعليًا على القرص + يحذف الـ entry من السجل
  - rollback_last يُرجع UndoEntry الذي تراجع عنه (أو None لو السجل فارغ)
  - لا تراجع عن rollback (مقصود — rollback نهائي)

PR-05 من development-roadmap-v1.0 (IFM Phase A)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

from .rule_schemas import UndoEntry, ActionType

logger = logging.getLogger(__name__)


class UndoLog:
    """سجل التراجع عن الإجراءات

    الاستخدام:
        log = UndoLog("/data/.ifm_undo.json")
        # (تنفيذ إجراءات — تُضاف تلقائيًا عبر RuleEngine)
        log.save()
        # لاحقًا:
        log.load()
        log.rollback_last()
    """

    def __init__(self, path: Optional[Union[str, Path]] = None):
        """
        Args:
            path: مسار ملف JSON لحفظ السجل. إن None، السجل في الذاكرة فقط.
        """
        self.path = Path(path) if path else None
        self.entries: List[UndoEntry] = []
        self._safe_mover = None  # SafeMover إلزامي للتراجع (لا shutil مباشر)
        if self.path and self.path.exists():
            self.load()

    @property
    def safe_mover(self):
        """يُرجع SafeMover مشترك للتراجع (يُنشأ عند الطلب).

        move_sidecar=False لأن UndoLog يدير الـsidecar صراحة في منطقه القائم.
        """
        if self._safe_mover is None:
            from .safe_mover import SafeMover
            self._safe_mover = SafeMover(verify_checksum=True, move_sidecar=False)
        return self._safe_mover

    # ─── الواجهة الأساسية ───────────────────────────────────────────────

    def append(self, entry: UndoEntry) -> None:
        """يضيف سجل تراجع جديدًا (دون حفظ تلقائي على القرص)"""
        self.entries.append(entry)

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)

    def list_entries(self) -> List[UndoEntry]:
        """يُرجع نسخة من قائمة السجلات"""
        return list(self.entries)

    def clear(self) -> None:
        """يفرّغ السجل (دون حذف الملف)"""
        self.entries = []

    # ─── حفظ/تحميل ───────────────────────────────────────────────────────

    def save(self) -> None:
        """يحفظ السجل في ملف JSON"""
        if not self.path:
            return
        data = {
            "version": 1,
            "saved_at": datetime.now().isoformat(),
            "entries": [e.to_dict() for e in self.entries],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self) -> None:
        """يحمّل السجل من ملف JSON"""
        if not self.path or not self.path.exists():
            self.entries = []
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.entries = [UndoEntry.from_dict(e) for e in data.get("entries", [])]
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"فشل تحميل سجل التراجع {self.path}: {e}")
            self.entries = []

    # ─── التراجع ─────────────────────────────────────────────────────────

    def rollback_last(self) -> Optional[UndoEntry]:
        """يرجع آخر إجراء منفّذ (FIFO reversal)

        Returns:
            UndoEntry الذي تم التراجع عنه، أو None لو السجل فارغ
        """
        if not self.entries:
            return None
        entry = self.entries.pop()
        try:
            self._rollback_entry(entry)
        except Exception as e:
            logger.error(f"فشل التراجع عن {entry.action_type} على {entry.file_path}: {e}")
            entry.success = False
            entry.error_message = str(e)[:200]
        # حفظ تلقائي لو path محدد
        if self.path:
            self.save()
        return entry

    def rollback_all(self) -> List[UndoEntry]:
        """يرجع كل الإجراءات بترتيب عكسي (LIFO)

        Returns:
            قائمة UndoEntry التي تم التراجع عنها (بنفس ترتيب التراجع)
        """
        rolled_back: List[UndoEntry] = []
        while self.entries:
            entry = self.rollback_last()
            if entry is not None:
                rolled_back.append(entry)
        return rolled_back

    def rollback_n(self, n: int) -> List[UndoEntry]:
        """يرجع آخر n إجراءات"""
        rolled_back: List[UndoEntry] = []
        for _ in range(min(n, len(self.entries))):
            entry = self.rollback_last()
            if entry is not None:
                rolled_back.append(entry)
        return rolled_back

    # ─── التراجع عن دفعة كاملة (P1 — مُقوّى بعد المراجعة المستقلة) ──────

    def _preflight_rollback(self, entry: UndoEntry) -> None:
        """فحص تعارض مبدئي قبل أي تعديل على القرص (قراءة فقط — fail-closed).

        دلالات غياب الملف المستهدف (مراجعة مستقلة Finding 5):
          - MOVE: الوجهة مفقودة + المسار الأصلي موجود → مؤشر قوي على أن
            التراجع اكتمل سابقاً (إصدار قديم/جلسة سابقة): يُعلَّم السجل
            already_rolled_back ولا يُعاد عكسه ولا يُحذف.
          - MOVE: الوجهة والأصل مفقودان معاً → غياب غير مفسَّر → رفض يُجهض
            الدفعة كاملة.
          - COPY: النسخة مفقودة لا يمكن تمييزها عدلياً عن حذف خارجي
            (سجلاتنا الناجحة تُحذف فقط بعد عكس ناجح) → رفع خطأ يُجهض
            الدفعة كاملة دون أي تعديل.
          - أنواع sidecar (tag/untag/set_category/delete_flag): يجب وجود
            الملف الأساسي؛ حارس محتوى sidecar غير متاح (قيد موثق في
            AI_WORKLOG — لا checksum_after لهذه الأنواع).
        """
        at = entry.action_type
        if at in (ActionType.MOVE.value, ActionType.COPY.value):
            target = Path(entry.file_path_after) if entry.file_path_after else None
            if target is not None and target.exists():
                if entry.checksum_after:
                    from .safe_mover import compute_sha256
                    current = compute_sha256(target)
                    if current != entry.checksum_after:
                        raise RuntimeError(
                            "رفض التراجع: عُدّل الملف بعد العملية الأصلية — "
                            f"حماية من فقد تعديلات المستخدم: {target}"
                        )
                return
            if target is None:
                raise RuntimeError(
                    f"بيانات التراجع ناقصة ({at}): file_path_after مفقود"
                )
            orig = Path(entry.file_path)
            if at == ActionType.MOVE.value and orig.exists():
                entry._ifm_already_rolled_back = True
                return
            raise RuntimeError(
                f"الملف المستهدف مفقود بلا تفسير ({at}): {target} — "
                "أُجهض الدفعة (fail-closed)"
            )
        # أنواع sidecar: الملف الأساسي شرط
        if not Path(entry.file_path).exists():
            raise RuntimeError(
                f"الملف الأساسي مفقود لعملية sidecar ({at}): {entry.file_path}"
            )

    def _capture_post_state(self, entry: UndoEntry):
        """يلتقط حالة ما بعد الدفعة قبل عكس الإجراء (للتعويض عند الفشل)."""
        if entry.action_type == ActionType.SET_CATEGORY.value:
            from .rule_engine import _load_sidecar
            return _load_sidecar(entry.file_path).get("category", "")
        return None

    def _reapply_entry(self, entry: UndoEntry, post_state) -> None:
        """تعويض آمن: إعادة تطبيق الإجراء الأصلي (عكس التراجع المتوقف).

        SafeMover فقط للنقل/النسخ — لا shutil ولا unlink غير محمي؛
        النسخة المتعوَّضة تُسترجع من المصدر عبر safe_mover.copy.
        """
        at = entry.action_type
        if at == ActionType.MOVE.value:
            if not entry.file_path_after:
                raise RuntimeError("تعويض move ناقص البيانات")
            res = self.safe_mover.move(entry.file_path_after, entry.file_path)
            if not res.success:
                raise RuntimeError(f"فشل تعويض النقل: {res.error}")
        elif at == ActionType.COPY.value:
            if not entry.file_path_after:
                raise RuntimeError("تعويض copy ناقص البيانات")
            res = self.safe_mover.copy(entry.file_path, entry.file_path_after)
            if not res.success:
                raise RuntimeError(f"فشل تعويض النسخ: {res.error}")
        elif at == ActionType.TAG.value:
            from .rule_engine import _load_sidecar_tags, _save_sidecar_tags
            tags = _load_sidecar_tags(entry.file_path)
            for tag in entry.tags_added:
                if tag not in tags:
                    tags.append(tag)
            _save_sidecar_tags(entry.file_path, tags)
        elif at == ActionType.UNTAG.value:
            from .rule_engine import _load_sidecar_tags, _save_sidecar_tags
            tags = _load_sidecar_tags(entry.file_path)
            removed_set = set(entry.tags_removed)
            tags = [t for t in tags if t not in removed_set]
            _save_sidecar_tags(entry.file_path, tags)
        elif at == ActionType.SET_CATEGORY.value:
            from .rule_engine import _load_sidecar, _save_sidecar
            sc = _load_sidecar(entry.file_path)
            if post_state:
                sc["category"] = post_state
            else:
                sc.pop("category", None)
            _save_sidecar(entry.file_path, sc)
        elif at == ActionType.DELETE_FLAG.value:
            from .rule_engine import _load_sidecar_tags, _save_sidecar_tags
            tags = _load_sidecar_tags(entry.file_path)
            if "to_delete" not in tags:
                tags.append("to_delete")
            _save_sidecar_tags(entry.file_path, tags)
        else:
            raise RuntimeError(f"لا يمكن تعويض نوع إجراء: {at}")

    def rollback_batch(self, batch_id: str) -> dict:
        """يتراجع عن كل إجراءات دفعة واحدة (أحدث إجراء أولاً) — P1 مُقوّى.

        النموذج (مراجعة مستقلة Finding 4):
          1. فحص مبدئي (preflight) لكل الإجراءات قبل أي تعديل — أي تعارض
             أو غياب غير مفسَّر يُجهض الدفعة كاملة دون أي تغيير.
          2. عكس بترتيب عكسي عبر SafeMover فقط (لا shutil مباشر).
          3. عند فشل منتصف الدفعة: استرداد تعويضي (Transactional Recovery)
             — كل إجراء عُكس بالفعل يُعاد تطبيقه (بعكس عكسه) بالترتيب
             العكسي، فتُستعاد حالة ما قبل محاولة التراجع تماماً؛ ثم تبقى
             **كل** السجلات في السجل (لا حذف إطلاقاً عند الفشل) ويُرفع
             خطأ يوثّق نتيجة التعويض.
          4. السجلات تُحذف فقط بعد نجاح عكس **كل** الدفعة.
            عملية MOVE مكتملة مسبقاً (دليل: الأصل موجود والوجهة مفقودة)
            تُعلَّم already_rolled_back ويُحتفظ بسجلها ويُذكر في النتيجة.

        Returns:
            {"batch_id", "rolled_back": [types], "already_rolled_back": [types],
             "remaining": n}

        Raises:
            ValueError: batch_id فارغ أو لا توجد إجراءات له.
            RuntimeError: فشل الفحص المبدئي (لم يُعدّل أي ملف)، أو فشل
                في منتصف الدفعة (عُوّض ما عُكس ولم يُحذف أي سجل).
        """
        if not batch_id:
            raise ValueError("batch_id مطلوب")
        idx = [i for i, e in enumerate(self.entries) if e.batch_id == batch_id]
        if not idx:
            raise ValueError(f"لا توجد إجراءات للدفعة: {batch_id}")
        preflight_errors: List[str] = []
        for i in reversed(idx):
            try:
                self._preflight_rollback(self.entries[i])
            except Exception as exc:
                preflight_errors.append(f"[{self.entries[i].action_type}] {exc}")
        if preflight_errors:
            raise RuntimeError(
                "أُجهض التراجع عن الدفعة كاملة (فحص مبدئي فاشل — "
                "لم يُعدّل أي ملف): " + " | ".join(preflight_errors)
            )
        rolled_back: List[str] = []
        already: List[str] = []
        completed: List[tuple] = []  # (index, entry, post_state)
        failure: Optional[Exception] = None
        failureEntry: Optional[UndoEntry] = None
        for i in reversed(idx):
            entry = self.entries[i]
            if getattr(entry, "_ifm_already_rolled_back", False):
                already.append(entry.action_type)
                continue
            try:
                post_state = self._capture_post_state(entry)
                self._rollback_entry(entry)
            except Exception as e:
                failure = e
                failureEntry = entry
                break
            completed.append((i, entry, post_state))
            rolled_back.append(entry.action_type)
        if failure is not None or failureEntry is not None:
            comp_errors: List[str] = []
            for (ci, centry, cpost) in reversed(completed):
                try:
                    self._reapply_entry(centry, cpost)
                except Exception as e2:
                    comp_errors.append(f"[{centry.action_type}] {e2}")
            if self.path:
                self.save()
            msg = (
                f"فشل التراجع في منتصف الدفعة عن {failureEntry.action_type} "
                f"({failureEntry.file_path}): {failure}. "
                f"عُكس بالفعل {len(completed)} إجراء و"
                + ("عُوِّضت كلها بنجاح — "
                   if not comp_errors else "فشل تعويض بعضها — ")
                + "استُعيدت حالة ما قبل محاولة التراجع، ولم يُحذف أي سجل "
                "(استرداد تعويضي — Transactional Recovery)."
            )
            if comp_errors:
                msg += " أخطاء التعويض: " + " | ".join(comp_errors)
            raise RuntimeError(msg)
        # نجاح الدفعة كاملة الآن — حذف السجلات المتراجَع عنها فعلاً
        # (بترتيب فهرسي تنازلي لإبقاء الفهارس صالحة)
        for (ci, centry, cpost) in completed:
            self.entries.pop(ci)
        if self.path:
            self.save()
        return {
            "batch_id": batch_id,
            "rolled_back": rolled_back,
            "already_rolled_back": already,
            "remaining": len(self.entries),
        }

    # ─── منطق التراجع لكل نوع ────────────────────────────────────────────

    def _rollback_entry(self, entry: UndoEntry) -> None:
        """ينفّذ العملية العكسية لإجراء واحد"""
        if not entry.success:
            logger.warning(
                f"محاولة التراجع عن إجراء فاشل أصلاً ({entry.action_type} على "
                f"{entry.file_path}) — قد لا يكون آمنًا"
            )

        action_type = entry.action_type

        if action_type == ActionType.MOVE.value:
            self._rollback_move(entry)
        elif action_type == ActionType.COPY.value:
            self._rollback_copy(entry)
        elif action_type == ActionType.TAG.value:
            self._rollback_tag(entry)
        elif action_type == ActionType.UNTAG.value:
            self._rollback_untag(entry)
        elif action_type == ActionType.SET_CATEGORY.value:
            self._rollback_set_category(entry)
        elif action_type == ActionType.DELETE_FLAG.value:
            self._rollback_delete_flag(entry)
        else:
            raise ValueError(f"لا يمكن التراجع عن نوع إجراء: {action_type}")

    def _rollback_move(self, entry: UndoEntry) -> None:
        """عكس النقل: نقل الملف من الوجهة إلى المصدر (مع sidecar)"""
        if not entry.file_path_after:
            raise ValueError("file_path_after مفقود لعملية move")
        src = Path(entry.file_path_after)
        dst = Path(entry.file_path)

        if not src.exists():
            logger.warning(f"ملف الوجهة غير موجود للتراجع: {src}")
            return

        dst.parent.mkdir(parents=True, exist_ok=True)

        # نقل الملف عبر SafeMover (بوابة واحدة — التضارب يأخذ لاحقة، لا استبدال صامت)
        from .rule_engine import _sidecar_path
        src_sidecar = _sidecar_path(str(src))
        result = self.safe_mover.move(str(src), str(dst))
        if not result.success:
            raise RuntimeError(f"فشل التراجع عن النقل عبر SafeMover: {result.error}")
        if src_sidecar.exists():
            dst_sidecar = _sidecar_path(str(dst))
            # لا حذف صامت لشاغل الـsidecar (جولة DeepSeek 11 — كان
            # dst_sidecar.unlink() يمسح بيانات شاغل): عقد «اللاحقة لا
            # الاستبدال» يُطبق هنا أيضاً — SafeMover يتضارب باللاحقة
            result_sc = self.safe_mover.move(str(src_sidecar), str(dst_sidecar))
            if not result_sc.success:
                raise RuntimeError(f"فشل تراجع الـsidecar عبر SafeMover: {result_sc.error}")

    def _rollback_copy(self, entry: UndoEntry) -> None:
        """عكس النسخ: حذف النسخة المنشأة (مع sidecar)

        استثناء معتمد موثق (جولة DeepSeek 11): الحذف هنا مباشر (unlink)
        لأن النسخة أُنشئت بواسطة العملية نفسها المراد التراجع عنها لحظة
        قليلة مضت — لا بيانات سابقة على القرص تُمس بهذا الحذف. الحارس:
        إن عُدّل الملف بعد نسخه (checksum يخالف المسجل في القيد) يُرفض
        التراجع صراحةً حمايةً لتعديلات المستخدم اللاحقة.
        """
        if not entry.file_path_after:
            raise ValueError("file_path_after مفقود لعملية copy")
        copied = Path(entry.file_path_after)
        if not copied.exists():
            logger.warning(f"النسخة المنسوخة غير موجودة: {copied}")
        else:
            # حارس التعديل اللاحق: checksum_after يسجله _exec_copy عند النسخ
            recorded = getattr(entry, "checksum_after", None)
            if recorded and copied.is_file():
                from .safe_mover import compute_sha256
                try:
                    current = compute_sha256(copied)
                except OSError as e:
                    raise RuntimeError(f"تعذر التحقق من النسخة قبل التراجع: {e}")
                if current != recorded:
                    raise RuntimeError(
                        "رفض التراجع عن النسخ: عُدّل الملف بعد إنشائه — "
                        f"حماية من فقد تعديلات المستخدم: {copied}"
                    )
            copied.unlink()
        # حذف sidecar المنسوخ إن وُجد (جزء من النسخة المنشأة نفسها —
        # يخضع لنفس الاستثناء المعتمد أعلاه)
        from .rule_engine import _sidecar_path
        copied_sidecar = _sidecar_path(str(copied))
        if copied_sidecar.exists():
            copied_sidecar.unlink()

    def _rollback_tag(self, entry: UndoEntry) -> None:
        """عكس إضافة وسم: إزالة الوسم"""
        from .rule_engine import _load_sidecar_tags, _save_sidecar_tags
        for tag in entry.tags_added:
            tags = _load_sidecar_tags(entry.file_path)
            if tag in tags:
                tags = [t for t in tags if t != tag]
                _save_sidecar_tags(entry.file_path, tags)

    def _rollback_untag(self, entry: UndoEntry) -> None:
        """عكس إزالة وسم: إعادة الوسم"""
        from .rule_engine import _load_sidecar_tags, _save_sidecar_tags
        for tag in entry.tags_removed:
            tags = _load_sidecar_tags(entry.file_path)
            if tag not in tags:
                tags.append(tag)
                _save_sidecar_tags(entry.file_path, tags)

    def _rollback_set_category(self, entry: UndoEntry) -> None:
        """عكس ضبط التصنيف: استعادة التصنيف الأصلي

        لو old_category كان فارغًا (لم يكن للـ sidecar تصنيف سابق)،
        نحذف مفتاح category بالكامل بدلًا من ترك قيمة فارغة.
        """
        from .rule_engine import _load_sidecar, _save_sidecar
        sidecar = _load_sidecar(entry.file_path)
        if entry.old_category:
            sidecar["category"] = entry.old_category
        else:
            # إزالة المفتاح لو كان فارغًا أصلاً
            sidecar.pop("category", None)
        _save_sidecar(entry.file_path, sidecar)

    def _rollback_delete_flag(self, entry: UndoEntry) -> None:
        """عكس وسم الحذف: إزالة وسم to_delete"""
        from .rule_engine import _load_sidecar_tags, _save_sidecar_tags
        tags = _load_sidecar_tags(entry.file_path)
        if "to_delete" in tags:
            tags = [t for t in tags if t != "to_delete"]
            _save_sidecar_tags(entry.file_path, tags)


# ─── Utility: عرض السجل ─────────────────────────────────────────────────────

def format_undo_log_summary(log: UndoLog) -> str:
    """يُرجع ملخصًا نصيًا للسجل (للعرض في CLI)"""
    if not log.entries:
        return "سجل التراجع فارغ."
    lines = [f"سجل التراجع ({len(log.entries)} إجراء):"]
    for i, e in enumerate(log.entries, start=1):
        status = "✓" if e.success else "✗"
        lines.append(
            f"  {i}. [{status}] {e.action_type:14s} {e.file_name() if hasattr(e, 'file_name') else Path(e.file_path).name}  ({e.rule_name})"
        )
    return "\n".join(lines)
