# الحاجز الموحّد للبيانات الحساسة (Sensitive Barrier) — مرجع المطوّر

> آخر تحديث: 2026-11-21 — جولة التصلّد الشامل (فرع
> `security/comprehensive-sensitive-barrier-hardening`).

هذا المستند هو العقد الرسمي لوحدة `src/core/sensitive_barrier.py` وكيفية
استخدامها في **كل** نقطة دخول بيانات في IntelliFile: AI وOCR وRAG والفهرسة
والتصنيف والمعاينة عبر الـAPI.

---

## 1. الهدف

ألا يصل محتوى أي ملف يُصنَّف "حساساً" إلى أي قارئ (قراءة نص، EXIF/magic
bytes، OCR، تضمينات، فهرسة، إرسال خارجي) دون تصريح صريح — على مستوى القارئات
نفسها، لا على مستوى واجهة المستخدم فقط.

---

## 2. مستويات الكشف الثلاثة — يجب ألا تُخلط

| المستوى | ماذا يفعل | هل يفتح الملف؟ | موضع الاستخدام |
|---|---|---|---|
| **Path/name-based** | يطابق الامتداد واسم الملف وأجزاء المسار (word-boundary) | **لا** — stat/lstat فقط | كل استدعاء حاجز (الطبقة الأولى دائماً) |
| **Header-based** | يقرأ **4 بايتات فقط** عند الإزاحة 128 للتحقق من دليمة `DICM` | نعم — 4 بايتات عبر `O_NOFOLLOW` | داخل `is_sensitive_path()` نفسه (كشف DICOM خلف امتداد مضلل مثل `.pdf`) |
| **Full content inspection** | قراءة كاملة للمحتوى | نعم — كامل | **ممنوع على الملفات الحساسة نهائياً** (فهرسة/تصنيف/OCR/إرسال) |

**صدق مهم:** الحاجز *لا* "لا يقرأ المحتوى" — الطبقة الثانية تقرأ 4 بايتات.
أي توثيق أو سجل يفترض "لا قراءة إطلاقاً" يجب أن يستشير هذا الجدول. اختبارات
`tests/unit/test_reader_read_prevention.py` تقيس هذا حرفياً: ميزانية قراءة
قصوى 4 بايتات للهدف عبر `os.open`، وصفر قراءات عبر `builtins.open` /
`io.open` / `Path.open`.

---

## 3. القواعد الإلزامية (لا يمكن تعطيلها)

### 3.1 ملفات الأسرار والاعتماديات
- **بالاسم الصارم:** `.env` (وأي اسم ينتهي بـ `.env`)، `.env.local`،
  `.env.production`، `.netrc`، `.htpasswd`، `.git-credentials`، `.npmrc`،
  `.pypirc`، `credentials.json` / `credentials.yaml` / `credentials.yml`،
  `secrets.json` / `secrets.yaml` / `secrets.yml`، مفاتيح SSH الخاصة
  (`id_rsa`، `id_dsa`، `id_ecdsa`، `id_ed25519`، `id_ed448`، `identity`).
- **بالامتداد:** `.pem`، `.p12`، `.pfx`، `.p7b`، `.p7c`، `.key`، `.ppk`،
  `.jks`، `.keystore`، `.kdb`، `.kdbx`، `.gpg`، `.asc`، `.crt`، `.cer`،
  `.der`، `.crl`، `.pub` (المفاتيح العامة تُحظر احترازياً — العائلة كلها).

### 3.2 المؤشرات الطبية (مسار أو اسم ملف)
- **مجلدات:** `mri`، `dicom`، `medical`، `patient`، `patients`،
  `medical_records`، `hospital_records`، `clinical`، `radiology`،
  `prescriptions`، `laboratory`، `lab_results`، `clinics`، `clinic`،
  `hospital`، `hospitals`، والأعرب المقابلة (مرضى، سجل طبي، أشعة، وصفة،
  تحاليل، مختبر، مستشفى، عيادة...).
- **أسماء ملفات:** `scan`، `xray`، `ultrasound`، `chest`، `brain`، `spine`،
  `prescription`، `lab_result`، ومؤشرات اعتماديات (`credentials`، `secret`،
  `password`، `private_key`، `api_key`...).
- المطابقة **كلمة كاملة** (word-boundary على `_` و`-` و`.`) — لا substring:
  `Amrita` ليست `mri`، و`secretary` ليست `secret`.

### 3.3 DICOM المستتر
امتداد تصوير طبي مؤكد (`.dcm`، `.nii`، `.mha`...) → حساس دائماً؛ ودليمة
`DICM` عند الإزاحة 128 → حساس **حتى لو كان الامتداد `.pdf` أو `.jpg` أو
غير معروف**.

