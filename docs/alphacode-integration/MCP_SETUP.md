# إعداد خادم IntelliFile MCP — 2026-11-20

## التشغيل اليدوي (تأكيد سريع)

```bash
python -m src.mcp_server
# ثم أرسل على stdin سطر JSON لكل رسالة:
# {"jsonrpc":"2.0","id":0,"method":"initialize","params":{}}
```

## تسجيل في عميل وكيل (AlphaCode وأمثاله — مخطط MCP القياسي)

```json
{
  "mcpServers": {
    "intelli-file": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/مسار/المستودع/intelli-file-manager",
      "env": {
        "IFM_PREFERENCE_DB": "~/.local/share/intelli-file/preferences.db",
        "IFM_MCP_LOG_LEVEL": "WARNING"
      }
    }
  }
}
```

- `IFM_PREFERENCE_DB`: قاعدة SQLite للتفضيلات (تُنشأ تلقائياً). بدونها يعمل الخادم بذاكرة فقط (لا حفظ).
- لا شبكة، لا تبعيات خارجية — stdio فقط. كل البيانات محلية.

## الأدوات المتاحة (8)

| الأداة | الغرض | تغيّر الحالة؟ |
|---|---|---|
| `classify_path` | تصنيف حساسية مسار | لا |
| `safe_move_file` | نقل آمن (لاحقة عند التضارب) | نعم → token |
| `safe_copy_file` | نسخ آمن | نعم → token |
| `evaluate_rule` | محاكاة قواعد على ملف | لا |
| `undo_last` | تراجع عبر SafeMover | نعم → token |
| `query_action_log` | استعلام سجل الإجراءات | لا |
| `feedback_record` | تسجيل إشارة مستخدم | نعم (قاعدة البيانات) |
| `preference_query` | استرجاع تفضيلات متقادة | لا |

## الاختبار

```bash
python -m pytest tests/unit/test_mcp_feedback.py -v   # 18 اختباراً دائماً
```

يتضمن اختبار تشغيل الخادم كعملية فرعية حقيقية والتفاوض البروتوكولي (initialize + tools/list).
