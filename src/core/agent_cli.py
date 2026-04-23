"""واجهة سطر أوامر البرمجي للتحكم بالوكيل"""
import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class AgentCLI:
    """واجهة سطر أوامر للتحكم في IntelliFile برمجياً"""

    def __init__(self):
        self.parser = self._build_parser()

    def _build_parser(self) -> argparse.ArgumentParser:
        """بناء محلل الأوامر"""
        parser = argparse.ArgumentParser(
            prog="intellifile",
            description="IntelliFile - تطبيق تصنيف الملفات الذكي",
        )
        parser.add_argument("-v", "--version", action="version", version="IntelliFile v1.0.0")
        parser.add_argument("--no-gui", action="store_true", help="تشغيل بدون واجهة رسومية")

        subparsers = parser.add_subparsers(dest="command")

        # أمر التصنيف
        classify = subparsers.add_parser("classify", help="تصنيف الملفات")
        classify.add_argument("path", help="مسار المجلد أو الملف")
        classify.add_argument("--output", "-o", help="مجلد الإخراج")
        classify.add_argument("--model", default="gemma3", help="نموذج AI")
        classify.add_argument("--auto", action="store_true", help="تصنيف تلقائي بدون تأكيد")

        # أمر التنظيم
        organize = subparsers.add_parser("organize", help="تنظيم الملفات في مجلدات")
        organize.add_argument("path", help="مسار المجلد")
        organize.add_argument("--dry-run", action="store_true", help="عرض ما سيحدث بدون تنفيذ")

        # أمر البحث
        search = subparsers.add_parser("search", help="بحث في الملفات")
        search.add_argument("query", help="نص البحث")
        search.add_argument("path", nargs="?", default=".", help="مسار البحث")

        # أمر المحادثة
        chat = subparsers.add_parser("chat", help="محادثة مع المساعد الذكي")
        chat.add_argument("--model", default="gemma3", help="نموذج AI")

        # أمر الكشف عن المكررات
        dup = subparsers.add_parser("duplicates", help="كشف الملفات المكررة")
        dup.add_argument("path", help="مسار المجلد")
        dup.add_argument("--delete", action="store_true", help="حذف المكررات تلقائياً")

        # أمر الإحصائيات
        stats = subparsers.add_parser("stats", help="إحصائيات الملفات")
        stats.add_argument("path", nargs="?", default=".", help="مسار المجلد")

        # أمر الجدول الزمني
        schedule = subparsers.add_parser("schedule", help="جدولة المهام الدورية")

        # أمر الصوت
        voice = subparsers.add_parser("voice", help="التحكم الصوتي")
        voice.add_argument("--timeout", type=int, default=10, help="مدة الاستماع")

        # أمر RAG
        rag = subparsers.add_parser("rag", help="محرك RAG للإجابة عن أسئلة")
        rag.add_argument("query", help="السؤال")
        rag.add_argument("--path", nargs="?", default=".", help="مسار الملفات")

        return parser

    def parse_args(self, args=None):
        """تحليل الأوامر"""
        return self.parser.parse_args(args)

    def execute_command(self, command: str, args: list = None) -> dict:
        """تنفيذ أمر CLI"""
        args = [command] + (args or [])
        parsed = self.parse_args(args)
        logger.info(f"تنفيذ: {command} {args}")

        if parsed.command == "classify":
            return self._cmd_classify(parsed)
        elif parsed.command == "organize":
            return self._cmd_organize(parsed)
        elif parsed.command == "search":
            return self._cmd_search(parsed)
        elif parsed.command == "chat":
            return self._cmd_chat(parsed)
        elif parsed.command == "duplicates":
            return self._cmd_duplicates(parsed)
        elif parsed.command == "stats":
            return self._cmd_stats(parsed)
        elif parsed.command == "voice":
            return self._cmd_voice(parsed)
        elif parsed.command == "rag":
            return self._cmd_rag(parsed)
        else:
            self.parser.print_help()
            return {"success": False, "error": "أمر غير معروف"}

    def _cmd_classify(self, args) -> dict:
        """تنفيذ التصنيف"""
        from .classifier import SmartFileClassifier
        from .config import Config
        config = Config()
        classifier = SmartFileClassifier(config)
        path = Path(args.path)

        if path.is_file():
            result = classifier.classify_file(str(path))
            print(f"\n📁 {result['name']}")
            print(f"   التصنيف: {result['category']}")
            print(f"   الثقة: {result['confidence']}%")
            print(f"   النوع: {result['content_type']}")
            return {"success": True, "results": [result]}
        elif path.is_dir():
            results = classifier.batch_classify(str(path))
            stats = classifier.get_stats(results)
            print(f"\n✅ تم تصنيف {len(results)} ملف في {args.path}")
            for cat, count in stats.items():
                print(f"   {cat}: {count} ملف")
            return {"success": True, "stats": stats, "results": results}
        else:
            return {"success": False, "error": "المسار غير موجود"}

    def _cmd_organize(self, args) -> dict:
        """تنفيذ التنظيم"""
        from .classifier import SmartFileClassifier
        from .file_handler import FileHandler
        from .config import Config

        config = Config()
        classifier = SmartFileClassifier(config)
        handler = FileHandler(config)
        path = Path(args.path)

        if not path.is_dir():
            return {"success": False, "error": "المسار ليس مجلداً"}

        results = classifier.batch_classify(str(path))
        created = handler.create_category_folders(str(path))

        if args.dry_run:
            print("\n🔍 وضع تجريبي:")
            for r in results:
                print(f"   {r['name']} -> {r['category']}/")
            return {"success": True, "dry_run": True, "results": results}

        moved = 0
        for r in results:
            result = handler.move_file(r["path"], r["category"], str(path))
            if result.get("success"):
                moved += 1

        print(f"\n✅ تم نقل {moved} ملف")
        return {"success": True, "moved": moved, "results": results}

    def _cmd_search(self, args) -> dict:
        """تنفيذ البحث الدلالي"""
        from .semantic_search import SemanticSearchEngine
        engine = SemanticSearchEngine()

        if args.path != ".":
            engine.index_files(args.path)

        results = engine.search(args.query)
        if not results:
            print(f"\nلم يتم العثور على نتائج لـ: {args.query}")
            return {"success": True, "results": []}

        print(f"\n🔍 نتائج البحث عن '{args.query}':")
        for filepath, score in results:
            print(f"   {Path(filepath).name} ({score:.1%})")
        return {"success": True, "results": results}

    def _cmd_chat(self, args) -> dict:
        """محادثة مع AI"""
        from .ai_engine import AIEngine
        from .config import Config
        engine = AIEngine(Config(model=args.model))

        if not engine.is_ollama_running():
            print("\n❌ Ollama غير متاح. تأكد من تشغيله:")
            print("   ollama serve")
            return {"success": False, "error": "Ollama غير متاح"}

        print("\n💬 المحادثة مع IntelliFile (اكتب 'خروج' للإنهاء):")
        while True:
            try:
                user_input = input("أنت: ").strip()
                if user_input.lower() in ("خروج", "exit", "q"):
                    break
                response = engine.chat(user_input)
                print(f"\n🤖 IntelliFile: {response}\n")
            except (KeyboardInterrupt, EOFError):
                break
        return {"success": True}

    def _cmd_duplicates(self, args) -> dict:
        """كشف المكررات"""
        from .file_agent import FileAgent
        agent = FileAgent()
        path = Path(args.path)

        if not path.is_dir():
            return {"success": False, "error": "المسار ليس مجلداً"}

        duplicates = agent.detect_duplicates(str(path))
        if not duplicates:
            print(f"\n✅ لا توجد ملفات مكررة في {args.path}")
            return {"success": True, "duplicates": []}

        print(f"\n⚠️ تم العثور على {len(duplicates)} مجموعة من المكررات:")
        for i, group in enumerate(duplicates, 1):
            print(f"\n  المجموعة {i}:")
            print(f"    الأصلي: {Path(group[0]).name}")
            for dup in group[1:]:
                print(f"    مكرر: {Path(dup).name}")

        return {"success": True, "groups": duplicates}

    def _cmd_stats(self, args) -> dict:
        """إحصائيات"""
        from .file_agent import FileAgent
        agent = FileAgent()
        path = Path(args.path)

        summary = agent.daily_summary(str(path))
        print(f"\n{summary}")
        return {"success": True, "summary": summary}

    def _cmd_voice(self, args) -> dict:
        """التحكم الصوتي"""
        from .voice_controller import VoiceController
        vc = VoiceController()
        print(f"\n🎤 جاري الاستماع ({args.timeout} ثانية)... اقل 'توقف' لإيقاف")
        text = vc.listen(args.timeout)
        if text:
            command = vc.parse_command(text)
            vc.speak(f"تنفيذ: {command['action']}")
            return {"success": True, "command": command, "text": text}
        return {"success": False, "error": "لم يتم التعرف على نص"}

    def _cmd_rag(self, args) -> dict:
        """محرك RAG"""
        from .rag_engine import RAGEngine
        engine = RAGEngine()

        if args.path != ".":
            import glob
            for f in glob.glob(str(Path(args.path) / "**/*"), recursive=True):
                if Path(f).is_file():
                    engine.ingest_file(f)

        answer = engine.query(args.query)
        print(f"\n📖 سؤال: {args.query}")
        print(f"\n💡 الإجابة:\n{answer}")
        return {"success": True, "answer": answer}


def main():
    """نقطة الدخول الرئيسية"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    cli = AgentCLI()

    if len(sys.argv) < 2:
        cli.parser.print_help()
        return

    result = cli.execute_command(sys.argv[1], sys.argv[2:])
    if not result.get("success"):
        print(f"\n❌ خطأ: {result.get('error', 'غير معروف')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
