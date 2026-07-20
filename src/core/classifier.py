"""مصنف الملفات الذكي - يجمع بين القواعد والمحرك الذكي"""
import os
import logging
import tempfile
from pathlib import Path
from typing import Optional
from .config import Config, CATEGORIES

logger = logging.getLogger(__name__)


class SmartFileClassifier:
    """مصنف ذكي يجمع بين التصنيف بالامتداد والمحتوى"""

    # خريطة الكلمات المفتاحية الطبية العربية-الإنجليزية
    _MEDICAL_KEYWORDS = {
        "قلب": "cardiology", "قلبية": "cardiology", "cardiac": "cardiology",
        "عظام": "orthopedic", "orthopedic": "orthopedic", "كسر": "orthopedic",
        "أعصاب": "neurology", "عصبي": "neurology", "neurology": "neurology",
        "جراحة": "general_surgery", "surgery": "general_surgery",
        "أشعة": "radiology", "radiology": "radiology",
        "أدوية": "pharmacology", "دواء": "pharmacology", "pharmacology": "pharmacology",
        "تشخيص": "pathology", "pathology": "pathology", "مختبر": "pathology",
        "بحث": "research", "research": "research",
    }

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self._magika = None
        self._medical_classifier = None
        self._scanner_fixer = None
        self._init_magika()

    def _init_medical_classifier(self):
        """محاولة استيراد MedicalClassifier من omni-medical-suite"""
        if self._medical_classifier is not None:
            return
        try:
            from packages.core.classifier import MedicalClassifier
            self._medical_classifier = MedicalClassifier()
            logger.info("تم تحميل MedicalClassifier من packages.core")
            return
        except ImportError:
            pass
        try:
            from hf_space.packages.core.classifier import MedicalClassifier
            self._medical_classifier = MedicalClassifier()
            logger.info("تم تحميل MedicalClassifier من hf_space.packages.core")
            return
        except ImportError:
            logger.debug("MedicalClassifier غير متاح — سيتم استخدام تصنيف الكلمات المفتاحية")
            self._medical_classifier = None

    def _init_scanner_fixer(self):
        """محاولة استيراد scanner_fixer من omni-medical-suite"""
        if self._scanner_fixer is not None:
            return
        try:
            from packages.scanner_fixer import fix_scan, enhance_for_ocr
            self._scanner_fixer = {"fix_scan": fix_scan, "enhance_for_ocr": enhance_for_ocr}
            logger.info("تم تحميل scanner_fixer من packages.scanner_fixer")
            return
        except ImportError:
            pass
        try:
            from scanner_fixer import fix_scan, enhance_for_ocr
            self._scanner_fixer = {"fix_scan": fix_scan, "enhance_for_ocr": enhance_for_ocr}
            logger.info("تم تحميل scanner_fixer (standalone)")
            return
        except ImportError:
            logger.debug("scanner_fixer غير متاح")
            self._scanner_fixer = None

    def classify_medical(self, text: str) -> dict:
        """تصنيف طبي للنص باستخدام MedicalClassifier أو الكلمات المفتاحية"""
        self._init_medical_classifier()
        if self._medical_classifier is not None:
            try:
                result = self._medical_classifier.classify(text)
                return {
                    "category": result.get("category", "unknown"),
                    "confidence": result.get("confidence", 0.0),
                    "all_scores": result.get("all_scores", {}),
                    "source": "medical_classifier",
                }
            except Exception as e:
                logger.debug(f"خطأ في MedicalClassifier: {e}")

        # تصنيف بالكلمات المفتاحية كاحتياطي
        if text:
            text_lower = text.lower()
            best_category = "unknown"
            best_keyword = None
            for keyword, category in self._MEDICAL_KEYWORDS.items():
                if keyword in text or keyword.lower() in text_lower:
                    best_category = category
                    best_keyword = keyword
                    break
            if best_keyword:
                return {
                    "category": best_category,
                    "confidence": 0.6,
                    "all_scores": {best_category: 0.6},
                    "source": "keyword_fallback",
                }

        return {"category": "unknown", "confidence": 0.0, "source": "keyword_fallback"}

    def classify_file_medical(self, filepath: str) -> dict:
        """تصنيف ملف طبي — يجمع بين تصنيف الملف وتصنيف المحتوى الطبي"""
        file_info = self.classify_file(filepath)
        if "error" in file_info:
            return file_info

        # استخراج النص من الملف
        text = self._extract_text_for_medical(filepath)

        # تصنيف طبي
        medical_info = self.classify_medical(text)

        # دمج النتائج
        return {**file_info, **medical_info}

    def _extract_text_for_medical(self, filepath: str) -> str:
        """استخراج نص من ملف للتصنيف الطبي"""
        path = Path(filepath)
        ext = path.suffix.lower()

        try:
            if ext in (".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml",
                        ".py", ".js", ".ts", ".html", ".css", ".sh", ".bat", ".log"):
                return path.read_text(encoding="utf-8", errors="ignore")[:5000]
            elif ext == ".pdf":
                try:
                    import pdfplumber
                    with pdfplumber.open(filepath) as pdf:
                        return "\n".join(p.extract_text() or "" for p in pdf.pages)[:5000]
                except ImportError:
                    try:
                        import fitz
                        doc = fitz.open(filepath)
                        text = "\n".join(page.get_text() for page in doc)
                        doc.close()
                        return text[:5000]
                    except ImportError:
                        return ""
            elif ext in (".docx",):
                try:
                    from docx import Document
                    doc = Document(filepath)
                    return "\n".join(p.text for p in doc.paragraphs)[:5000]
                except Exception:
                    return ""
            elif ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"):
                # للصور: نحاول OCR بسيط
                try:
                    import pytesseract
                    from PIL import Image
                    img = Image.open(filepath)
                    return pytesseract.image_to_string(img, lang="ara+eng")[:5000]
                except Exception:
                    return path.name
        except Exception as e:
            logger.debug(f"لا يمكن استخراج النص من {filepath}: {e}")

        return path.name

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
                    # تحويل نوع Magika إلى تصنيفنا
                    mapped = self._map_magika_type(magika_type)
                    if mapped and mapped != "أخرى":
                        category = mapped
                        confidence = 95.0
                    elif extension and self.config.get_category(extension) != "أخرى":
                        confidence = 75.0  # content + extension agree it's not "other"
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
