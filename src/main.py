"""نقطة الدخول الرئيسية لتطبيق IntelliFile

يدعم ثلاثة أوضاع تشغيل:
1. واجهة رسومية (GUI) - افتراضي إذا توفرت PySide6
2. واجهة سطر أوامر (CLI)
3. وضع الخدمة (API Server)
"""
import sys
import logging
import argparse
from pathlib import Path


def setup_logging(verbose: bool = False):
    """تهيئة نظام التسجيل"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                str(Path.home() / ".intellifile" / "app.log"),
                encoding="utf-8",
            ),
        ],
    )


def main():
    """نقطة الدخول الرئيسية"""
    parser = argparse.ArgumentParser(
        prog="intellifile",
        description="IntelliFile - تطبيق تصنيف الملفات الذكي | Smart File Classifier",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="تفعيل السجلات التفصيلية")
    parser.add_argument("--version", action="version", version="IntelliFile v1.0.0")
    parser.add_argument("--no-gui", action="store_true", help="تشغيل بدون واجهة رسومية")
    parser.add_argument("--cli", action="store_true", help="تشغيل واجهة سطر الأوامر")
    parser.add_argument("--web", action="store_true", help="تشغيل خادم الويب فقط")
    parser.add_argument("--config", type=str, default=None, help="مسار ملف إعدادات مخصص")

    subparsers = parser.add_subparsers(dest="command", help="الأوامر المتاحة")

    # أمر التصنيف
    classify_parser = subparsers.add_parser("classify", help="تصنيف ملف أو مجلد")
    classify_parser.add_argument("path", help="مسار الملف أو المجلد")
    classify_parser.add_argument("--output", "-o", help="مجلد الإخراج")
    classify_parser.add_argument("--auto", action="store_true", help="تصنيف تلقائي بدون تأكيد")
    classify_parser.add_argument("--model", default=None, help="نموذج AI المطلوب")

    # أمر التنظيم
    organize_parser = subparsers.add_parser("organize", help="تنظيم الملفات في مجلدات")
    organize_parser.add_argument("path", help="مسار المجلد")
    organize_parser.add_argument("--dry-run", action="store_true", help="عرض ما سيحدث بدون تنفيذ")

    # أمر البحث
    search_parser = subparsers.add_parser("search", help="بحث دلالي في الملفات")
    search_parser.add_argument("query", help="نص البحث")
    search_parser.add_argument("path", nargs="?", default=".", help="مسار البحث")

    # أمر الكشف عن المكررات
    dup_parser = subparsers.add_parser("duplicates", help="كشف الملفات المكررة")
    dup_parser.add_argument("path", help="مسار المجلد")

    # أمر الإحصائيات
    stats_parser = subparsers.add_parser("stats", help="إحصائيات الملفات")
    stats_parser.add_argument("path", nargs="?", default=".", help="مسار المجلد")

    # أمر المحادثة
    chat_parser = subparsers.add_parser("chat", help="محادثة مع المساعد الذكي")
    chat_parser.add_argument("--model", default=None, help="نموذج AI")

    # أمر التحكم الصوتي
    voice_parser = subparsers.add_parser("voice", help="التحكم الصوتي")
    voice_parser.add_argument("--timeout", type=int, default=10, help="مدة الاستماع بالثواني")

    # أمر RAG
    rag_parser = subparsers.add_parser("rag", help="محرك RAG للإجابة عن أسئلة")
    rag_parser.add_argument("query", help="السؤال")
    rag_parser.add_argument("--path", nargs="?", default=".", help="مسار الملفات")

    args = parser.parse_args()

    # تهيئة التسجيل
    setup_logging(args.verbose)
    logger = logging.getLogger("intellifile")

    # إنشاء مجلد البيانات
    data_dir = Path.home() / ".intellifile"
    data_dir.mkdir(parents=True, exist_ok=True)

    # تحميل الإعدادات
    from src.core.config import Config
    config = Config.load(args.config)

    # إذا تم تحديد أمر فرعي - تنفيذه عبر CLI
    if args.command:
        from src.core.agent_cli import AgentCLI
        cli = AgentCLI()

        # بناء قائمة الأوامر
        cmd_args = [args.command]
        for key in vars(args):
            if key in ("command", "verbose", "no_gui", "cli", "web", "config"):
                continue
            val = getattr(args, key)
            if val is not None and val is not False:
                if isinstance(val, bool) and val:
                    cmd_args.append(f"--{key.replace('_', '-')}")
                elif isinstance(val, bool):
                    continue
                else:
                    cmd_args.append(str(val))

        result = cli.execute_command(args.command, cmd_args[1:])
        if not result.get("success"):
            print(f"\nخطأ: {result.get('error', 'غير معروف')}")
            sys.exit(1)
        return

    # الوضع التلقائي
    if args.web:
        _start_web_server(config, logger)
    elif args.cli or args.no_gui:
        from src.core.agent_cli import AgentCLI
        AgentCLI().parser.print_help()
    else:
        # محاولة تشغيل الواجهة الرسومية
        try:
            _start_gui(config, logger)
        except ImportError:
            logger.info("PySide6 غير متوفرة - التبديل إلى وضع CLI")
            from src.core.agent_cli import AgentCLI
            AgentCLI().parser.print_help()


def _start_gui(config, logger):
    """بدء واجهة سطح المكتب الرسومية"""
    try:
        from PySide6.QtWidgets import QApplication
        from src.gui.main_window import MainWindow
    except ImportError as e:
        logger.error(f"لا يمكن تشغيل الواجهة الرسومية: {e}")
        raise

    app = QApplication(sys.argv)
    app.setApplicationName("IntelliFile")
    app.setApplicationVersion("1.0.0")

    window = MainWindow(config)
    window.show()

    sys.exit(app.exec())


def _start_web_server(config, logger):
    """بدء خادم الويب"""
    import subprocess
    web_dir = Path(__file__).parent.parent / "web"

    if not web_dir.exists():
        logger.error(f"مجلد الويب غير موجود: {web_dir}")
        sys.exit(1)

    logger.info("جاري بدء خادم الويب...")
    logger.info("افتح http://localhost:3000 في المتصفح")

    try:
        subprocess.run(["npm", "run", "dev"], cwd=str(web_dir), check=True)
    except FileNotFoundError:
        logger.error("npm غير موجود. تأكد من تثبيت Node.js")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logger.error(f"خطأ في تشغيل خادم الويب: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
