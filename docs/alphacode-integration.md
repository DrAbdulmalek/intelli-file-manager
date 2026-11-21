# بروتوكول التكامل: AlphaCode ↔ IntelliFile (الحلقة المغلقة المحلية)

> الحالة: v1.0 — 2026-11-21. هذا المستند هو المرجع الرسمي للحلقة؛ السكربتات
> المذكورة هي التنفيذ الوحيد المعتمد لها، وأي عمل خارجها يعتبر خارج البروتوكول.

## 1) الفكرة في سطرين

AlphaCode (وكيل العمل المحلي) يستخدم IntelliFile (منظّم الملفات الذكي) للبحث
والتنظيم والتصنيف، وIntelliFile يستخدم ما ينتجه AlphaCode (تقارير العمل،
الملاحظات، اللوغات، وكل ما يصادفه) كمصدر evidence يتعلم منه — **دون تعديل أي
ملف من ملفات المشروع إلا بعد موافقة صريحة من المستخدم**، والرفع إلى GitHub
تلقائي على فرع مخصص لا يلوث main.

## 2) الحلقة المغلقة (الخمس خطوات)

```
┌────────────── AlphaCode (جهازك) ──────────────┐
│  جلسة عمل → outbox: تقرير/ملاحظات/لوغ/أي ملف   │
└──────────────┬────────────────────────────────┘
               │ ① alphacode_sync.py  (مسح أمني + رفع تلقائي)
               ▼
   GitHub: فرع alphacode/artifacts  ← (أرشيف كامل، بلا force push)
               │
               ▼ ② نسخة محلية إلى data/alphacode/inbox/
┌────────────── IntelliFile ────────────────────┐
│ ③ alphacode_ingest.py:                        │
│    تصنيف (SmartFileClassifier) + سجل بصمات    │
│    + evidence في FeedbackEngine (حالة pending)│
│    + لوحة summary.md                          │
│ ④ IntelliFile يعمل: بحث/تنظيم/تصنيف/MCP       │
│    ← AlphaCode يستدعي خادم MCP (اتجاه معاكس)  │
└──────────────┬────────────────────────────────┘
               │ ⑤ اقتراح تعديلات على المشروع (patches)
               ▼
   data/alphacode/proposals/<id>/{patch.diff,meta.json}
               │  alphacode_apply.py — بوابة الموافقة الإلزامية
               ▼
   [موافقة المستخدم (توقيع sha256)] → نسخة احتياطية → تطبيق → اختبارات
                                     ↘ فشل الاختبارات ⇒ rollback تلقائي
```

## 3) الأدوار والحدود

| الطرف | يملك | ممنوع |
|---|---|---|
| AlphaCode | الكتابة في `data/alphacode/outbox/` و`proposals/` فقط | تعديل أي ملف في شجرة المشروع مباشرة |
| IntelliFile | قراءة/تصنيف/فهرسة كل الـoutbox، وتشغيل أدوات MCP القرائية | كتابة قواعد تفضيل مفعّلة من artifacts بدون تأكيد مستخدم |
| المستخدم | الموافقة/الرفض على كل proposal، وتأكيد feedback | — |
| `alphacode_sync.py` | فرع `alphacode/artifacts` حصراً | أي فرع آخر، أي force push، أي ملف حساس |

## 4) التخطيط على القرص (كل شيء تحت `data/` المهملة من git)

```
data/alphacode/
├── outbox/          # AlphaCode يكتب هنا (تقارير، ملاحظات، لوغات، أي شيء يصادفه)
├── inbox/           # ما اجتاز المسح الأمني وينتظر الابتلاع
├── processed/       # أُرشِف باسم غير قابل للتغيير: <UTC>__<sha256-8>__<الاسم>
├── rejected/        # ما رفضه المسح الأمني + سبب الرفض (سجل نصي)
├── proposals/       # اقتراحات التعديل على المشروع (patches)
│   └── <id>/{patch.diff, meta.json}
├── approvals.jsonl  # قرارات المستخدم: {"id","sha256","decision","ts"}
├── backups/         # نسخ ما قبل التطبيق (للتراجع)
└── summary.md       # لوحة الحالة التي يولّدها ingest
```

## 5) الخطوات بالتفصيل

### ① الرفع التلقائي — `scripts/alphacode_sync.py`
- يمسح `outbox/` عبر حاجز الحساسية الحقيقي للتطبيق (`is_sensitive_path`) قبل
  أي شيء: أي ملف بنمط سر/بيانات طبية يذهب إلى `rejected/` مع السبب — لا يُرفع
  ولا يُنسخ أبداً.
- سقوف صارمة: 4MB للملف الواحد، 300 ملف للدفعة، إجمالي 64MB للدفعة.
- يرفع إلى فرع أيتام `alphacode/artifacts` (يُنشأ أول مرة) عبر worktree
  مؤقت — **تاريخ main يبقى نظيفاً**، ودفع عادي فقط (لا force؛ إذا سبقه أحد
  يدفع يجلب بـ`--ff-only` ويعيد الدفع).
