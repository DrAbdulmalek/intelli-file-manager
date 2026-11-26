# SCOPE_POLICY — intelli-file-manager / Archive Sort

> سياسة النطاق والسلامة لعمليات فرز الأرشيف على القرص الخارجي.
> هذه السياسة مُلزمة لكل دفعة تنفيذ. خرقها = STOP فوري.

## 1. قواعد الجذر والوجهة (Self-Nesting)

**Batch roots must not share their basename with any rule destination. If collision → exit 1, request rename of destination or split batch.**

تفصيل:
- قبل أي دفعة، شغّل `scripts/check_self_nesting.py <root>`.
- إن كان اسم الجذر (basename) يساوي اسم أي مجلد وجهة في القواعد → **exit 1** → أوقف.
- لا تُعِد تسمية الوجهة تلقائيًا. اطلب قرار المالك: إعادة تسمية الوجهة أو تقسيم الدفعة.
- السبب: الحادثة الموثّقة 2026-11-27 — `وسائط/` نُقلت داخل `وسائط/وسائط/` لأن اسم الجذر = اسم الوجهة، ثم rollback.

## 2. الدفعات الآمنة

- حجم الدفعة ≤ 33 ملفًا حتى إثبات السلامة على دفعتين متتاليتين ناجحتين.
- كل دفعة: dry-run → فحص self-nesting → موافقة المالك → execute → تحقق checksum → UndoLog.
- لا نقل/حذف/أرشفة دون موافقة صريحة على الدفعة.

## 3. المناطق المحظورة (لا تُمس)

- `fiinote_export/` — ملفات اعتماد (password exports). لا فتح، لا قراءة، لا نقل.
- `crops.db` — قبل إنهاء إجراء "D ثم C" والتحقق الرباعي.
- `وسائط/` — لا إعادة تشغيل قبل توقيع تشخيص P0.2.
- أي ملف `*password*`, `*passwd*`, `*secret*`, `*credential*`, `*.kdbx`, `*.key` — لا فتح محتوى.
- `~/secure/vault-*` — لا find على المحتوى.

## 4. الخصوصية

- التقارير تُرفع كـ SHA-256 + أعداد مجمّعة فقط.
- لا مسارات خام في المخرجات العامة.
- check_self_nesting.py / undo_diag.py لا يطبعان أي مسار.

## 5. قواعد Git

- لا تعديل على main. لا دمج PRs. لا force-push.
- كل commit برسالة واضحة + تحديث progress.md.
- الدفع على `feat/*` أو `fix/*` فقط.