"""محرك التصنيف الدينامي - يكتشف هيكل مجلدات تلقائياً"""
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter

logger = logging.getLogger(__name__)


class EmergentCategoryEngine:
    """يكتشف ويقترح هيكل تصنيف ديناميكي"""

    def __init__(self):
        pass

    def analyze_directory(self, directory: str) -> Dict:
        """تحليل المجلد واقتراح هيكل جديد"""
        dir_path = Path(directory)
        if not dir_path.is_dir():
            return {"error": "المجلد غير موجود"}

        stats = self._collect_stats(dir_path)
        hierarchy = self.generate_hierarchy(stats)
        return {
            "directory": str(dir_path),
            "total_files": stats["total"],
            "total_size": stats["total_size"],
            "extension_distribution": stats["extensions"],
            "proposed_structure": hierarchy,
            "savings": self._estimate_savings(stats, hierarchy),
        }

    def generate_hierarchy(self, stats: Dict = None) -> Dict:
        """توليد هيكل تصنيف مقترح"""
        if stats is None:
            return {}

        extensions = stats.get("extension_distribution", {})

        # تجميع الامتدادات في مجموعات ذكية
        categories = self._cluster_extensions(extensions)

        hierarchy = {}
        for cat_name, exts in categories.items():
            hierarchy[cat_name] = {
                "files_count": sum(exts.values()),
                "extensions": list(exts.keys()),
                "total_size": sum(exts.values()),
            }

        # ترتيب حسب الأهمية
        sorted_cats = sorted(hierarchy.items(), key=lambda x: x[1]["files_count"], reverse=True)
        return {"categories": dict(sorted_cats)}

    def apply_structure(self, base_dir: str, structure: Dict) -> List[str]:
        """تطبيق الهيكل المقترح وإنشاء المجلدات"""
        created = []
        base = Path(base_dir)

        categories = structure.get("categories", {})
        for cat_name in categories:
            cat_dir = base / cat_name
            if not cat_dir.exists():
                cat_dir.mkdir(parents=True, exist_ok=True)
                created.append(str(cat_dir))
                logger.info(f"تم إنشاء: {cat_name}/")

        return created

    def suggest_reorganization(self, directory: str) -> Dict:
        """اقتراح إعادة تنظيم المجلد"""
        dir_path = Path(directory)
        result = self.analyze_directory(directory)

        moves = []
        for item in dir_path.rglob("*"):
            if not item.is_file() or item.name.startswith("."):
                continue
            ext = item.suffix.lower()
            # البحث عن التصنيف الأمثل
            for cat_name, cat_info in result["proposed_structure"]["categories"].items():
                if ext in cat_info["extensions"]:
                    current_parent = item.parent.name
                    proposed_parent = cat_name
                    if current_parent != proposed_parent:
                        moves.append({
                            "file": str(item),
                            "from": current_parent,
                            "to": proposed_parent,
                        })
                    break

        result["moves"] = moves
        return result

    def _collect_stats(self, dir_path: Path) -> Dict:
        """جمعرفة إحصائيات المجلد"""
        total_size = 0
        extensions = Counter()

        for item in dir_path.rglob("*"):
            if item.is_file() and not item.name.startswith("."):
                try:
                    size = item.stat().st_size
                    total_size += size
                    ext = item.suffix.lower() or "(بدون)"
                    extensions[ext] += 1
                except Exception:
                    continue

        return {
            "total": sum(extensions.values()),
            "total_size": total_size,
            "extensions": dict(extensions),
        }

    def _cluster_extensions(self, extensions: Dict) -> Dict:
        """تجميع الامتدادات في تصنيفات"""
        mapping = {
            "مستندات": [".pdf", ".doc", ".docx", ".odt", ".txt", ".rtf", ".md", ".epub",
                        ".xls", ".xlsx", ".csv", ".ods", ".ppt", ".pptx"],
            "صور": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico",
                    ".tiff", ".raw", ".psd", ".heic"],
            "فيديو": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp"],
            "صوت": [".mp3", ".wav", ".ogg", ".flac", ".aac", ".wma", ".m4a", ".opus"],
            "أرشيفات": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tar.gz"],
            "برمجة": [".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".yaml", ".yml",
                      ".sql", ".java", ".cpp", ".c", ".h", ".go", ".rs", ".rb", ".php", ".sh",
                      ".jsx", ".tsx", ".vue", ".swift", ".kt", ".dart"],
            "أنظمة": [".exe", ".msi", ".deb", ".pkg", ".rpm", ".AppImage", ".iso", ".dmg",
                      ".img", ".dll", ".so", ".ini", ".cfg", ".conf", ".log", ".sys", ".tmp"],
            "خطوط": [".ttf", ".otf", ".woff", ".woff2", ".eot"],
        }

        clusters = {}
        for ext, count in extensions.items():
            found = False
            for cat, exts in mapping.items():
                if ext in exts:
                    if cat not in clusters:
                        clusters[cat] = {}
                    clusters[cat][ext] = count
                    found = True
                    break
            if not found:
                if "أخرى" not in clusters:
                    clusters["أخرى"] = {}
                clusters["أخرى"][ext] = count

        return clusters

    def _estimate_savings(self, stats: Dict, hierarchy: Dict) -> str:
        """تقدير وفور المساحة من إعادة التنظيم"""
        return "يمكن توفير مساحة من خلال دمج الملفات المكررة وتنظيمها."
