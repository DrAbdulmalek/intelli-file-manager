# -*- coding: utf-8 -*-
"""طبقة MCP لـ intelli-file-manager — تكامل AlphaCode مع بروتوكولات المستودع.

يوفّر هذا الرزمة:
  - server.py: خادم MCP عبر stdio (JSON-RPC 2.0) بلا تبعيات خارجية
  - feedback.py: مخزن الإشارات (SQLite) ومتعلم التفضيلات
  - __main__.py: نقطة الدخول `python -m src.mcp_server`

العقد الثابت (غير القابل للتعلم — جوهر مقترح DeepSeek §7):
  - الحظر الأمني (sensitive_barrier) ورفض overwrite (SafeMover) خارج
    حلقة التفضيلات نهائياً — لا تفضيل مستخدم يعدّلهما.
"""
