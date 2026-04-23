#!/usr/bin/env python3
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
from src.core.logger import setup_logger
from src.core.file_handler import FileHandler
from src.core.ai_engine import AIEngine
from src.core.rag_engine import RAGEngine
from src.core.classifier import DocumentClassifier


class IntelliFileCLI(cmd.Cmd):
    """واجهة سطر الأوامر التفاعلية لـ IntelliFile"""
    
    intro = """
╔═══════════════════════════════════════════════════════════╗
║           🚀 IntelliFile - نظام إدارة الملفات الذكي        ║
║                   واجهة سطر الأوامر                        ║
╚═══════════════════════════════════════════════════════════╝

اكتب 'help' أو '?' لعرض الأوامر المتاحة.
اكتب 'exit' للخروج من التطبيق.
"""
    
    prompt = "📁 intellifile > "
    
    def __init__(self, config: Optional[Config] = None):
        super().__init__()
        
        # تحميل الإعدادات
        self.config = config if config else Config()
        
        # إعداد السجلات
        self.logger = setup_logger(level=logging.INFO)
        
        # تهيئة المحركات
        try:
            self.file_handler = FileHandler(self.config)
            self.ai_engine = AIEngine(self.config)
            self.rag_engine = RAGEngine(self.config, self.ai_engine)
            self.classifier = DocumentClassifier(self.config)
            self.initialized = True
            self.logger.info("✅ تم تهيئة جميع المحركات بنجاح")
        except Exception as e:
            self.logger.error(f"❌ فشل التهيئة: {str(e)}")
            self.initialized = False
            self.file_handler = None
            self.ai_engine = None
            self.rag_engine = None
            self.classifier = None
    
    def preloop(self):
        """يتم استدعاؤها قبل بدء حلقة الأوامر"""
        if not self.initialized:
            print("⚠️ تحذير: لم يتم تهيئة النظام بشكل كامل. بعض الأوامر قد لا تعمل.")
    
    def do_scan(self, arg):
        """
        مسح مجلد وتحليل محتوياته
        
        الاستخدام: scan <مسار_المجلد>
        مثال: scan /home/user/documents
        """
        if not self.initialized or not self.file_handler:
            print("❌ الخطأ: النظام غير مهيأ")
            return
        
        if not arg:
            print("❌ الخطأ: يرجى تحديد مسار المجلد")
            print("مثال: scan /home/user/documents")
            return
        
        try:
            path = Path(arg).expanduser().resolve()
            if not path.exists():
                print(f"❌ الخطأ: المسار '{path}' غير موجود")
                return
            
            if not path.is_dir():
                print(f"❌ الخطأ: '{path}' ليس مجلداً")
                return
            
            print(f"📁 جاري مسح المجلد: {path}")
            results = self.file_handler.scan_directory(str(path))
            
            print(f"\n📊 تم العثور على {len(results)} ملفاً:")
            for i, file_info in enumerate(results[:20], 1):
                print(f"  {i:2d}. {file_info['name']} ({file_info['type']}, {file_info.get('size', 'N/A')})")
            
            if len(results) > 20:
                print(f"  ... و{len(results) - 20} ملفات أخرى")
            
            # سؤال عن الفهرسة
            if results:
                response = input("\n📚 هل تريد فهرسة هذه المستندات؟ (y/n): ")
                if response.lower() in ['y', 'yes', 'نعم']:
                    print("🔄 جاري الفهرسة...")
                    indexed = self.rag_engine.index_documents([f['path'] for f in results])
                    print(f"✅ تمت فهرسة {indexed} مستنداً بنجاح")
                    
        except Exception as e:
            print(f"❌ حدث خطأ: {str(e)}")
            self.logger.error(f"خطأ في scan: {str(e)}", exc_info=True)
    
    def do_search(self, arg):
        """
        بحث دلالي في المستندات المفهرسة
        
        الاستخدام: search <نص_البحث>
        مثال: search تقرير المبيعات السنوي
        """
        if not self.initialized or not self.rag_engine:
            print("❌ الخطأ: النظام غير مهيأ")
            return
        
        if not arg:
            print("❌ الخطأ: يرجى إدخال نص البحث")
            print("مثال: search تقرير المبيعات")
            return
        
        try:
            print(f"🔍 جاري البحث عن: {arg}")
            results = self.rag_engine.semantic_search(arg, top_k=5)
            
            if not results:
                print("⚠️ لم يتم العثور على نتائج")
                return
            
            print(f"\n📋 نتائج البحث ({len(results)} نتائج):")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. 📄 {result.get('file_name', 'Unknown')}")
                print(f"   📊 التشابه: {result.get('similarity', 0):.2%}")
                content = result.get('content', '')
                if len(content) > 200:
                    content = content[:200] + "..."
                print(f"   📝 المحتوى: {content}")
                
        except Exception as e:
            print(f"❌ حدث خطأ: {str(e)}")
            self.logger.error(f"خطأ في search: {str(e)}", exc_info=True)
    
    def do_classify(self, arg):
        """
        تصنيف ملف معين
        
        الاستخدام: classify <مسار_الملف>
        مثال: classify /home/user/doc.pdf
        """
        if not self.initialized or not self.classifier:
            print("❌ الخطأ: النظام غير مهيأ")
            return
        
        if not arg:
            print("❌ الخطأ: يرجى تحديد مسار الملف")
            print("مثال: classify /home/user/document.pdf")
            return
        
        try:
            path = Path(arg).expanduser().resolve()
            if not path.exists():
                print(f"❌ الخطأ: الملف '{path}' غير موجود")
                return
            
            if not path.is_file():
                print(f"❌ الخطأ: '{path}' ليس ملفاً")
                return
            
            print(f"🏷️ جاري تصنيف الملف: {path}")
            classification = self.classifier.classify_file(str(path))
            
            print(f"\n📊 نتيجة التصنيف:")
            print(f"  📁 النوع: {classification['category']}")
            print(f"  📈 الثقة: {classification['confidence']:.1f}%")
            print(f"  🔑 الكلمات المفتاحية: {', '.join(classification['keywords'][:5])}")
            if 'subcategory' in classification:
                print(f"  📂 الفئة الفرعية: {classification['subcategory']}")
                
        except Exception as e:
            print(f"❌ حدث خطأ: {str(e)}")
            self.logger.error(f"خطأ في classify: {str(e)}", exc_info=True)
    
    def do_chat(self, arg):
        """
        طرح سؤال على الذكاء الاصطناعي حول المستندات
        
        الاستخدام: chat <السؤال>
        مثال: chat ما هي النقاط الرئيسية في هذا التقرير؟
        """
        if not self.initialized or not self.rag_engine:
            print("❌ الخطأ: النظام غير مهيأ")
            return
        
        if not arg:
            print("❌ الخطأ: يرجى إدخال السؤال")
            print("مثال: chat ما هو محتوى هذا الملف؟")
            return
        
        try:
            print(f"💬 جاري معالجة السؤال: {arg}")
            response = self.rag_engine.query(arg)
            print(f"\n🤖 الإجابة:\n{response}")
            
        except Exception as e:
            print(f"❌ حدث خطأ: {str(e)}")
            self.logger.error(f"خطأ في chat: {str(e)}", exc_info=True)
    
    def do_status(self, arg):
        """عرض حالة النظام"""
        print("\n📊 حالة النظام:")
        print(f"  🤖 نموذج الذكاء الاصطناعي: {self.config.ai_model}")
        print(f"  💾 قاعدة البيانات: {self.config.vector_db_path}")
        print(f"  🌐 اللغة: {'العربية' if self.config.language == 'ar' else 'English'}")
        print(f"  📁 مجلد العمل: {self.config.working_dir}")
        
        if self.ai_engine:
            try:
                status = self.ai_engine.check_connection()
                print(f"  🔌 اتصال Ollama: {'✅ متصل' if status else '❌ غير متصل'}")
            except Exception as e:
                print(f"  🔌 اتصال Ollama: ❌ خطأ - {str(e)}")
        else:
            print("  🔌 محرك الذكاء الاصطناعي: ❌ غير مهيأ")
    
    def do_config(self, arg):
        """
        عرض أو تغيير الإعدادات
        
        الاستخدام: 
          config              - عرض جميع الإعدادات
          config set key value - تغيير إعداد معين
        """
        if not arg:
            print("\n⚙️ الإعدادات الحالية:")
            for key, value in vars(self.config).items():
                if not key.startswith('_'):
                    print(f"  {key}: {value}")
            return
        
        parts = arg.split(maxsplit=2)
        if parts[0].lower() == 'set' and len(parts) == 3:
            key, value = parts[1], parts[2]
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                print(f"✅ تم تحديث {key} إلى {value}")
            else:
                print(f"❌ الخطأ: الإعداد '{key}' غير موجود")
        else:
            print("❌ الاستخدام الصحيح: config set key value")
    
    def do_index(self, arg):
        """
        فهرسة ملفات محددة
        
        الاستخدام: index <مسار1> [مسار2 ...]
        مثال: index file1.pdf file2.docx /path/to/folder
        """
        if not self.initialized or not self.rag_engine:
            print("❌ الخطأ: النظام غير مهيأ")
            return
        
        if not arg:
            print("❌ الخطأ: يرجى تحديد ملفات للفهرسة")
            return
        
        try:
            paths = []
            for item in arg.split():
                path = Path(item).expanduser().resolve()
                if path.exists():
                    if path.is_file():
                        paths.append(str(path))
                    elif path.is_dir():
                        # مسح المجلد وإضافة جميع الملفات
                        files = self.file_handler.scan_directory(str(path))
                        paths.extend([f['path'] for f in files])
                else:
                    print(f"⚠️ المسار '{path}' غير موجود، تم تجاوزه")
            
            if not paths:
                print("❌ لم يتم العثور على ملفات صالحة للفهرسة")
                return
            
            print(f"📚 جاري فهرسة {len(paths)} ملفاً...")
            indexed = self.rag_engine.index_documents(paths)
            print(f"✅ تمت فهرسة {indexed} مستنداً بنجاح")
            
        except Exception as e:
            print(f"❌ حدث خطأ: {str(e)}")
            self.logger.error(f"خطأ في index: {str(e)}", exc_info=True)
    
    def do_clear(self, arg):
        """مسح قاعدة البيانات"""
        confirm = input("⚠️ هل أنت متأكد من مسح قاعدة البيانات؟ (y/n): ")
        if confirm.lower() in ['y', 'yes', 'نعم']:
            try:
                self.rag_engine.clear_database()
                print("✅ تم مسح قاعدة البيانات بنجاح")
            except Exception as e:
                print(f"❌ حدث خطأ: {str(e)}")
        else:
            print("ℹ️ تم إلغاء العملية")
    
    def do_exit(self, arg):
        """الخروج من التطبيق"""
        print("\n👋 شكراً لاستخدامك IntelliFile!")
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
        print(f"❌ أمر غير معروف: '{line}'")
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
        setup_logger(level=logging.DEBUG)
    else:
        setup_logger(level=logging.INFO)
    
    # بدء واجهة سطر الأوامر
    try:
        cli = IntelliFileCLI(config)
        cli.cmdloop()
    except KeyboardInterrupt:
        print("\n\n⚠️ تم إيقاف التطبيق بواسطة المستخدم")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ حدث خطأ حرج: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
