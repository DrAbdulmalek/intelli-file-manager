# -*- coding: utf-8 -*-
"""المخططات - تعريف هياكل البيانات للملفات

يحتوي هذا الملف على الفئات (classes) التي تمثل البيانات الوصفية للملفات
وسجلات الملفات الكاملة المخزنة في قاعدة البيانات المتجهية.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


class FileCategory(str, Enum):
    """تصنيفات الملفات المدعومة في النظام

    كل تصنيف يحتوي على قيمة عربية تُستخدم في واجهة المستخدم
    وقيمة إنجليزية تُستخدم داخلياً في النظام.
    """

    DOCUMENTS = "مستندات"
    IMAGES = "صور"
    VIDEOS = "فيديو"
    AUDIO = "صوت"
    ARCHIVES = "أرشيفات"
    CODE = "برمجة"
    SYSTEM = "أنظمة"
    FONTS = "خطوط"
    OTHER = "أخرى"

    @classmethod
    def from_extension(cls, extension: str) -> "FileCategory":
        """تحديد تصنيف الملف بناءً على امتداده

        Args:
            extension: امتداد الملف (مثل 'pdf', 'jpg', 'py')

        Returns:
            FileCategory: التصنيف المناسب للملف
        """
        ext = extension.lower().lstrip(".")

        # رسم خرائط الامتدادات إلى التصنيفات
        category_map: Dict[str, "FileCategory"] = {
            # مستندات
            "pdf": cls.DOCUMENTS, "doc": cls.DOCUMENTS, "docx": cls.DOCUMENTS,
            "txt": cls.DOCUMENTS, "rtf": cls.DOCUMENTS, "odt": cls.DOCUMENTS,
            "xls": cls.DOCUMENTS, "xlsx": cls.DOCUMENTS, "csv": cls.DOCUMENTS,
            "ppt": cls.DOCUMENTS, "pptx": cls.DOCUMENTS, "md": cls.DOCUMENTS,
            "epub": cls.DOCUMENTS, "tex": cls.DOCUMENTS, "json": cls.DOCUMENTS,
            "xml": cls.DOCUMENTS, "yaml": cls.DOCUMENTS, "yml": cls.DOCUMENTS,
            "ini": cls.DOCUMENTS, "cfg": cls.DOCUMENTS, "toml": cls.DOCUMENTS,
            "log": cls.DOCUMENTS,
            # صور
            "jpg": cls.IMAGES, "jpeg": cls.IMAGES, "png": cls.IMAGES,
            "gif": cls.IMAGES, "bmp": cls.IMAGES, "svg": cls.IMAGES,
            "webp": cls.IMAGES, "ico": cls.IMAGES, "tiff": cls.IMAGES,
            "tif": cls.IMAGES, "raw": cls.IMAGES, "psd": cls.IMAGES,
            "heic": cls.IMAGES, "avif": cls.IMAGES,
            # فيديو
            "mp4": cls.VIDEOS, "avi": cls.VIDEOS, "mkv": cls.VIDEOS,
            "mov": cls.VIDEOS, "wmv": cls.VIDEOS, "flv": cls.VIDEOS,
            "webm": cls.VIDEOS, "m4v": cls.VIDEOS, "mpg": cls.VIDEOS,
            "mpeg": cls.VIDEOS, "3gp": cls.VIDEOS,
            # صوت
            "mp3": cls.AUDIO, "wav": cls.AUDIO, "flac": cls.AUDIO,
            "aac": cls.AUDIO, "ogg": cls.AUDIO, "wma": cls.AUDIO,
            "m4a": cls.AUDIO, "opus": cls.AUDIO,
            # أرشيفات
            "zip": cls.ARCHIVES, "rar": cls.ARCHIVES, "7z": cls.ARCHIVES,
            "tar": cls.ARCHIVES, "gz": cls.ARCHIVES, "bz2": cls.ARCHIVES,
            "xz": cls.ARCHIVES, "iso": cls.ARCHIVES, "dmg": cls.ARCHIVES,
            # برمجة
            "py": cls.CODE, "js": cls.CODE, "ts": cls.CODE, "jsx": cls.CODE,
            "tsx": cls.CODE, "java": cls.CODE, "c": cls.CODE, "cpp": cls.CODE,
            "h": cls.CODE, "hpp": cls.CODE, "cs": cls.CODE, "go": cls.CODE,
            "rs": cls.CODE, "rb": cls.CODE, "php": cls.CODE, "swift": cls.CODE,
            "kt": cls.CODE, "scala": cls.CODE, "r": cls.CODE, "lua": cls.CODE,
            "sh": cls.CODE, "bash": cls.CODE, "zsh": cls.CODE, "ps1": cls.CODE,
            "sql": cls.CODE, "html": cls.CODE, "css": cls.CODE, "scss": cls.CODE,
            "less": cls.CODE, "vue": cls.CODE, "svelte": cls.CODE,
            # أنظمة
            "exe": cls.SYSTEM, "dll": cls.SYSTEM, "sys": cls.SYSTEM,
            "bat": cls.SYSTEM, "cmd": cls.SYSTEM, "msi": cls.SYSTEM,
            "so": cls.SYSTEM, "dylib": cls.SYSTEM, "bin": cls.SYSTEM,
            "deb": cls.SYSTEM, "rpm": cls.SYSTEM, "apk": cls.SYSTEM,
            # خطوط
            "ttf": cls.FONTS, "otf": cls.FONTS, "woff": cls.FONTS,
            "woff2": cls.FONTS, "eot": cls.FONTS,
        }

        return category_map.get(ext, cls.OTHER)


@dataclass
class FileMetadata:
    """بيانات وصفية للملف

    تحتوي على جميع المعلومات المتعلقة بالملف بما في ذلك:
    - المعلومات الأساسية (الاسم، المسار، الحجم)
    - معلومات التصنيف (الفئة، الثقة، العلامات)
    - معلومات التعريف (الهاش، أنواع المحتوى)
    - معلومات الوقت (الإنشاء، التعديل، التصنيف)

    Attributes:
        file_name: اسم الملف
        file_path: المسار الكامل للملف
        file_size: حجم الملف بالبايت
        extension: امتداد الملف
        mime_type: نوع MIME للملف
        category: تصنيف الملف
        confidence: مستوى الثقة في التصنيف (0.0 - 1.0)
        is_protected: هل الملف محمي (للقراءة فقط)
        is_duplicate: هل الملف مكرر
        sha256_hash: تجميعة SHA-256 للملف
        created_at: تاريخ إنشاء الملف
        modified_at: تاريخ آخر تعديل
        classified_at: تاريخ التصنيف
        tags: قائمة العلامات المرتبطة بالملف
        parent_dir: المسار الأب للملف
        content_type: نوع المحتوى
    """

    file_name: str = ""
    file_path: str = ""
    file_size: int = 0
    extension: str = ""
    mime_type: str = "unknown"
    category: str = FileCategory.OTHER.value
    confidence: float = 0.0
    is_protected: bool = False
    is_duplicate: bool = False
    sha256_hash: str = ""
    created_at: str = ""
    modified_at: str = ""
    classified_at: str = ""
    tags: List[str] = field(default_factory=list)
    parent_dir: str = ""
    content_type: str = "unknown"
    # ميتاداتا موسّعة حسب نوع الوسيط (PR-03):
    #   - صور: {width, height, format, mode, exif, captured_at, camera_make, ...}
    #   - صوت/فيديو: {duration_seconds, bit_rate, format_name, video, audio, tags, ...}
    # فارغة {} للملفات النصية والمستندات (لا ميتاداتا موسّعة لها).
    extra_metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        """تهيئة تلقائية بعد إنشاء الكائن

        - تعيين تاريخ الإنشاء إذا لم يُحدد
        - تعيين تاريخ التصنيف إذا لم يُحدد
        - استخراج الامتداد من اسم الملف تلقائياً
        - استخراج المسار الأب من المسار الكامل
        """
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.classified_at:
            self.classified_at = datetime.now().isoformat()
        if self.file_path and not self.parent_dir:
            import os
            self.parent_dir = os.path.dirname(self.file_path)
        if self.file_name and not self.extension:
            # استخراج الامتداد من اسم الملف
            if "." in self.file_name:
                self.extension = self.file_name.rsplit(".", 1)[-1].lower()

    def to_dict(self) -> dict:
        """تحويل البيانات الوصفية إلى قاموس

        Returns:
            dict: تمثيل القاموس للبيانات الوصفية
        """
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "FileMetadata":
        """إنشاء كائن FileMetadata من قاموس

        Args:
            data: القاموس الذي يحتوي على البيانات الوصفية

        Returns:
            FileMetadata: كائن البيانات الوصفية الجديد
        """
        # تصفية الحقول غير الموجودة في تعريف البيانات
        valid_fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid_fields)

    @property
    def file_size_human(self) -> str:
        """إرجاع حجم الملف بصيغة مقروءة للإنسان

        Returns:
            str: الحجم بصيغة مقروءة (مثل '1.5 MB')
        """
        if self.file_size == 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(self.file_size)
        unit_index = 0

        while size >= 1024.0 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1

        return f"{size:.2f} {units[unit_index]}"

    @property
    def category_enum(self) -> FileCategory:
        """إرجاع كائن FileCategory المقابل للتصنيف النصي

        Returns:
            FileCategory: كائن التصنيف
        """
        for cat in FileCategory:
            if cat.value == self.category:
                return cat
        return FileCategory.OTHER

    def matches_query(self, query: str) -> bool:
        """فحص تطابق الملف مع استعلام بحث نصي

        يبحث في الاسم والامتداد والعلامات والتصنيف والمسار الأب.

        Args:
            query: نص الاستعلام

        Returns:
            bool: True إذا تطابق الملف مع الاستعلام
        """
        if not query:
            return True

        query_lower = query.lower()
        searchable_fields = [
            self.file_name.lower(),
            self.extension.lower(),
            self.category.lower(),
            self.parent_dir.lower(),
            self.mime_type.lower(),
            self.content_type.lower(),
        ]
        searchable_fields.extend(tag.lower() for tag in self.tags)

        return any(query_lower in field for field in searchable_fields)

    def merge(self, other: "FileMetadata") -> "FileMetadata":
        """دمج بيانات وصفية أخرى مع البيانات الحالية

        البيانات الجديدة تتجاوز البيانات الحالية فقط إذا كانت غير فارغة.

        Args:
            other: البيانات الوصفية الأخرى للدمج

        Returns:
            FileMetadata: البيانات المدمجة
        """
        merged = self.to_dict()
        for key, value in other.to_dict().items():
            # تخطي الحقول الفارغة أو الصفرية
            if value is None:
                continue
            if isinstance(value, str) and not value:
                continue
            if isinstance(value, (int, float)) and value == 0:
                continue
            if isinstance(value, list) and not value:
                continue
            if isinstance(value, dict) and not value:
                continue
            merged[key] = value
        return FileMetadata.from_dict(merged)


@dataclass
class FileRecord:
    """سجل ملف كامل في قاعدة البيانات

    يمثل سجل ملف واحد في قاعدة البيانات المتجهية ويجمع بين:
    - المعرف الفريد
    - البيانات الوصفية
    - التضمين (embedding) للبحث الدلالي
    - النص المستخرج من الملف

    Attributes:
        id: المعرف الفريد للسجل
        metadata: البيانات الوصفية للملف
        embedding: متجه التضمين للبحث الدلالي
        document_text: النص المستخرج من الملف
    """

    id: str = ""
    metadata: FileMetadata = field(default_factory=FileMetadata)
    embedding: Optional[List[float]] = None
    document_text: str = ""

    def __post_init__(self):
        """تهيئة تلقائية بعد إنشاء السجل

        - تعيين المعرف من تجميعة SHA-256 إذا لم يُحدد
        - التأكد من أن البيانات الوصفية هي كائن FileMetadata
        """
        if not self.id and self.metadata.sha256_hash:
            self.id = f"file:{self.metadata.sha256_hash}"
        if not self.id:
            import uuid
            self.id = f"file:{uuid.uuid4().hex}"

    def to_dict(self) -> dict:
        """تحويل السجل إلى قاموس

        Returns:
            dict: تمثيل القاموس للسجل
        """
        return {
            "id": self.id,
            "metadata": self.metadata.to_dict(),
            "embedding": self.embedding,
            "document_text": self.document_text,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileRecord":
        """إنشاء سجل ملف من قاموس

        Args:
            data: القاموس الذي يحتوي على بيانات السجل

        Returns:
            FileRecord: سجل الملف الجديد
        """
        metadata = data.get("metadata", {})
        if isinstance(metadata, dict):
            metadata = FileMetadata.from_dict(metadata)
        elif not isinstance(metadata, FileMetadata):
            metadata = FileMetadata()

        return cls(
            id=data.get("id", ""),
            metadata=metadata,
            embedding=data.get("embedding"),
            document_text=data.get("document_text", ""),
        )

    @classmethod
    def from_metadata(
        cls,
        metadata: FileMetadata,
        embedding: Optional[List[float]] = None,
        document_text: str = "",
    ) -> "FileRecord":
        """إنشاء سجل ملف من بيانات وصفية

        Args:
            metadata: البيانات الوصفية للملف
            embedding: متجه التضمين (اختياري)
            document_text: النص المستخرج (اختياري)

        Returns:
            FileRecord: سجل الملف الجديد
        """
        return cls(
            metadata=metadata,
            embedding=embedding,
            document_text=document_text,
        )

    @property
    def has_embedding(self) -> bool:
        """هل يحتوي السجل على تضمين صالح؟

        Returns:
            bool: True إذا كان التضمين موجوداً وغير فارغ
        """
        return self.embedding is not None and len(self.embedding) > 0

    @property
    def display_name(self) -> str:
        """الاسم المعروض للملف

        Returns:
            str: اسم الملف أو 'ملف غير معروف' إذا كان الاسم فارغاً
        """
        return self.metadata.file_name or "ملف غير معروف"

    def summary(self) -> str:
        """ملخص مختصر للسجل

        Returns:
            str: نص ملخص يتضمن الاسم والحجم والتصنيف
        """
        parts = [
            f"📄 {self.display_name}",
            f"📂 {self.metadata.parent_dir or 'غير محدد'}",
            f"📦 {self.metadata.file_size_human}",
            f"🏷️ {self.metadata.category}",
        ]
        if self.metadata.confidence > 0:
            parts.append(f"📊 ثقة: {self.metadata.confidence:.1%}")
        if self.metadata.tags:
            parts.append(f"🔖 {', '.join(self.metadata.tags)}")
        return "\n".join(parts)