### 3.4 skip_dirs لا يعطّل شيئاً
المعامل `skip_dirs` في `is_sensitive_path()` **مُتجاهَل** — كان سابقاً
يستطيع إبطال كشف `secrets`/`credentials` (ثغرة مُثبتة في `FileInventory`).
`skip_dirs` مشروع فقط في **تقليم المسح** (`path_policy.iter_files`) قبل
الوصول إلى القارئات. الاستثناءان التنظيميان (`secrets`/`credentials` في
جرد `FileInventory`) أُزيلا ليظهر الملف السري في الجرد كسجل محجوب
(بلا hash ولا محتوى) بدل اختفاء صامت.

---

## 4. سياسة الروابط الرمزية وحدود TOCTOU

ما يفعله الحاجز:
1. **التصنيف:** أي مسار يمر عبر رابط رمزي (نهائي أو وسيط) يُصنّف على
   `realpath` الهدف أيضاً — حساس إن حسّ أي جانب (بلا قراءة محتوى عدا فحص
   header على الهدف).
2. **`open_checked(path, mode)`:** يفحص الحاجز، ثم يفتح بـ `O_NOFOLLOW`
   (POSIX)، ثم يتحقق عبر `fstat` أن المفتوح ملف عادي. رفض الرابط الرمزي
   (حتى لو كان هدفه عادياً) يتطلب `require_real_file=True` (الافتراضي).
3. **`verify_open_identity(fd, st)`:** مقارنة `st_dev`/`st_ino` بعد الفتح —
   ضد بدل ملف عادي بآخر عادي بنفس الاسم.

حدود الحماية المتبقية (**موثّقة، لا تُخفى**):
- `O_NOFOLLOW` يمنع بدل المكوّن **الأخير** فقط برابط رمزي.
- بدل مجلد **أب** (rename) بين الفحص والفتح خارج نطاق الوحدة؛ المسح
  التكراري يمر عبر `iter_files` الذي يرفض الجذور ذات مكوّنات symlink
  ولا يتبع الروابط، لكن السباق الكامل على مستوى الشجرة يحتاج حجز inode
  (فتح ثم جولة المسح على وصف الملف) — غير منفذ حالياً.
- نافذة "بدّل ملف عادي بملف عادي بعد الفحص وقبل القراءة" تُغلق جزئياً
  بـ`verify_open_identity` — القرّاء الحرِجون المستقبليون ينبغي أن يستخدموه.

---

## 5. كيف تضيف قارئ ملفات جديد **دون** تجاوز الحاجز

```python
from .sensitive_barrier import block_if_sensitive, open_checked

def my_reader(filepath: str) -> str:
    # (أ) إن كنت تقرأ بنفسك عبر open():
    block_if_sensitive(filepath, operation="وصف العملية")
    with open(filepath, "rb") as f:          # القراءة بعد الحاجز
        ...

    # (ب) الأفضل: استخدم open_checked — حاجز + O_NOFOLLOW + فحص ملف عادي
    with open_checked(filepath, "rb", operation="وصف العملية") as f:
        ...
```

قواعد إلزامية للقارئ الجديد:
1. الحاجز **قبل** أول `open()` في المسار — لا بعده، ولا في طبقة أعلى فقط.
2. لا تمرّر مجلداً كاملاً إلى أي محرك (RAG/فهرسة) — وسّعه عبر
   `path_policy.iter_files` وافحص **كل ملف سيُقرأ** على حدة.
3. لا تجعل أي إعداد مستخدم (skip_dirs أو غيره) يعلو على الحاجز.
4. أضف اختباراً في `tests/unit/test_reader_read_prevention.py` يستخدم
   `ReadRecorder` ويُثبت عدم فتح ملف حساس اصطناعي.
5. حدّث جدول القارئات في تقرير المراجعة الأمنية.

---

## 6. جدول القارئات المراجَعة (الحالة بعد جولة التصلّد)

