#!/usr/bin/env python3
"""
IntelliFile - Main Entry Point
النقطة الرئيسية لتشغيل تطبيق IntelliFile
"""

import sys
import argparse
import logging
from pathlib import Path

# إضافة مسار المشروع إلى sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.config import Config
from src.core.logger import setup_logger
from src.core.file_handler import FileHandler
from src.core.ai_engine import AIEngine
from src.core.rag_engine import RAGEngine
from src.core.classifier import DocumentClassifier

def main():
    """الدالة الرئيسية للتطبيق"""
    
    # إعداد محلل الأوامر
    parser = argparse.ArgumentParser(
        description="IntelliFile - نظام إدارة الملفات الذكي",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
أمثلة الاستخدام:
  %(prog)s --scan /path/to/folder
  %(prog)s --search "بحث عن مستند"
  %(prog)s --classify /path/to/file.pdf
  %(prog)s --chat "ما هو محتوى هذا الملف؟"
        """
    )
    
    # إضافة الخيارات
    parser.add_argument(
        '--scan', '-s',
        type=str,
        help='مسح مجلد وتحليل محتوياته'
    )
    parser.add_argument(
        '--search', '-q',
        type=str,
        help='بحث دلالي في المستندات'
    )
    parser.add_argument(
        '--classify', '-c',
        type=str,
        help='تصنيف ملف معين'
    )
    parser.add_argument(
        '--chat',
        type=str,
        help='طرح سؤال على الذكاء الاصطناعي حول المستندات'
    )
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='مسار ملف الإعدادات'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='تشغيل وضع التفاصيل'
    )
    parser.add_argument(
        '--version',
        action='version',
        version='IntelliFile v1.0.0'
    )
    
    args = parser.parse_args()
    
    # إعداد السجلات
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logger(level=log_level)
    
    try:
        # تحميل الإعدادات
        config = Config.load(args.config) if args.config else Config()
        
        logger.info("🚀 بدء تشغيل IntelliFile...")
        logger.debug(f"الإعدادات: {config}")
        
        # تهيئة المحركات
        file_handler = FileHandler(config)
        ai_engine = AIEngine(config)
        rag_engine = RAGEngine(config, ai_engine)
        classifier = DocumentClassifier(config)
        
        logger.info("✅ تم تهيئة جميع المحركات بنجاح")
        
        # معالجة الأوامر
        if args.scan:
            logger.info(f"📁 جاري مسح المجلد: {args.scan}")
            results = file_handler.scan_directory(args.scan)
            print(f"\n📊 تم العثور على {len(results)} ملفاً")
            for file_info in results[:10]:  # عرض أول 10 ملفات فقط
                print(f"  • {file_info['name']} ({file_info['type']})")
            if len(results) > 10:
                print(f"  ... و{len(results) - 10} ملفات أخرى")
            
            # فهرسة الملفات في قاعدة البيانات
            logger.info("📚 جاري فهرسة المستندات...")
            indexed = rag_engine.index_documents([f['path'] for f in results])
            logger.info(f"✅ تمت فهرسة {indexed} مستنداً")
            
        elif args.search:
            logger.info(f"🔍 جاري البحث عن: {args.search}")
            results = rag_engine.semantic_search(args.search, top_k=5)
            print(f"\n📋 نتائج البحث:")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. {result.get('file_name', 'Unknown')}")
                print(f"   التشابه: {result.get('similarity', 0):.2%}")
                print(f"   المحتوى: {result.get('content', '')[:200]}...")
                
        elif args.classify:
            logger.info(f"🏷️ جاري تصنيف الملف: {args.classify}")
            classification = classifier.classify_file(args.classify)
            print(f"\n📊 نتيجة التصنيف:")
            print(f"  النوع: {classification['category']}")
            print(f"  الثقة: {classification['confidence']:.1f}%")
            print(f"  الكلمات المفتاحية: {', '.join(classification['keywords'][:5])}")
            
        elif args.chat:
            logger.info(f"💬 جاري معالجة السؤال: {args.chat}")
            response = rag_engine.query(args.chat)
            print(f"\n🤖 الإجابة:\n{response}")
            
        else:
            # عرض المساعدة إذا لم يتم تحديد أي أمر
            parser.print_help()
            
            # عرض حالة النظام
            print("\n📊 حالة النظام:")
            print(f"  نموذج الذكاء الاصطناعي: {config.ai_model}")
            print(f"  قاعدة البيانات: {config.vector_db_path}")
            print(f"  اللغة: {'العربية' if config.language == 'ar' else 'English'}")
            
            # التحقق من اتصال Ollama
            try:
                status = ai_engine.check_connection()
                print(f"  اتصال Ollama: {'✅ متصل' if status else '❌ غير متصل'}")
            except Exception as e:
                print(f"  اتصال Ollama: ❌ خطأ - {str(e)}")
        
        logger.info("✨ اكتملت العملية بنجاح")
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️ تم إيقاف التطبيق بواسطة المستخدم")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ حدث خطأ: {str(e)}", exc_info=True)
        print(f"\n❌ خطأ: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
