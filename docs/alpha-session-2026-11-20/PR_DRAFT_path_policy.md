# PR draft: fix/p0-path-policy-bypass-only

**الفرع:** `fix/p0-path-policy-bypass-only`  
**الأصل:** `origin/main` (a8e6dd6)  
**الهدف:** جزء path_policy من PR #63 — الجزء السليم القابل للدمج  
**CI:** غير مرسل (prohibited per user rule — no push to GitHub)

---

## ما يحتويه هذا الفرع

تعديلات على `src/core/path_policy.py` و `src/core/file_handler.py` و `src/core/rule_engine.py` و `tests/unit/test_file_handler.py`:

1. **DEFAULT_SKIP_DIRS**: إضافة `.ssh` و `.config` إلى المجلدات المتجاهلة افتراضياً
2. **معالجة نقاط التركيب (mount points)**: `iter_files` لا يعبر نقاط التركيب
3. **إصلاح os.walk الصامت**: `on_error` يُبلغ عن الأخطاء بدلاً من تجاهلها صمتاً
4. **إغلاق مسارات الالتفاف**: إزالة مسارات الالتفاف في FileHandler وRuleEngine — SafeMover هو بوابة التنفيذ الوحيدة

---

## ما لا يحتويه (يُنقل إلى PR منفصل)

- SafeMover TOCTOU (F2–F5) → في `fix/p0-safe-mover-and-barrier`
- حاجز الحساسية (F1) → في `fix/p0-safe-mover-and-barrier`
- التراجع (F6/F7) → في `fix/p0-safe-mover-and-barrier`
- renameat2 (F8) → في `fix/p0-safe-mover-and-barrier`

---

## اختبار

| اختبار | حالة |
|-------|------|
| tests/unit/test_file_handler.py | ناجح |
| جميع اختبارات path_policy | ناجحة |

---

## قرار المطلوب

يُفتح PR على `fix/p0-path-policy-bypass-only` من `origin/main` للمراجعة قبل الدمج.
