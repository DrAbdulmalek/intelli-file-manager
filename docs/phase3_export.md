# المرحلة 3 — تجميع السطور RTL + بوابات الجودة (كما طُبّقت في هذا المستودع)

> المصدر: محادثة DeepSeek «المراحل 0-4» (2026-10). هذا الدليل هو النسخة
> المُواءمة مع بنية المستودع الفعلية (`src/services/` بدل `backend/app/services/`،
> وJSONL exporter الموجود بدل parquet المقترح).

## ما تفعله

1. تأخذ قصاصات الكلمات المُحرَّرة (محرر `/edit-ocr`)
2. **تجمّعها في سطور بترتيب RTL الصحيح** (`src/services/line_aggregator.py`)
3. تشغّل بوابات الجودة قبل التصدير (`src/services/dataset_validator.py`)
4. التصدير نفسه يتم عبر `HFExporter` الموجود (JSONL محلي + رفع صريح بتوكن)

## التركيز الحرج: RTL

**المشكلة الشائعة**: عند ترتيب كلمات عربية بـ `x_min` تصاعديًا
تحصل على نص **مقلوب**.

**الحل الصحيح**: RTL يقرأ من **اليمين لليسار**، لذا:
- رتّب بحسب `x_max` (الحافة اليمنى) **تنازليًا**
- ثم ادمج النصوص بمسافة واحدة
- `clean_text()` يحذف bidi marks (U+200E وما جاورها) ويوحّد whitespace و NFKC

## نقاط الوصول

| الموقع | الوظيفة |
|---|---|
| `src/services/line_aggregator.py` | `LineAggregator.aggregate()` / `aggregate_to_text()` / `aggregate_to_structured()` / `detect_direction()` / `clean_text()` |
| `src/services/dataset_validator.py` | `DatasetValidator.validate_all(snippets, source_image_path)` — 7 بوابات |
| `GET /api/snippets/lines?source_image=...&approved_only=true` | معاينة السطور المجمعة (يغذي `LineReviewPanel`) |
| `POST /api/snippets/validate?source_image=...` | تقرير بوابات الجودة قبل التصدير |
| `web/src/components/ocr/LineReviewPanel.tsx` | لوحة مراجعة السطور (مدمجة في SnippetPanel بزر «مراجعة السطور») |
| `scripts/export_training_data.py` | التصدير CLI (موجود مسبقًا — `--push --token` للرفع الصريح) |

## بوابات الجودة

| البوابة | الخطورة | ما تمنعه |
|---------|---------|----------|
| INVALID_BBOX / EMPTY_BBOX | error | bbox ناقص أو بلا مساحة |
| OUT_OF_BOUNDS | error | bbox خارج حدود الصورة الأصلية |
| EMPTY_TEXT | error | قصاصة بلا نص (عند `require_all_text`) |
| NUMERICAL_DRIFT | error | تغيير الأرقام بين `ocr_text` والنص المصحح (خطير طبيًا) |
| UNIT_DRIFT | error | تغيير وحدات طبية (mg → g) في قصاصات `category=medical` |
| LOW_CONFIDENCE | warning | ثقة منخفضة (مسموح مع توثيق) |
| NO_LETTERS | warning | نصوص بلا حروف (أرقام/رموز فقط) |

مبدأ الميثاق محفوظ: **الثقة 0.0 = غير معروفة** — لا تُعامل كرسوب تلقائي
ولا تُختلق درجة بديلة.

## صيغة التصدير (الموجودة فعليًا في المستودع)

`HFExporter` (في `src/services/hf_exporter.py`) يُنتج JSONL + صور تحت
`data/hf_export/` — عقد الصفوف موثق في ترويسة الملف. الرفع إلى HuggingFace
خطوة **صريحة** بتوكن (`POST /api/snippets/export-hf/push` أو
`scripts/export_training_data.py --push --token hf_xxx`) — لا دفع تلقائي أبدًا.

> ملاحظة تدقيق: حزمة المحادثة اقترحت مُصدِّر parquet + `upload_to_hf.py`
> منفصلًا؛ المستودع يملك عقد JSONL أبسط ومُختبَرًا مع سياسة "لا رفع بلا
> توكن صريح"، فاعتمدناه وأبقينا بوابات الجودة والتجميع كإضافة مستقلة
> تغذي نفس المسار.

## الاختبارات

```bash
pytest tests/unit/test_line_aggregator.py tests/unit/test_dataset_validator.py -v
```

## المستوى التالي

- تدريب TrOCR/كاشف كلمات على البيانات المُصدَّرة (ocr-core `[word-detect]`)
- تقييم CER/WER على مجموعة تحقق مستقلة (`tests/benchmarks/test_arabic_ocr.py`)
