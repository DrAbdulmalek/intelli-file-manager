# محرر القصاصات — تقسيم/دمج/تراجع (كلمة كلمة بشكل كامل وصحيح)

> المصدر: محادثة DeepSeek (المرحلتان 2-3) + طلب المالك الصريح:
> «أريد أيضًا في قسم تحويل صفحة الخط اليدوي لقصاصات قابلة للتدريب أن
> يستطيع المستخدم تعديل المربعات ليختار كلمة كلمة بشكل كامل وصحيح».

## ما أُضيف في هذه الحزمة

| الملف | الوظيفة |
|---|---|
| `web/src/lib/snippet-ops.ts` | دوال نقية: `splitBBox` / `splitSnippet` / `mergeBBox` / `mergeSnippets` / `sortSnippetsRTL` / `suggestSplitPoint` |
| `web/src/hooks/useSnippetHistory.ts` | تراجع/إعادة (reducer بثلاث خانات، حد 50 خطوة) |
| `web/src/lib/__tests__/snippet-ops.test.ts` | اختبارات vitest (‏`npm run test` في `web/`) |
| `web/src/components/ocr/SnippetPanel.tsx` | دمج الأدوات: أزرار + اختصارات لوحة مفاتيح |
| `src/services/line_aggregator.py` | تجميع السطور RTL (انظر `docs/phase3_export.md`) |
| `src/services/dataset_validator.py` | بوابات الجودة السبع |
| `GET /api/snippets/lines` + `POST /api/snippets/validate` | نقاط API جديدة في `src/api/server.py` |

## الاستخدام (صفحة `/edit-ocr`)

1. حمّل صورة → تظهر قصاصاتها.
2. حدد مربعًا:
   - **S (تقسيم)**: يقسم المربع نصفين عند المنتصف — لعزل كلمة التصقت بأخرى.
     النصف الأيمن يُنشأ قصاصة جديدة على الخادم؛ النص يُمسح في النصفين
     (كلمة مقسومة تحتاج تحريرًا يدويًا) وتُصفَّر الثقة (لا تُختلق).
   - **M (دمج)**: يدمج المحدد مع أقرب جار في نفس السطر (تداخل رأسي ≥50%) —
     لكلمة انشطرت مربعين. النص يُدمج بترتيب RTL القرائي (الأيمن أولًا).
   - **Ctrl+Z / Ctrl+Y**: تراجع/إعادة **محلي** لعرض المربعات والنصوص.
3. الاختصارات تعمل عبر `e.code` (مستقلة عن تخطيط اللوحة عربية/إنجليزية)،
   ولا تلتقط حقول النص (textarea/input) حتى يبقى تراجع المتصفح النصي سليمًا.

### حدود التراجع (أمانة)

التقسيم والدمج **عمليتان خادميتان فوريتان** (PATCH/POST/DELETE عبر العقد
الموجود). التراجع المحلي يعيد العرض فقط؛ إن تراجعت عن تقسيم بعد حفظه،
أعد التحميل من الخادم أو استخدم العملية المعاكسة (دمج النصفين). هذا موثق
في tooltip الأزرار.

## قرارات التدقيق — حزمة المحادثة مقابل المستودع

المحادثة صممت المحرر على `react-konva` بهيكل `frontend/` + `backend/app/`.
المستودع يملك مسبقًا تنفيذًا بديلًا أنضج (canvas أصلي، عقد API مُختبَر،
سياسة ثقة ocr-core). القرار: **لا محرر مكرر** — تُستخلص القيمة الفريدة فقط.

| artifact المحادثة | المصير | السبب |
|---|---|---|
| `WordSnippetEditor.tsx` (react-konva) | ❌ لم يُضف (superseded) | `BBoxEditor.tsx` الموجود يغطي رسم/سحب/تحجيم/حرارة ثقة بلا تبعية konva |
| `EditorToolbar.tsx` / `SnippetSidebar.tsx` | ❌ لم تُضف (superseded) | مدمجتان في `SnippetPanel.tsx` الموجود |
| `konva-helpers.ts` | ❌ لم يُضف | تحويل الإحداثيات غير مطلوب — المحرر الحالي يرسم بإحداثيات الصورة مباشرة |
| `useSnippetApi.ts` | ❌ لم يُضف (superseded) | `SnippetPanel` يستدعي العقد الموجود مباشرة |
| `useSnippetHistory.ts` | ✅ أُضيف (مُكيَّف: أنواع من `snippet-ops`) | تراجع/إعادة كانا ناقصين فعلًا |
| `snippet-ops.ts` (split/merge/sortRTL) | ✅ أُضيف (مُكيَّف مع `BBox {x1..y2}` وحالات المستودع) | الميزة الجوهرية المطلوبة (كلمة كلمة) كانت ناقصة |
| `snippet-ops.test.ts` | ✅ أُضيف + وُسّع (splitBBox/mergeBBox/ثقة 0.0) | يعمل عبر vitest (أُضيف devDependency) |
| `LineReviewPanel.tsx` | ✅ أُضيف كما هو (مكوّن عرضي) + وُصل بـ `/api/snippets/lines` | مراجعة السطور قبل التصدير |
| `WordBBoxEditor.tsx` (مسودة msg مبكرة) | ❌ مسودة تجاوزتها المرحلة 2 ثم التنفيذ الموجود | — |
| `line_aggregator.py` / `dataset_validator.py` | ✅ أُضيفا في `src/services/` | جديدان كليًا على المستودع |
| `hf_exporter.py` (parquet) | ❌ (superseded) | `src/services/hf_exporter.py` الموجود (JSONL + رفع صريح بتوكن) أنضج وأُختبِر |
| `export_training_data.py` / `upload_to_hf.py` | ❌ (superseded) | `scripts/export_training_data.py` الموجود يغطي التصدير و`--push` |
| `backend/app/api/glossary.py` | ❌ (superseded) | `GET /api/glossary/suggest` موجود + `src/core/glossary_service.py` |
| `tests/services/test_hf_exporter.py` | ❌ (يخص المُصدِّر البديل) | tests الموجودة تغطي `HFExporter` الفعلي |
| `tests/e2e/word_editor.spec.ts` (Playwright) | ❌ لم يُضف | لا بنية Playwright في المستودع — إضافة إطار e2e قرار منفصل |
| `tests/services/test_line_aggregator.py` / `test_dataset_validator.py` | ✅ أُضيفا في `tests/unit/` (مسارات مستوردة مُصحَّحة + إصلاح fixture معكوسة في `test_two_lines_rtl`) | — |

## تشغيل الاختبارات

```bash
# Python (من جذر المستودع)
pytest tests/unit/test_line_aggregator.py tests/unit/test_dataset_validator.py -v

# Web (من web/)
npm install          # مرة واحدة — يضيف vitest
npm run test         # vitest run
```
