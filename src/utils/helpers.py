"""وظائف مساعدة لتطبيق IntelliFile"""
import os
import hashlib
from pathlib import Path


def format_size(size_bytes: int) -> str:
    """تنسيق حجم الملف بالبايت/كيلوبايت/ميغابايت/غيغابايت"""
    if size_bytes == 0:
        return "0 بايت"
    units = ["بايت", "كيلوبايت", "ميغابايت", "غيغابايت", "تيرابايت"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.1f} {units[i]}"


def get_file_icon(extension: str) -> str:
    """إرجاع أيقونة مناسبة لامتداد الملف"""
    icons = {
        ".pdf": "📄", ".doc": "📝", ".docx": "📝", ".odt": "📝",
        ".txt": "📃", ".rtf": "📝", ".md": "📃",
        ".xls": "📊", ".xlsx": "📊", ".csv": "📊", ".ods": "📊",
        ".ppt": "📊", ".pptx": "📊", ".odp": "📊",
        ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️", ".gif": "🖼️",
        ".bmp": "🖼️", ".svg": "🖼️", ".webp": "🖼️", ".ico": "🖼️",
        ".mp4": "🎬", ".avi": "🎬", ".mkv": "🎬", ".mov": "🎬",
        ".wmv": "🎬", ".flv": "🎬", ".webm": "🎬",
        ".mp3": "🎵", ".wav": "🎵", ".ogg": "🎵", ".flac": "🎵",
        ".aac": "🎵", ".wma": "🎵", ".m4a": "🎵",
        ".zip": "📦", ".rar": "📦", ".7z": "📦", ".tar": "📦",
        ".gz": "📦", ".bz2": "📦", ".xz": "📦",
        ".py": "🐍", ".js": "⚡", ".ts": "⚡", ".html": "🌐",
        ".css": "🎨", ".json": "📋", ".xml": "📋", ".yaml": "📋",
        ".yml": "📋", ".sql": "🗃️", ".db": "🗃️", ".sqlite": "🗃️",
        ".exe": "⚙️", ".msi": "⚙️", ".deb": "📦", ".pkg": "📦",
        ".ttf": "🔤", ".otf": "🔤", ".woff": "🔤", ".woff2": "🔤",
        ".ini": "⚙️", ".cfg": "⚙️", ".conf": "⚙️", ".log": "📋",
        ".iso": "💿", ".dmg": "💿", ".img": "💿",
    }
    return icons.get(extension.lower(), "📁")


def compute_file_hash(filepath: str, algorithm: str = "sha256") -> str:
    """حساب hash للملف للكشف عن المكررات"""
    h = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def is_path_safe(base_path: str, target_path: str) -> bool:
    """التحقق من أن المسار آمن ولا يحتوي على path traversal"""
    try:
        base = Path(base_path).resolve()
        target = Path(target_path).resolve()
        return str(target).startswith(str(base))
    except (ValueError, OSError):
        return False


def sanitize_filename(filename: str) -> str:
    """تنظيف اسم الملف من الأحرف الخطرة"""
    dangerous_chars = '<>:"/\\|?*\0'
    for char in dangerous_chars:
        filename = filename.replace(char, '_')
    return filename.strip('. ')
