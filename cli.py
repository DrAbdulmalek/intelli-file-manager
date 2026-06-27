#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IntelliFile - Command Line Interface (CLI)
واجهة سطر الأوامر التفاعلية لتطبيق IntelliFile
"""

import sys
import cmd
import logging
from pathlib import Path
from typing import Optional

# إضافة مسار المشروع إلى sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.config import Config
from src.core.file_handler import FileHandler
from src.core.ai_engine import AIEngine
from src.core.rag_engine import RAGEngine
from src.core.classifier import SmartFileClassifier


class IntelliFileCLI(cmd.Cmd):
    """واجهة سطر الأوامر التفاعلية لـ IntelliFile"""

    intro = """
╔═══════════════════════════════════════════════════════════╗
║           IntelliFile - نظام إدارة الملفات الذكي        ║
║                   واجهة سطر الأوامر                        ║
╚═══════════════════════════════════════════════════════════╝

اكتب 'help' أو '?' لعرض الأوامر المتاحة.
اكتب 'exit' للخروج من التطبيق.
"""

    prompt = "intellifile > "

    def __init__(self, config: Optional[Config] = None):
        super().__init__()

        # تحميل الإعدادات
        self.config = config if config else Config()

        # إعداد السجلات
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        self.logger = logging.getLogger("intellifile.cli")

        # تهيئة المحركات
        try:
            self.file_handler = FileHandler(self.config)
            self.ai_engine = AIEngine(self.config)
            self.rag_engine = RAGEngine()
            self.classifier = SmartFileClassifier(self.config)
            self.initialized = True
            self.logger.info("تم تهيئة جميع المحركات بنجاح")
        except Exception as e:
            self.logger.error(f"فشل التهيئة: {str(e)}")
            self.initialized = False
            self.file_handler = None
            self.ai_engine = None
            self.rag_engine = None
            self.classifier = None

    def preloop(self):
        """يتم استدعاؤها قبل بدء حلقة الأوامر"""
        if not self.initialized:
            print("تحذير: لم يتم تهيئة النظام بشكل كامل. بعض الأوامر قد لا تعمل.")

    def do_scan(self, arg):
        """
        مسح مجلد وتحليل محتوياته

        الاستخدام: scan <مسار_المجلد>
        مثال: scan /home/user/documents
        """
        if not arg:
            print("خطأ: يرجى تحديد مسار المجلد")
            print("مثال: scan /home/user/documents")
            return

        try:
            path = Path(arg).expanduser().resolve()
            if not path.exists():
                print(f"خطأ: المسار '{path}' غير موجود")
                return

            if not path.is_dir():
                print(f"خطأ: '{path}' ليس مجلداً")
                return

            print(f"جاري مسح المجلد: {path}")

            # Count files
            files = list(path.rglob("*"))
            files = [f for f in files if f.is_file() and not f.name.startswith(".")]

            print(f"\nتم العثور على {len(files)} ملفاً:")
            for i, f in enumerate(files[:20], 1):
                print(f"  {i:2d}. {f.name} ({f.suffix or 'بدون امتداد'})")

            if len(files) > 20:
                print(f"  ... و{len(files) - 20} ملفات أخرى")

        except Exception as e:
            print(f"خطأ: {str(e)}")
            self.logger.error(f"خطأ في scan: {str(e)}", exc_info=True)

    def do_search(self, arg):
        """
        بحث دلالي في المستندات المفهرسة

        الاستخدام: search <نص_البحث>
        مثال: search تقرير المبيعات السنوي
        """
        if not self.initialized or not self.rag_engine:
            print("خطأ: النظام غير مهيأ")
            return

        if not arg:
            print("خطأ: يرجى إدخال نص البحث")
            return

        try:
            print(f"جاري البحث عن: {arg}")
            response = self.rag_engine.query(arg)
            print(f"\nالنتيجة:\n{response}")

        except Exception as e:
            print(f"خطأ: {str(e)}")

    def do_classify(self, arg):
        """
        تصنيف ملف معين

        الاستخدام: classify <مسار_الملف>
        مثال: classify /home/user/doc.pdf
        """
        if not arg:
            print("خطأ: يرجى تحديد مسار الملف")
            return

        try:
            path = Path(arg).expanduser().resolve()
            if not path.exists():
                print(f"خطأ: الملف '{path}' غير موجود")
                return

            print(f"جاري تصنيف الملف: {path}")

            if self.ai_engine:
                suggestion = self.ai_engine.suggest_category(str(path), path.name)
                print(f"\nنتيجة التصنيف:")
                print(f"  الفئة: {suggestion}")
            else:
                print("خطأ: محرك الذكاء الاصطناعي غير مهيأ")

        except Exception as e:
            print(f"خطأ: {str(e)}")

    def do_chat(self, arg):
        """
        طرح سؤال على الذكاء الاصطناعي

        الاستخدام: chat <السؤال>
        مثال: chat ما هي النقاط الرئيسية في هذا التقرير؟
        """
        if not self.initialized or not self.ai_engine:
            print("خطأ: النظام غير مهيأ")
            return

        if not arg:
            print("خطأ: يرجى إدخال السؤال")
            return

        try:
            print(f"جاري معالجة السؤال: {arg}")
            response = self.ai_engine.chat(arg)
            print(f"\nالإجابة:\n{response}")

        except Exception as e:
            print(f"خطأ: {str(e)}")

    def do_status(self, arg):
        """عرض حالة النظام"""
        print("\nحالة النظام:")
        print(f"  نموذج الذكاء الاصطناعي: {self.config.ai_model}")
        print(f"  عنوان Ollama: {self.config.ollama_url}")
        print(f"  اللغة: {'العربية' if self.config.language == 'ar' else 'English'}")

        if self.ai_engine:
            try:
                status = self.ai_engine.is_ollama_running()
                print(f"  اتصال Ollama: {'متصل' if status else 'غير متصل'}")
            except Exception as e:
                print(f"  اتصال Ollama: خطأ - {e}")
        else:
            print("  محرك الذكاء الاصطناعي: غير مهيأ")

    def do_config(self, arg):
        """
        عرض أو تغيير الإعدادات

        الاستخدام:
          config              - عرض جميع الإعدادات
          config set key value - تغيير إعداد معين
        """
        if not arg:
            print("\nالإعدادات الحالية:")
            for key, value in vars(self.config).items():
                if not key.startswith('_'):
                    print(f"  {key}: {value}")
            return

        parts = arg.split(maxsplit=2)
        if parts[0].lower() == 'set' and len(parts) == 3:
            key, value = parts[1], parts[2]
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                print(f"تم تحديث {key} إلى {value}")
            else:
                print(f"خطأ: الإعداد '{key}' غير موجود")
        else:
            print("الاستخدام الصحيح: config set key value")

    def do_exit(self, arg):
        """الخروج من التطبيق"""
        print("\nشكراً لاستخدامك IntelliFile!")
        return True

    def do_quit(self, arg):
        """الخروج من التطبيق (مرادف لـ exit)"""
        return self.do_exit(arg)

    def do_EOF(self, arg):
        """معالجة Ctrl+D"""
        print()
        return self.do_exit(arg)

    def emptyline(self):
        """تجاهل الأسطر الفارغة"""
        pass

    def default(self, line):
        """معالجة الأوامر غير المعروفة"""
        print(f"أمر غير معروف: '{line}'")
        print("اكتب 'help' لعرض الأوامر المتاحة.")


def main():
    """الدالة الرئيسية لواجهة سطر الأوامر"""
    import argparse

    parser = argparse.ArgumentParser(description="IntelliFile CLI - واجهة سطر الأوامر")
    parser.add_argument('--config', type=str, default=None, help='مسار ملف الإعدادات')
    parser.add_argument('--verbose', '-v', action='store_true', help='وضع التفاصيل')
    args = parser.parse_args()

    # تحميل الإعدادات
    config = Config.load(args.config) if args.config and Path(args.config).exists() else Config()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # بدء واجهة سطر الأوامر التفاعلية
    try:
        cli = IntelliFileCLI(config)
        cli.cmdloop()
    except KeyboardInterrupt:
        print("\nتم إيقاف التطبيق بواسطة المستخدم")
        sys.exit(0)
    except Exception as e:
        print(f"\nخطأ حرج: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