- التوكن من البيئة `ALPHACODE_GH_TOKEN` أو `GITHUB_TOKEN` فقط — لا يُكتب في
  أي ملف ولا يظهر في وسائط git.
- بعد الرفع يسلّم نسخة إلى `inbox/` (الخطوة ②) ويترك `outbox/` فارغاً.

### ③ الابتلاع — `scripts/alphacode_ingest.py`
- يوقّع كل ملف باسم غير قابل للتغيير ويحفظ `manifest.jsonl` (sha256، الحجم،
  النوع).
- يصنّف عبر `SmartFileClassifier.classify_file` (مع تدهور لطيف لو غابت
  الاعتماديات الثقيلة).
- يسجل كل artifact كـ evidence في `FeedbackEngine.capture(...)` بحالة
  **pending** — لا يصبح قاعدة تفضيل فعّالة إلا بعد تأكيدك من واجهة التطبيق
  أو عبر `FeedbackEngine.confirm`.
- يولّد `summary.md`: آخر التقارير، العدّادات، الاقتراحات المفتوحة،
  المرفوضات الأمنية.

### ④ الاستخدام المعاكس — AlphaCode يستدعي IntelliFile
خادم MCP المحلي الموجود أصلاً `src/integrations/alphacode_mcp_server.py`
(stdio JSON-RPC) يعرض: جرداً بصرياً فقط + تحقق خطط dry-run + أدوات التفضيلات.
إعدادات العميل لدى AlphaCode:

```json
{
  "mcpServers": {
    "intellifile": {
      "command": "python",
      "args": ["-m", "src.integrations.alphacode_mcp_server"],
      "env": { "INTELLIFILE_AGENT_ROOTS": "/abs/path/to/AlphaCodeWorkspace" }
    }
  }
}
```
- `INTELLIFILE_AGENT_ROOTS` يحصر الجذور المسموح فحصها — لا شيء خارجها يُرى.
- الخادم بحكم تصميمه لا يعرض محتوى ملفات ولا أي أداة نقل/حذف/كتابة.

### ⑤ بوابة الموافقة — `scripts/alphacode_apply.py`
القاعدة الذهبية: **لا تُعدَّل شجرة المشروع إلا بموافقة موقّعة بالتجزئة.**
- AlphaCode يضع اقتراحه في `proposals/<id>/patch.diff` + `meta.json`
  (الملفات المستهدفة، المنطق، خطة الاختبار).
- الموافقة إما تفاعلية (`apply <id> --interactive` تعرض الـdiff وتسأل) أو
  بكتابة سطر في `approvals.jsonl`:
  `{"id":"...","sha256":"<تجزئة patch.diff كاملة>","decision":"approved","ts":"..."}`
  — تجزئة غير مطابقة ⇒ رفض قاطع (لا تلاعب بعد الموافقة).
- عند التنفيذ: `git apply --check` أولاً ⇒ نسخة احتياطية للمستهدفات في
  `backups/<id>/` ⇒ تطبيق ⇒ `pytest tests/unit -q` (أو `--full-tests`) ⇒
  فشل الاختبارات ⇒ تراجع تلقائي ويُعاد كل ملف بايت-بايت.
- التراجع اليدوي متاح دائماً: `apply --rollback <id>`.

## 6) قضبان الأمان المجمعة

1. حاجز الحساسية v2 (`src/core/sensitive_barrier.py`) هو الحَكَم في المسح —
   نفس الحاجز الذي يحمي التطبيق يحمي الرفع.
2. لا force push ولا إعادة كتابة تاريخ في أي فرع، وأيتام `alphacode/artifacts`
   لا تُدمج في main أبداً.
3. كل كتابة في `proposals/` أو `approvals.jsonl` قابلة للإعادة والتدقيق
   (append-only، بطوابع زمن UTC).
4. feedback من artifacts يبدأ pending دائماً — التعلم الفعّال يتطلب تأكيدك.
5. التوكنات في البيئة فقط، ويُنصح بتوكن fine-grained بصلاحية Contents:write
   على هذا المستودع وحده وبانتهاء صلاحية قصير.

## 7) تشغيل سريع

```bash
# من AlphaCode بعد كل جلسة (يمكن وضعه في hooks نهاية الجلسة):
python scripts/alphacode_sync.py            # مسح + رفع + تسليم للـinbox

# على جهاز IntelliFile (أو نفس الجهاز):
python scripts/alphacode_ingest.py          # تصنيف + evidence + summary

# عندما يضع AlphaCode اقتراح تعديل:
python scripts/alphacode_apply.py list
python scripts/alphacode_apply.py apply <id> --interactive   # أو موافقة موقعة
python scripts/alphacode_apply.py rollback <id>              # عند الحاجة
```