| القارئ | الملف | حاجز قبل القراءة | حماية تكرارية | الملاحظة |
|---|---|---|---|---|
| `AIEngine.summarize_file` | `src/core/ai_engine.py` | نعم (استثناء) | — | الحاجز قبل تهيئة العميل |
| `AIEngine.extract_keywords` | `src/core/ai_engine.py` | نعم (استثناء) | — | كذلك |
| `AIEngine.suggest_category` | `src/core/ai_engine.py` | لا يقرأ محتوى | — | اسم الملف فقط |
| `FileCopilot.summarize_file` | `src/core/file_copilot.py` | نعم | — | رسالة حظر في النتيجة |
| `FileCopilot.index_files` | `src/core/file_copilot.py` | نعم لكل ملف | نعم — توسعة المجلدات عبر iter_files + فحص كل ملف قبل RAG | لا يمر مجلد خام إلى RAG |
| `SmartTagger._extract_content` | `src/core/smart_tagger.py` | نعم (نص فارغ) | — | عقد الدالة محفوظ |
| `SmartTagger.get_tags/auto_tag` | `src/core/smart_tagger.py` | نعم | — | عبر `_extract_content` |
| `MultimodalProcessor.process_image/audio/video` | `src/core/multimodal_processor.py` | نعم (استثناء) | — | يشمل EXIF وOCR وAI |
| `MultimodalProcessor.extract_text_from_pdf/docx/xlsx/pptx` | `src/core/multimodal_processor.py` | نعم (استثناء) | — | قبل توكيل الاستخراج |
| `EnhancedMultimodalProcessor.process_image` | `src/core/enhanced_multimodal.py` | نعم (داخل ocr_service) | — | + process_audio/video/document أُضيفت (كانت أسلاك مكسورة) |
| `ocr_service.ocr_image` / `enhance_image` | `src/core/ocr_service.py` | نعم (نتيجة محجوبة) | — | + `external_send_allowed` |
| `metadata_extractor.extract_image_metadata` | `src/core/metadata_extractor.py` | نعم (`sensitive_blocked`) | — | EXIF يُعامل حساساً |
| `metadata_extractor.extract_av_metadata` | `src/core/metadata_extractor.py` | نعم | — | ffprobe لا يرى حساساً |
| `metadata_extractor.detect_content_type` | `src/core/metadata_extractor.py` | نعم — امتداد فقط | — | لا magic bytes للحساس |
| `SmartFileClassifier.classify_file` | `src/core/classifier.py` | نعم — بلا Magika | نعم عبر batch_classify | content_type=sensitive_blocked |
| `SmartFileClassifier.batch_classify` | `src/core/classifier.py` | نعم لكل ملف | نعم — iter_files | لا symlinks |
| `FileInventory.scan` | `src/core/file_inventory.py` | نعم — لا SHA ولا magic ولا EXIF | نعم — iter_files + رفض symlinks | الجرد بالعناوين فقط للحساس |
| `HybridSearchEngine._extract_text/index_files` | `src/core/hybrid_search.py` | نعم (نص فارغ) | نعم — iter_files | عقد PR #63 محفوظ |
| `RAGEngine._extract_text/ingest_file` | `src/core/rag_engine.py` | نعم | — | كذلك |
| `SemanticSearchEngine._extract_text` | `src/core/semantic_search.py` | نعم | نعم — iter_files | كذلك |
| `/api/file/serve` | `src/api/server.py` | نعم (403) | — | + مصادقة |
| `/api/process/*` | `src/api/server.py` | نعم (403) | — | + مصادقة |
| `HFExporter._crop_and_save` | `src/services/hf_exporter.py` | نعم | — | صورة حساسة لا تُصدَّر |
| `tree_manifest.snapshot/verify` | `src/core/tree_manifest.py` | أداة سلامة قراءة-فقط | رفض جذر symlink | لا يقرأ إلا بغرض hash التحقق |
| `SafeMover` / `FileHandler` / `watcher` / `voice_controller` | — | لا يقرأون محتوى (نقل/أحداث/صوت المستخدم) | نعم — iter_files | خارج نطاق المحتوى |

أي قارئ جديد يُضاف هنا وإلا فهو غير مُدقَّق.

---

## 7. الاختبارات

| ملف الاختبار | ماذا يُثبت |
|---|---|
| `tests/unit/test_sensitive_barrier.py` | العقد الأساسي القديم (مُحافَظ عليه) |
| `tests/unit/test_sensitive_barrier_v2.py` | الأسرار، المؤشرات الجديدة، symlink، O_NOFOLLOW، skip_dirs عاجز |
| `tests/unit/test_reader_read_prevention.py` | **عدم الفتح الفعلي** لكل قارئ (قياس البايتات) + التكراري + سيناريوهات الخلط |
| `tests/unit/test_sensitive_barrier_first.py` | عدم فتح الحساس أثناء الفهرسة (SHA/magic/metadata) |
| `tests/unit/test_hybrid_search_barrier.py` | بوابة الفهرسة الهجينة |
| `tests/unit/test_f1_f8_inversion.py` | الانعكاسات A1/A2/P1–P5 |
| `tests/integration/test_api_auth_ws.py` | مصادقة API/WS، توكن HF، حاجز file/serve، sandbox |
| `tests/unit/test_tree_manifest.py` + `test_reader_read_prevention.py` (قسم manifest) | symlink root/target، التبدل أثناء الهاش |
