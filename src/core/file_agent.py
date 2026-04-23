"""وكيل الملفات المستقل - مهام دورية ذكية"""
import logging
import threading
from pathlib import Path
from typing import Optional
from datetime import datetime
from .config import Config

logger = logging.getLogger(__name__)


class FileAgent:
    """وكيل مستقل يقوم بمهام دورية تلقائياً"""

    def __init__(self, classifier=None, search_engine=None, config=None):
        self.classifier = classifier
        self.search_engine = search_engine
        self.config = config or Config()
        self._running = False
        self._thread = None

    def start(self, directories: list = None, interval_minutes: int = 30):
        """بدء المراقبة الدورية"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop,
                                         args=(directories, interval_minutes),
                                         daemon=True)
        self._thread.start()
        logger.info("تم بدء وكيل الملفات")

    def stop(self):
        """إيقاف المراقبة"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("تم إيقاف وكيل الملفات")

    def _run_loop(self, directories: list, interval_minutes: int):
        """حلقة المراقبة الرئيسية"""
        import time
        while self._running:
            try:
                self.scan_and_organize(directories)
                time.sleep(interval_minutes * 60)
            except Exception as e:
                logger.error(f"خطأ في الحلقة: {e}")
                time.sleep(60)

    def scan_and_organize(self, directories: list = None) -> dict:
        """فحص المجلدات وتنظيمها"""
        results = {"scanned": 0, "classified": 0, "moved": 0, "errors": 0}

        dirs = directories or self.config.watch_directories
        if not dirs:
            return results

        for directory in dirs:
            dir_path = Path(directory)
            if not dir_path.is_dir():
                continue

            for item in dir_path.iterdir():
                if not item.is_file() or item.name.startswith("."):
                    continue

                results["scanned"] += 1
                try:
                    if self.classifier:
                        info = self.classifier.classify_file(str(item))
                        category = info.get("category", "أخرى")
                        results["classified"] += 1
                except Exception:
                    results["errors"] += 1

        logger.info(f"المسح: {results}")
        return results

    def detect_duplicates(self, directory: str) -> list:
        """كشف الملفات المكررة"""
        from .utils.helpers import compute_file_hash

        hashes = {}
        duplicates = []

        dir_path = Path(directory)
        for item in dir_path.rglob("*"):
            if not item.is_file():
                continue
            try:
                h = compute_file_hash(str(item))
                if h in hashes:
                    duplicates.append({
                        "original": hashes[h],
                        "duplicate": str(item),
                        "hash": h[:16],
                    })
                else:
                    hashes[h] = str(item)
            except Exception:
                continue

        logger.info(f"تم العثور على {len(duplicates)} ملف مكرر")
        return duplicates

    def daily_summary(self, directory: str) -> str:
        """إنشاء ملخص يومي للمجلد"""
        dir_path = Path(directory)
        total_size = 0
        file_count = 0
        extensions = {}

        for item in dir_path.rglob("*"):
            if item.is_file():
                file_count += 1
                total_size += item.stat().st_size
                ext = item.suffix.lower() or "بدون امتداد"
                extensions[ext] = extensions.get(ext, 0) + 1

        top_exts = sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:10]

        summary = f"📅 ملخص يومي - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        summary += f"📁 المجلد: {directory}\n"
        summary += f"📊 عدد الملفات: {file_count}\n"
        summary += f"💾 الحجم الكلي: {self._format_bytes(total_size)}\n\n"
        summary += "📊 أكثر الامتدادات:\n"
        for ext, count in top_exts:
            summary += f"  {ext or '(بدون)'}: {count} ملف\n"

        return summary

    @staticmethod
    def _format_bytes(size: int) -> str:
        if size == 0:
            return "0 بايت"
        for unit in ["بايت", "كيلوبايت", "ميغابايت", "غيغابايت"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} تيرابايت"
