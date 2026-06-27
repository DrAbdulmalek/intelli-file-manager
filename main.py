#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IntelliFile - نقطة الدخول الرئيسية للتطبيق

ملف الدخول الرئيسي على مستوى المشروع.
يوفّر واجهة بسيطة لتشغيل التطبيق بأوضاعه المختلفة:
  - واجهة رسومية (GUI)
  - واجهة سطر أوامر (CLI)
  - خادم الويب (Web)

الاستخدام:
    python main.py              # تشغيل الواجهة الرسومية
    python main.py --cli        # تشغيل واجهة سطر الأوامر
    python main.py --web        # تشغيل خادم الويب
    python main.py --help       # عرض المساعدة
"""

import sys
import os

# التأكد من أن مجلد المشروع في مسار Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    """نقطة الدخول الرئيسية - تفويض إلى src.main"""
    from src.main import main as _main
    _main()


if __name__ == "__main__":
    main()
