# -*- coding: utf-8 -*-
"""حقن فشل نظام ملفات **حتمي ومستقل عن هوية المستخدم (uid)**.

لماذا هذه الوحدة؟
    اختبارات «فشل التراجع لا يُعرض نجاحاً» (F19 متابعة) كانت تحقن الفشل
    بجعل الدليل الأب قراءة-فقط::

        os.chmod(ro_parent, 0o555)   # ← غير حتمي

    هذا الحقن يسقط بصمت تحت المستخدم الجذر (uid 0): في POSIX الجذر يتجاوز
    بتات الصلاحيات (CAP_DAC_OVERRIDE)، فتُكتب الوجهة داخل الدليل
    «المقفول» وينجح التراجع فعلاً. النتيجة: الاختبار يفشل رغم أن المنتج
    سليم — أو أخطر: يُعاد ضبطه على ``success=True`` فيفقد الاختبار
    قيمته كلياً. الحالة نفسها تظهر في أي حاوية Docker/devcontainer
    تعمل بالجذر، وفي بعض عدّادات CI.

البديل الحتمي
    ``blocked_parent()`` ينشئ **ملفاً عادياً** في مسار يُستخدم كأبٍ للوجهة.
    أي محاولة نقل إلى ``<ذلك المسار>/target.txt`` تفشل عند
    ``dst.parent.mkdir(parents=True, exist_ok=True)`` بـ``FileExistsError``
    (لأن ``exist_ok`` يتسامح مع دليل موجود فقط، لا مع ملف عادي).

    هذا الفشل:
      - مستقل عن uid والصلاحيات ونظام الملفات (لا يعتمد على بتات mode).
      - يقع **قبل** أي تعديل على القرص: المصدر يبقى سليماً ولا فقد بيانات.
      - حقيقي على مستوى نظام التشغيل، لا mock ولا monkeypatch.

القاعدة
    لا تستخدم ``chmod`` لحقن فشل في اختبار يجب أن يكون حتمياً. استخدم
    ``blocked_parent()``. وإن كان الاختبار يقيس *الصلاحيات نفسها* (مثل
    «دليل غير قابل للقراءة يجعل اللقطة ناقصة») فتخطَّ صراحةً تحت الجذر
    عبر ``is_root()`` — لا تفترض أن البتات تمنع الجذر.
"""
from __future__ import annotations

import os
from pathlib import Path

__all__ = ["blocked_parent", "is_root"]


def is_root() -> bool:
    """هل العملية الحالية بالجذر (uid 0)؟ الجذر يتجاوز بتات الصلاحيات."""
    return hasattr(os, "geteuid") and os.geteuid() == 0


def blocked_parent(base: Path | str, name: str = "blocked_parent") -> Path:
    """ينشئ ملفاً عادياً يمنع أي نقل إلى داخله — لأي uid بما فيه الجذر.

    Args:
        base: دليل الاختبار المؤقت (``tmp_path``).
        name: اسم المسار الذي سيُستخدم كأبٍ للوجهة.

    Returns:
        المسار المُنشأ (ملف عادي). استخدمه هكذا::

            parent = blocked_parent(tmp_path)
            entry = UndoEntry(action_type="move",
                              file_path=str(parent / "target.txt"),
                              file_path_after=str(existing_file),
                              success=True)

    Raises:
        FileExistsError: لو كان المسار موجوداً مسبقاً (لا نستبدل شيئاً).
    """
    path = Path(base) / name
    # exclusive creation: لا حذف ولا استبدال لأي ملف قائم
    with open(path, "x", encoding="utf-8") as fh:
        fh.write("not a directory — deterministic move-failure injection\n")
    return path
