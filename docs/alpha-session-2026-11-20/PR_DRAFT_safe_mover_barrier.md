# PR draft: fix/p0-safe-mover-and-barrier

**الفرع:** `fix/p0-safe-mover-and-barrier`  
**الأصل:** `origin/main` (a8e6dd6)  
**الهدف:** جزء SafeMover + حاجز الحساسية من PR #63 — الجزء المعيب الذي يُعاد بناؤه مع إصلاح F1–F8  
**CI:** غير مرسل (prohibited per user rule — no push to GitHub)

---

## ما يحتويه هذا الفرع

إصلاح جميع العيوب الثمانية (F1–F8) التي وجدتها المراجعة المستقلة (CLAUDE_INDEPENDENT_REVIEW_2026-11-20):

### F1 — حاجز الحساسية (High)
- تمديد التغطية إلى `ocr_service.py` و `file_inventory.py` بالإضافة إلى `classifier.py`
- `_has_dicom_header()`: يقرأ 4 بايتات عند الإزاحة 128 (`DICM`) دون فتح المحتوى
- `_name_parts_lower()`: مطابقة بحدود كلمات (word-boundary) تمنع إنذارات كاذبة (`mri` داخل `Amrita`)
- `external_send_allowed()`: مُنفذ فعلياً (لم يعد كوداً ميتاً)، يُمنع إرسال الملفات الحساسة لأي خدمة خارجية

### F2–F5 — SafeMover (High)
- `renameat2(RENAME_NOREPLACE)` عبر ctypes على لينكس، مع fallback `os.link`+`unlink`
- رفض الاستبدال الصامت (لا overwrite فوق موجودة)
- `try/finally` على `BaseException` (يغطي `KeyboardInterrupt`)
- رفض النقل/النسخ فوق مجلد موجود (P5)

### F6/F7 — التراجع (High)
- `undo_last_action` يستخدم `SafeMover.move` بدلاً من `shutil.move(dest, src)` الصامت
- لو وُجد ملف جديد بالاسم الأصلي → يُحفظ في مكانه (لا يُستبدل، لا يُحذف)

### F8 — تناقض الوثيقة/كود (High)
- `renameat2` موثق ومُنفذ في الكود (لا تناقض بعد الآن)

---

## اختبار دائم

`tests/unit/test_f1_f8_inversion.py` — 12 اختباراً، جميعها **تمر** على الكود المصلح:

| # | التجربة | الحالة |
|---|---------|--------|
| A1 | أسماء أشعة عامة → تُمسح كطبية | FIXED-VERIFIED |
| A2 | إنذارات كاذبة → NON_SENSITIVE | FIXED-VERIFIED |
| A3 | DICOM header على امتداد عام → يُكتشف | FIXED-VERIFIED |
| A4 | external_send_allowed يُمنع الحساس | FIXED-VERIFIED |
| P1 | TOCTOU يُرفض الاستبدال | FIXED-VERIFIED |
| P3 | غير OSError يُ捕获، المصدر محفوظ | FIXED-VERIFIED |
| P4 | KeyboardInterrupt يُ捕获، المصدر محفوظ | FIXED-VERIFIED |
| P5 | overwrite على مجلد → رفض صريح | FIXED-VERIFIED |
| U | التراجع لا يدمر الملف الجديد | FIXED-VERIFIED |
| F8 | renameat2 منفذ وموثق | FIXED-VERIFIED |

---

## فحوصات الجودة

| الفحص | النتيجة |
|-------|---------|
| `python3 -m pytest tests/unit/test_f1_f8_inversion.py -v` | 12/12 ناجح |
| `python3 -c "from src.core.safe_mover import SafeMover"` | ينجح |
| `python3 -c "from src.core.sensitive_barrier import external_send_allowed"` | ينجح |

---

## قرار المطلوب

يُفتح PR على `fix/p0-safe-mover-and-barrier` من `origin/main` للمراجعة قبل الدمج. لا يُدمج مع PR #63 كما هو.
