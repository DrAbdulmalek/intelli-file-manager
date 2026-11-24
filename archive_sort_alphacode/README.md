# archive_sort_alphacode — ناتج عمل AlphaCode

> ⚠️ **هذا المجلد وكل محتوياته ناتج عن عمل الوكيل AlphaCode** (v1.1.20).
> أُنشئ في جلسة 2026-11-24 لتطبيق "القرار الموحد لفرز الأرشيف" على قرص
> `/run/media/xorthomson/My Passport/` باستخدام قواعد مشروع
> `intelli-file-manager`. راجعه المالك قبل أي اعتماد أو تنفيذ.

## المحتويات

| المسار | الوصف |
|--------|-------|
| `scripts/archive_sort.py` | سكريبت فرز **قراءة فقط** (مسح + dry-run HTML بفلاتر). لا ينفّذ أي نقل. |
| `rules/archive_sort_rules.yaml` | ملف القواعد المبني من القرار الموحد (12 قاعدة، 7 وجهات). |
| `LOGS/` | السجلات المفصلة وتقرير المحاكاة (يُملأ بعد تشغيل المسح). |

## الاستخدام (آمن — لا يكتب على القرص)

```bash
cd /home/xorthomson/02_Projects/GitHub/GitHub/intelli-file-manager
python3 archive_sort_alphacode/scripts/archive_sort.py \
    --root "/run/media/xorthomson/My Passport" \
    --out archive_sort_alphacode/LOGS/dry_run_report.html
```

## الأمان والحدود

- **قراءة فقط**: يستخدم `FileInventory` و`RuleEngine.dry_run` — لا نقل ولا حذف.
- **التنفيذ الفعلي غير متاح** في هذا السكريبت؛ هو مرحلة منفصلة معتمدة يدوياً
  بعد اجتياز بوابة تأمين النسختين الخارجيتين لـ `crops.db`.
- **لا تفريغ تلقائي** لسلة_التحقق؛ التفريغ بقرار يدوي موثق بعد 30 يوماً.

## المرجع

- القرار: `القرار_الموحد_لفرز_الأرشيف.docx` (2026-11-24)
- الجرد: `جرد_الأرشيف_وخطة_الفرز.xlsx`
- الأداة: intelli-file-manager | GitHub main = 5a96a05 (الإصدار 1.7)

---
*ناتج عمل AlphaCode — 2026-11-24 — Mile: لا تنفيذ فعلي على القرص قبل اعتماد المالك.*