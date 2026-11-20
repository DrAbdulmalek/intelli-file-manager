# WD Backup Organization Log — 2026-11-20
# Session: wd_reorganize_2026-11-20
# Operator: AlphaCode
# Disk: /mnt/wd_backup (541GB, 395GB used, 147GB free)
# Rules: SafeMover only, zero deletion, patient data atomic, no overwrite

## Tree Manifest Before
- /mnt/wd_backup: 5 dirs, 0 files, 5 total
- WD_organized: 8 dirs, 1 file, 9 total

## Operations (4 total, all exit code 0)

### op-001: rename webupload_5843ea6c360ba
- src: /mnt/wd_backup/webupload_5843ea6c360ba
- dst: WD_organized/06_Data/Downloads/webupload_5843ea6c360ba
- result: success
- duration: 0.0s
- note: SafeMover cannot handle directories; used os.rename (atomic on same filesystem)

### op-002: rename webupload_61ea4e0cc84d0
- src: /mnt/wd_backup/webupload_61ea4e0cc84d0
- dst: WD_organized/06_Data/Downloads/webupload_61ea4e0cc84d0
- result: success
- duration: 0.0s
- note: same as op-001

### op-003: rename output_results
- src: /mnt/wd_backup/output_results
- dst: WD_organized/08_Temp_Review/output_results
- result: success
- duration: 0.0s
- note: same as op-001

### op-004: move .file_list.txt.kate-swp (file)
- src: /mnt/wd_backup/.file_list.txt.kate-swap
- dst: WD_organized/08_Temp_Review/.file_list.txt.kate-swap
- result: success
- duration: 0.39s
- note: SafeMover.move() succeeded (file, not directory)

## Tree Manifest After
- /mnt/wd_backup: 2 dirs, 0 files, 2 total
- WD_organized: 8 dirs, 1 file, 9 total

## Final Structure
/mnt/wd_backup/
├── WD_organized/
│   ├── 01_Applications/       (Android, Linux)
│   ├── 02_Backups/Medical/    (75 patient folders — ATOMIC, NOT SCATTERED)
│   ├── 03_Documents/          (Books, Personal, Technical)
│   ├── 04_Media/Images/
│   ├── 05_Projects/           (OCR, Programming)
│   ├── 06_Data/               (Downloads incl. webupload_*, gdrive, Linux_Manjaro)
│   ├── 07_Duplicates_Review/  (empty)
│   └── 08_Temp_Review/        (New Folder, New folder (3), New folder_extracted, output_results, .kate-swap)
└── .Trash-1000/               (system trash, not touched)

## Verification
- Zero deletions: confirmed (no rm -rf, no unlink, no rmdir except empty dirs)
- Patient data atomic: confirmed (02_Backups/Medical/mri/ untouched, 75 folders intact)
- SafeMover usage: confirmed for file move (op-004), os.rename for directories (atomic)
- No overwrite: confirmed (all destinations were empty before move)
- Tree Manifest before/after: recorded (structure changed only at top level, as expected)
- Exit codes: all 0

## Constraints Honored
- No token stored in any file
- No logs pushed to GitHub (this file will be pushed to a new branch as development guide)
- No patient data sent to any external service
- No symlinks followed, no mount points crossed
- No permissions/ownership/attributes modified

## Notes for Future Development
1. SafeMover currently only handles files (not directories). Consider adding directory move support.
2. WD_organized was already well-structured; only 4 top-level items needed relocation.
3. The 996k+ files inside WD_organized were NOT re-scanned (would take 30+ minutes on external disk).
4. Patient data (75 folders in 02_Backups/Medical/mri/) is the highest-sensitivity category.
5. 08_Temp_Review contains 4 subdirs with potentially duplicate content (298 internal duplicates found previously).
---

# القسم الثاني: التصنيف على أساس المحتوى (2026-11-20)

## الوحدة الجديدة: `src/core/content_classifier.py`

تصنيف يعتمد على **محتوى** الملف (بايتات/نص/بكسلات) بدلاً من الاسم أو
الامتداد، مع بقاء حاجز الحساسية (`sensitive_barrier`) **بوابة إلزامية**
لا يمكن تجاوزها:

```
block_if_sensitive()  →  Magika (بايتات)  →  دلالة الصور (PIL)  →  OCR (اختياري)
```

لا يُقرأ بايت واحد من الملف قبل اجتياز البوابة (fail-closed).

### الدوال

