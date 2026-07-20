"""إعدادات تطبيق IntelliFile"""
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict


CATEGORIES = [
    "مستندات", "صور", "فيديو", "صوت",
    "أرشيفات", "برمجة", "أنظمة", "خطوط", "أخرى"
]

EXTENSION_MAP = {
    # مستندات
    ".pdf": "مستندات", ".doc": "مستندات", ".docx": "مستندات",
    ".odt": "مستندات", ".txt": "مستندات", ".rtf": "مستندات",
    ".md": "مستندات", ".tex": "مستندات", ".epub": "مستندات",
    ".xls": "مستندات", ".xlsx": "مستندات", ".csv": "مستندات",
    ".ods": "مستندات", ".ppt": "مستندات", ".pptx": "مستندات",
    # صور
    ".jpg": "صور", ".jpeg": "صور", ".png": "صور", ".gif": "صور",
    ".bmp": "صور", ".svg": "صور", ".webp": "صور", ".ico": "صور",
    ".tiff": "صور", ".raw": "صور", ".psd": "صور", ".heic": "صور",
    # فيديو
    ".mp4": "فيديو", ".avi": "فيديو", ".mkv": "فيديو", ".mov": "فيديو",
    ".wmv": "فيديو", ".flv": "فيديو", ".webm": "فيديو", ".m4v": "فيديو",
    ".3gp": "فيديو",
    # صوت
    ".mp3": "صوت", ".wav": "صوت", ".ogg": "صوت", ".flac": "صوت",
    ".aac": "صوت", ".wma": "صوت", ".m4a": "صوت", ".opus": "صوت",
    # أرشيفات
    ".zip": "أرشيفات", ".rar": "أرشيفات", ".7z": "أرشيفات",
    ".tar": "أرشيفات", ".gz": "أرشيفات", ".bz2": "أرشيفات",
    ".xz": "أرشيفات", ".tar.gz": "أرشيفات", ".tgz": "أرشيفات",
    # برمجة
    ".py": "برمجة", ".js": "برمجة", ".ts": "برمجة", ".html": "برمجة",
    ".css": "برمجة", ".json": "برمجة", ".xml": "برمجة", ".yaml": "برمجة",
    ".yml": "برمجة", ".sql": "برمجة", ".java": "برمجة", ".cpp": "برمجة",
    ".c": "برمجة", ".h": "برمجة", ".go": "برمجة", ".rs": "برمجة",
    ".rb": "برمجة", ".php": "برمجة", ".sh": "برمجة", ".bat": "برمجة",
    ".jsx": "برمجة", ".tsx": "برمجة", ".vue": "برمجة", ".swift": "برمجة",
    ".kt": "برمجة", ".dart": "برمجة",
    # أنظمة
    ".exe": "أنظمة", ".msi": "أنظمة", ".deb": "أنظمة", ".pkg": "أنظمة",
    ".rpm": "أنظمة", ".AppImage": "أنظمة", ".iso": "أنظمة",
    ".dmg": "أنظمة", ".img": "أنظمة", ".dll": "أنظمة",
    ".so": "أنظمة", ".ini": "أنظمة", ".cfg": "أنظمة", ".conf": "أنظمة",
    ".log": "أنظمة", ".sys": "أنظمة", ".tmp": "أنظمة",
    # خطوط
    ".ttf": "خطوط", ".otf": "خطوط", ".woff": "خطوط",
    ".woff2": "خطوط", ".eot": "خطوط",
}


@dataclass
class Config:
    """إعدادات التطبيق الرئيسية"""
    categories: list = field(default_factory=lambda: list(CATEGORIES))
    extension_map: dict = field(default_factory=lambda: dict(EXTENSION_MAP))
    ai_model: str = "llama3.2"  # نموذج الذكاء الاصطناعي الموحد
    ollama_url: str = "http://localhost:11434"
    database_path: str = str(Path.home() / ".intellifile")
    vector_db_path: str = str(Path.home() / ".intellifile" / "vectors")
    working_dir: str = str(Path.cwd())
    language: str = "ar"
    dark_mode: bool = True
    auto_classify: bool = True
    duplicate_detection: bool = True
    file_protection: bool = True
    voice_enabled: bool = False
    watch_directories: list = field(default_factory=list)
    custom_categories: list = field(default_factory=list)

    def save(self, filepath: str = None):
        """حفظ الإعدادات في ملف JSON"""
        if filepath is None:
            filepath = str(Path(self.database_path) / "config.json")
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, filepath: str = None) -> "Config":
        """تحميل الإعدادات من ملف JSON"""
        if filepath is None:
            filepath = str(Path.home() / ".intellifile" / "config.json")
        path = Path(filepath)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Merge with defaults
            default = cls()
            for key, value in data.items():
                if hasattr(default, key):
                    setattr(default, key, value)
            return default
        return cls()

    def get_category(self, extension: str) -> str:
        """الحصول على تصنيف امتداد الملف"""
        return self.extension_map.get(extension.lower(), "أخرى")

    def add_custom_category(self, name: str, extensions: list = None):
        """إضافة تصنيف مخصص"""
        if name not in self.categories:
            self.categories.append(name)
            self.custom_categories.append(name)
        if extensions:
            for ext in extensions:
                self.extension_map[ext.lower()] = name
