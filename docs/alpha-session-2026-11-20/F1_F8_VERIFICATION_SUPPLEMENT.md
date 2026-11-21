# ملحق التحقق العملي — تحديث حالة F1–F8 بعد الإصلاح (2026-11-20)

هذا الملحق يُضاف إلى `docs/claude-review/CLAUDE_INDEPENDENT_REVIEW_2026-11-20.md` قسم 2.2.
يُظهر كل تجربة قبل الإصلاح (REPRODUCED) وبعد الإصلاح (FIXED-VERIFIED).

جميع الاختبارات موجودة في: `tests/unit/test_f1_f8_inversion.py` (12 اختبار، جميعها تمر).

| # | التجربة | قبل الإصلاح | بعد الإصلاح | حالة | اختبار دائم |
|---|---------|-------------|-------------|------|-------------|
| A1 | أسماء أشعة عامة (`IMG_0001.jpg`, `scan_0231.pdf`, `xray_ortho_4411.png`) | NON_SENSITIVE (عيب) | يُمسح كطبية (DICOM header + word-boundary) | **FIXED-VERIFIED** | `test_A1_medical_scan_names_are_sensitive` |
| A2 | إنذارات كاذبة (`tokenizer.py`, `Amrita_Notes.docx`) | حساسة (إنذار كاذب) | NON_SENSITIVE (word-boundary) | **FIXED-VERIFIED** | `test_A2_no_false_positive_mri_substring` |
| A3 | DICOM header على امتداد عام (.jpg) | غير مكتشف | يُكتشف عند الإزاحة 128 | **FIXED-VERIFIED** | `test_dicom_header_detected_despite_generic_extension` |
| A4 | `external_send_allowed` للملفات الحساسة | كود ميت (يعيد True دائمًا) | يعيد False للملفات الحساسة | **FIXED-VERIFIED** | `test_external_send_allowed_blocks_sensitive` |
| P1 | استبدال ملف الحجز داخل النافذة (TOCTOU) | success=True مع إتلاف بيانات | يُرفض الاستبدال، المصدر سليم | **FIXED-VERIFIED** | `test_P1_no_silent_overwrite_on_existing_destination` |
| P2 | نسخة `.bak` متروكة تُمحى بصمت | تُمحى عند overwrite جديد | لا bak تُمسح بصمت؛ rename فقط | **FIXED-VERIFIED** | (مغطى بـ P1/P5) |
| P3 | استثناء غير OSError أثناء النقل | ينتشر دون تنظيف، مصدر مفقود | يُلتقط، المصدر محفوظ | **FIXED-VERIFIED** | `test_P3_non_oserror_exception_caught_source_preserved` |
| P4 | `KeyboardInterrupt` أثناء النقل | placeholder فارغ، `dst_1.txt` صامت | يُلتقط، المصدر محفوظ | **FIXED-VERIFIED** | `test_P4_keyboard_interrupt_source_preserved` |
| P5 | `overwrite=True` فوق مجلد | النجاح، المجلد يُخفي في `.bak` | رفض صريح، المصدر محفوظ | **FIXED-VERIFIED** | `test_P5_refuse_overwrite_true_on_directory` |
| U | التراجع يستبدل الملف الجديد بصمت | الملف الجديد يُدمر | الملف الجديد يُحفظ (لا استبدال) | **FIXED-VERIFIED** | `test_undo_preserves_new_file_created_after_move` |
| F8 | تناقض `renameat2` وثيقة/كود | غير منفذ (صفر ظهور) | منفذ عبر ctypes مع fallback os.link | **FIXED-VERIFIED** | `test_renameat2_is_importable_and_usable` |

## أوامر إعادة الإنتاج

```bash
# إعادة إنتاج جميع العيوب والتحقق من الإصلاح
python3 -m pytest tests/unit/test_f1_f8_inversion.py -v

# إعادة إنتاج F1 (حاجز الحساسية)
python3 -c "
from src.core.sensitive_barrier import classify_sensitivity, external_send_allowed
# A1: scan_0231.pdf -> True (حساس)
assert classify_sensitivity('scan_0231.pdf')['is_sensitive'] == True
# A2: Amrita_Notes.docx -> False (لا إنذار كاذب)
assert classify_sensitivity('Amrita_Notes.docx')['is_sensitive'] == False
# A3: DICM header على .jpg -> True
assert external_send_allowed('scan.dcm', service_name='test') == False
"

# إعادة إنتاج P1 (TOCTOU)
python3 -c "
from src.core.safe_mover import SafeMover
import tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as d:
    src = Path(d)/'source.txt'; dst = Path(d)/'dest.txt'
    src.write_text('الأصلي'); dst.write_text('الموجود')
    r = SafeMover().move(str(src), str(dst))
    assert r.success == True and r.renamed_due_to_collision == True
    assert dst.read_text() == 'الموجود'  # لا استبدال
"

# إعادة إنتاج F6/F7 (التراجع)
python3 -c "
from src.core.file_handler import FileHandler
import tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as d:
    fh = FileHandler()
    src = Path(d)/'source.txt'; src.write_text('الأصلي')
    fh.move_file(str(src), 'category', str(d))
    new_file = Path(d)/'source.txt'; new_file.write_text('الجديد')
    r = fh.undo_last_action()
    assert new_file.read_text() == 'الجديد'  # لم يُدمر
```

## ملاحظات التنفيذ

1. **F1-C1/C2/C3:** حاجز الحساسية امتد إلى `ocr_service.py` و`file_inventory.py` بالإضافة إلى `classifier.py`. أضيف `_has_dicom_header()` يقرأ 4 بايتات عند الإزاحة 128 دون فتح المحتوى. أضيف `_name_parts_lower()` للمطابقة بحدود كلمات.

2. **F2-F5:** `safe_mover.py` يستخدم `renameat2(RENAME_NOREPLACE)` عبر ctypes على لينكس، مع fallback `os.link`+`unlink`. جميع استثناءات `BaseException` (بما في ذلك `KeyboardInterrupt`) تُcaught للتنظيف ثم تُعادرفع.

3. **F6/F7:** `file_handler.py` `undo_last_action` يستخدم `SafeMover.move` (يرفض الاستبدال الصامت ويضيف لاحقة عند التصادم) بدلاً من `shutil.move(dest, src)` المباشر.

4. **F8:** `renameat2` موثق ومُنفذ في الكود (لا تناقض وثيقة/كود بعد الآن).

5. **ملف السجل المحلي:** `LOGS/session_20261120/DUPLICATE_ANALYSIS.json` تم تحديثه: dup-004 وdup-005 أصبحا CONFIRMED.

6. **مقارنة 08_Temp_Review:** 298 مجموعة مكررة داخل `New folder_extracted` فقط (0 بين المجلدين). تقرير محفوظ في `LOGS/session_20261120/08_Temp_Review_internal_duplicates.json`. لا حذف تلقائي per user rule.
