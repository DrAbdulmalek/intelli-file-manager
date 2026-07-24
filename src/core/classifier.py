"""مصنف الملفات الذكي - يجمع بين القواعد والمحرك الذكي

This classifier handles general-purpose file categorization (documents, code,
images, archives, etc.) using extension rules and content-based detection
via Magika. It does NOT perform domain-specific classification (medical,
legal, financial). For domain-specific classification, use a plugin or
external service.
"""
import logging
from pathlib import Path
from typing import Optional
from .config import Config

logger = logging.getLogger(__name__)


class SmartFileClassifier:
    """مصنف ذكي يجمع بين التصنيف بالامتداد والمحتوى"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self._magika = None
        self._init_magika()

    def _init_magika(self):
        """تهيئة مكتبة Magika للتصنيف بالمحتوى"""
        try:
            from magika import Magika
            self._magika = Magika()
            logger.info("تم تهيئة Magika بنجاح")
        except ImportError:
            logger.warning("Magika غير مثبتة - سيعتم التصنيف بالامتداد فقط")
            self._magika = None
        except Exception as e:
            logger.warning(f"خطأ في تهيئة Magika: {e}")
            self._magika = None

    def classify_file(self, filepath: str) -> dict:
        """تصنيف ملف واحد وإرجاع معلوماته"""
        path = Path(filepath)
        if not path.exists():
            return {"error": f"الملف غير موجود: {filepath}"}

        extension = path.suffix.lower()
        category = self.config.get_category(extension)
        confidence = 85.0  # default for rule-based
        content_type = "unknown"

        # محاولة التصنيف بالمحتوى
        if self._magika:
            try:
                result = self._magika.identify_path(filepath)
                if result and hasattr(result, "output"):
                    magika_type = result.output
                    content_type = magika_type
                    mapped = self._map_magika_type(magika_type)
                    if mapped and mapped != "أخرى":
                        category = mapped
                        confidence = 95.0
                    elif extension and self.config.get_category(extension) != "أخرى":
                        confidence = 75.0
            except Exception as e:
                logger.debug(f"خطأ في تصنيف Magika: {e}")

        stat = path.stat()
        return {
            "name": path.name,
            "path": str(path),
            "extension": extension,
            "category": category,
            "confidence": confidence,
            "content_type": content_type,
            "size": stat.st_size,
            "modified": stat.st_mtime,
        }

    def classify_by_content(self, filepath: str) -> str:
        """تصنيف الملف بناءً على محتواه فقط"""
        if not self._magika:
            return "أخرى"
        try:
            result = self._magika.identify_path(filepath)
            if result and hasattr(result, "output"):
                return self._map_magika_type(result.output) or "أخرى"
        except Exception:
            pass
        return "أخرى"

    def batch_classify(self, directory: str) -> list:
        """تصنيف جميع الملفات في مجلد"""
        results = []
        dir_path = Path(directory)
        if not dir_path.is_dir():
            logger.error(f"المجلد غير موجود: {directory}")
            return results

        for item in dir_path.rglob("*"):
            if item.is_file() and not item.name.startswith("."):
                try:
                    result = self.classify_file(str(item))
                    if "error" not in result:
                        results.append(result)
                except Exception as e:
                    logger.debug(f"خطأ في تصنيف {item}: {e}")

        logger.info(f"تم تصنيف {len(results)} ملف في {directory}")
        return results

    def _map_magika_type(self, magika_type: str) -> Optional[str]:
        """تحويل نوع Magika إلى تصنيف IntelliFile"""
        mapping = {
            "pdf": "مستندات", "docx": "مستندات", "pptx": "مستندات",
            "xlsx": "مستندات", "csv": "مستندات", "txt": "مستندات",
            "html": "برمجة", "json": "برمجة", "xml": "برمجة",
            "python": "برمجة", "javascript": "برمجة", "php": "برمجة",
            "java": "برمجة", "c": "برمجة", "cpp": "برمجة",
            "sql": "برمجة", "shell": "برمجة",
            "jpg": "صور", "png": "صور", "gif": "صور",
            "bmp": "صور", "svg": "صور", "webp": "صور",
            "mp4": "فيديو", "avi": "فيديو", "mkv": "فيديو", "mov": "فيديو",
            "mp3": "صوت", "wav": "صوت", "flac": "صوت", "ogg": "صوت",
            "zip": "أرشيفات", "rar": "أرشيفات", "7z": "أرشيفات",
            "tar": "أرشيفات", "gzip": "أرشيفات",
            "exe": "أنظمة", "elf": "أنظمة", "dex": "أنظمة",
            "ttf": "خطوط", "otf": "خطوط", "woff": "خطوط", "woff2": "خطوط",
            "apk": "أنظمة", "iso": "أنظمة",
        }
        return mapping.get(magika_type.lower())

    def get_stats(self, results: list) -> dict:
        """إحصائيات التصنيف"""
        stats = {}
        for item in results:
            cat = item.get("category", "أخرى")
            stats[cat] = stats.get(cat, 0) + 1
        return stats


# Alias للتوافق مع الكود القديم
DocumentClassifier = SmartFileClassifier