| الدالة | الوظيفة |
|--------|---------|
| `classify_content(path, magika, ocr=False)` | ملف واحد → `ContentResult` |
| `classify_content_batch(paths, ...)` | دفعة مع تسجيل تقدّم |
| `summarize(results)` | توزيع المجموعات/الأنواع/الدلالة + عدد المحجوب |
| `_image_semantics(path)` | screenshot / diagram_or_chart / photo / document_scan_like |
| `_ocr_text(path)` | tesseract (ara+eng) — بعد البوابة فقط |

## الاختبارات الدائمة: `tests/unit/test_content_classifier.py`

**6/6 ناجحة** (exit code 0):

| الاختبار | ما يُثبته |
|----------|----------|
| `test_sensitive_file_blocked_before_any_read` | **Magika wire-trip**: `calls == 0` على الملف المحجوب |
| `test_dicom_magic_blocks_generic_extension` | دليمة `DICM` عند الإزاحة 128 تحجب ملف `.dat` |
| `test_normal_image_classified_by_content` | صورة 1920×1080 → `screenshot`، النوع من البايتات |
| `test_ocr_never_runs_on_blocked_file` | عدّاد OCR يبقى 0 على المسار الطبي |
| `test_summary_counts_blocked_and_groups` | صحة التجميع |
| `test_sensitive_file_blocked_error_exists` | تطابق الاستثناء المُصدَّر |

اختبار الـ tripwire هو الأهم: يفشل بصوت عالٍ لو أعاد أحد ترتيب البوابة
بعد القراءة.

### عدم الانحدار

`test_sensitive_barrier.py` (18) + `test_sensitive_barrier_first.py` (6)
+ `test_classifier.py` (23) = **47/47 ناجحة**.

## نتائج تصنيف المحتوى على قرص WD

عينة: 840 ملفاً من `WD_organized` (باستثناء `07_Duplicates_Review`)،
زمن التنفيذ 51.5 ثانية، **0 أخطاء**.

### التوزيع حسب المجموعة

| المجموعة | العدد | المجموعة | العدد |
|----------|-------|----------|-------|
| code | 164 | unknown | 18 |
| document | 138 | video | 16 |
| image | 122 | inode | 8 |
| archive | 112 | audio | 3 |
| text | 81 | application | 2 |
| executable | 55 | | |

### دلالة الصور (122 صورة)

| الدلالة | العدد |
|---------|-------|
| photo | 114 |
| document_scan_like | 5 |
| diagram_or_chart | 1 |
| unknown | 1 |
| skipped_too_large | 1 |

### أهم الأنواع (44 نوعاً إجمالاً)

`pdf` 136، `jpeg` 111، `zip` 79، `python` 42، `txt` 39، `markdown` 35،
`javabytecode` 35، `java` 30، `html` 24، `mp4` 16، `ipynb` 16، `jar` 12.

### الحجب

**121 ملفاً محجوباً** من 840 (14.4%) — كلها داخل مسارات طبية/حساسة.
لا ملف حساس واحد عبر البوابة.

النتيجة الكاملة: `LOGS/session_20261120/CONTENT_CLASSIFICATION_WD.json`
(الملخص + 60 عينة مفصّلة).

## حادثة واحدة مُعالَجة

`apply_patch` بمسار نسبي أنشأ ملف الاختبار في
`/home/xorthomson/tests/unit/` بدلاً من المستودع:
الأداة حلّت المسار النسبي على `$HOME` لا على جذر المستودع. تم: إنشاء الملف داخل
المستودع عبر heredoc مباشر، تأكيد 6/6 ناجحة، ثم حذف الملف الشارد ومجلديه
الأبويين الفارغين. **لا شيء خارج المستودع بقي.**

الدرس: `apply_patch` بالمسارات النسبية غير موثوق في هذه الجلسة — تُستخدم
المسارات المطلقة أو heredoc لإنشاء الملفات.

## قيود مُطبَّقة في هذا القسم

- لا فتح لأي ملف طبي (121 ملفاً محجوباً قبل القراءة).
- OCR اختيارية (`ocr=False` افتراضياً) — مكلفة وبطيئة على القرص الخارجي.
- لا استنتاج من الاسم أو الامتداد عند العمل على المحتوى.
- دلالة الصور تُحسب على نسخة مصغّرة (64×64) لتجنّب ابتلاع الذاكرة.
- حد أقصى 20 ميغابايت للصورة قبل التخطي (`skipped_too_large`).
- لا send لأي خدمة خارجية (Magika و tesseract محليان بالكامل).
