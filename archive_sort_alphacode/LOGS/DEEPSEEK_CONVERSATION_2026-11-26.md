# محادثة DeepSeek / Z.ai - أرشيف الجلسة التقنية
**التاريخ:** 2026-11-26  
**المشروع:** intelli-file-manager / ocr-core / أسطول Marathon  
**المصدر:** Z.ai share + DeepSeek share (الرابط: https://chat.deepseek.com/share/6if5jxgq00odeq8qzg)

---

## ملخص الجلسة

### المشاريع المعنية
| المشروع | الحالة | الوصف |
|----------|--------|-------|
| **intelli-file-manager** | نشط | فرز الأرشيف، بوابة OCR مركزية |
| **ocr-core** | نشط | إصلاح #79: حل النماذج محليًا، privacy، policy |
| **repo-sync-toolkit** | نشط | جرد حي، مزامنة GitHub/HF |
| **marathon-suite** | تنسيق | حملات، بوابات صدق |

---

## القرارات التقنية الرئيسية

### 1. intelli-file-manager - فرز الأرشيف (Phase 5)
- **البوابة 1:** مغلقة ✅ (crops.db integrity ok, 55,124 صف، SHA-256 baseline)
- **البند 4 (الحساسيات v1):** معتمد ✅ (1,552 ملف)
- **البنود السبعة (§8):** معتمدة ✅
- **Deep Scan:** مكتمل (SHA-256=8a531618...)
- **id=156:** يحتاج مراجعة يدوية (قفزة إحداثيات 193→2224)
- **Metric 6 (سلة_تحقق):** 11,514 ملف مشتبه (mp3_: 6,030، jpg_: 5,412)
- **Phase 5 Trial Batch:** جاهز للتنفيذ (200-500 ملف، UndoLog، SHA-256، copy→verify→delete)

### 2. ocr-core - إصلاحات متعددة
| PR | الوصف | الحالة |
|----|-------|-------|
| #79 | فرض حل النماذج محليًا (LOCAL_ONLY افتراضيًا) | ✅ منفذ، CI أخضر |
| #80 | استعادة pii-scrubbing + 23 اختبار privacy | مسودة |
| #81 | إصلاح #79: model_policy، local_files_only، fallback | ✅ CI أخضر (544 passed) |

### 3. repo-sync-toolkit #17
- جرد حي كامل (45 مستودع + 9 أصول HF)
- manifest.json + سجل قرارات

---

## المشكلات المحلولة

### 1. crops.db Divergence
- **A (snapshot):** 55,124 صف
- **B (toolkit):** 55,141 صف (+17 صف، 25 تعديل)
- **القرار:** D ثم C موجّه - تحقيق id=156 أولاً، ثم اعتماد B كأساس مع حل 25 تعارض بالتصنيف

### 2. UndoLog Bug Fix
- **المشكلة:** `execute_plan()` ينادي `save()` بلا `append()`
- **الإصلاح:** إضافة `undo_log.append(UndoEntry(...))` للـ move/tag
- **إضافة:** حقل `checksum_before` في `UndoEntry` schema
- **الحارس:** منع `--out`/`--undo-log` داخل `--root` (self-deletion guard)

### 3. Git Push Failure
- **السبب:** ملفات ضخمة في التاريخ (dry_run_deep_pilot.html 54MB، dry_run_report_v3_deep.html 120MB)
- **الحل:** `git filter-repo --strip-blobs-bigger-than 50M` محليًا

---

## الخطوات التالية (Ready to Execute)

### فوري (Phase 5 Trial Batch)
```bash
# على مجلد صغير (50-100 ملف)
PYTHONPATH=src python3 scripts/archive_sort.py \
  --root "/run/media/xorthomson/My Passport/NewFolder/backup" \
  --rules archive_sort_alphacode/rules/archive_sort_rules.yaml \
  --execute --confirm-execute \
  --batch-size 500 \
  --undo-log .ifm_undo_backup_trial.json \
  --sensitive "هوية,جواز,بطاقة,رخصة,عقد,توقيع,فاتورة,بنك,حساب,طبي,تحليل,شخصي,خاص,عائلي,password,passwd,secret,token,wallet,seed,invoice,bank,contract,medical,.env,.local,.pem,.key,.p12,.pfx,.jks,.keystore" \
  --out /tmp/scratchpad/trial_backup_execute.html
```

### قبل أي كتابة على crops.db
1. عرض نتيجة id=156 كاملة (صف A، صف B، فروق، استنتاج)
2. تثبيت baseline SHA-256 الجديد لـ B
3. تحديث progress.md + session-handoff.md

### Git Housekeeping
```bash
cd /home/xorthomson/02_Projects/GitHub/GitHub/intelli-file-manager
git bundle create ~/ifm-backup-$(date +%F-%H%M).bundle --all
pip install git-filter-repo
git filter-repo --strip-blobs-bigger-than 50M --force
git remote add origin git@github.com:DrAbdulmalek/intelli-file-manager.git
git push -u origin feat/archive-sort-unified-decision
```

---

## الملفات المحدثة في الجلسة
- `scripts/archive_sort.py` - UndoLog append، checksum_before، self-deletion guard
- `src/core/rule_schemas.py` - حقل `checksum_before` في `UndoEntry`
- `archive_sort_alphacode/rules/archive_sort_rules.yaml` - 4 قواعد فرعية مفعلة
- `.gitignore` - استثناء `*.html` من LOGS/

---

## Notes for Next Session
- **لا ترفع البوابة 1 مرة أخرى** - مغلقة نهائياً
- **لا تبدأ الكتابة قبل id=156 + Metric 6** معروضة
- **trial batch على ملفات فقط** - لا crops.db
- **git filter-repo** مطلوب يدوياً قبل أي push مستقبلي
