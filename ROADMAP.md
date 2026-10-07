# ROADMAP — IntelliFile Manager

> خطة الإصدارات القادمة — تُحدَّث مع كل إصدار. الوضع الحالي: v2.2.0-dev.

## v2.2 — قصاصات التدريب + محرر OCR (هذا الإصدار)

- [x] خدمة OCR المركزية `ocr_service` (تستهلك ocr-core v0.5+)
- [x] قصاصات تدريب SQLite (`src/db/snippet_db.py`) + API كامل (CRUD/approve/reject/export)
- [x] محرر مربعات الويب `edit-ocr` (BBoxEditor + SnippetPanel + GlossarySuggest)
- [x] المسارد الطبية: `/api/glossary/suggest` (741 زوجًا مدمجًا + دعم المسرد الكامل عبر env)
- [x] تصدير HuggingFace: JSONL محلي + رفع صريح يتطلب توكنًا صريحًا
- [x] وضع خفيف بلا LLM (`INTELLIFILE_LIGHTWEIGHT=1`)
- [x] Rate limiting على /api/* (بدون تبعيات جديدة)
- [x] أساس المراقبة (PR #38: SQLite + JSONL observability)

## v2.3 — القياس والجودة

- [ ] harness قياس CER/WER للعربية على عينة `arabic-medical-ocr-corrections`
- [ ] بوابة تغطية اختبارات في CI + badge في README
- [ ] معالجة أخطاء موحدة للمستندات التالفة (تقرير حالة لكل ملف)
- [ ] توثيق دعم Windows/macOS بجانب Linux

## v2.4 — التوزيع والمراقبة

- [ ] حزم: pip (pyproject كامل) + AppImage + تقييم DMG/MSI
- [ ] `/metrics` (prometheus_client) + logging مركزي
- [ ] لوحة ربط heatmap الثقة بنتائج OCR الحية (بعد استقرار القصاصات)

## v3 — الرؤية

- [ ] محرك عربي مخصص مدرّب على القصاصات المعتمدة (بعد 5k قصاصة)
- [ ] مزامنة المسرد مع glossary-api
- [ ] واجهة سطح المكتب (PySide6) لمحرر القصاصات بجانب الويب
