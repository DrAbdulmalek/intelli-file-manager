# -*- coding: utf-8 -*-
"""نقطة الدخول: `python -m src.mcp_server`

المتغيرات البيئية:
  IFM_PREFERENCE_DB      مسار قاعدة التفضيلات SQLite (اختياري — بدونها ذاكرة فقط)
  IFM_MCP_LOG_LEVEL      مستوى السجل على stderr (افتراضي WARNING)
"""
from .server import main

if __name__ == "__main__":
    main()
