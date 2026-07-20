"""نظام الوسوم الذكي (Smart Tagging) — TagSpaces-style

Features:
  - Auto-tag files based on content and metadata
  - Tag categories: medical, document-type, language, priority, status
  - Sidecar .json metadata files (TagSpaces compatible)
  - Hierarchical tags (e.g., medical/cardiology/diagnosis)
  - Batch tagging and tag management
  - Arabic + English tag support
  - Integration with classifier and medical NER
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Tag:
    """وسم واحد"""
    name: str
    category: str = "general"  # medical, document-type, language, priority, status
    confidence: float = 1.0
    source: str = "auto"  # auto, manual, ner, classifier

    @property
    def is_hierarchical(self) -> bool:
        return "/" in self.name

    @property
    def levels(self) -> list[str]:
        return self.name.split("/")

    def to_dict(self) -> dict:
        return {"name": self.name, "category": self.category,
                "confidence": self.confidence, "source": self.source}


@dataclass
class FileTags:
    """وسوم ملف واحد — متوافق مع TagSpaces"""
    filepath: str
    tags: list[Tag] = field(default_factory=list)
    last_updated: str = ""
    auto_tags: list[Tag] = field(default_factory=list)
    manual_tags: list[Tag] = field(default_factory=list)

    @property
    def all_tag_names(self) -> list[str]:
        return [t.name for t in self.tags]

    def add_tag(self, tag: Tag):
        """إضافة وسم (بدون تكرار)"""
        if tag.name not in self.all_tag_names:
            self.tags.append(tag)
            if tag.source == "manual":
                self.manual_tags.append(tag)
            else:
                self.auto_tags.append(tag)

    def remove_tag(self, tag_name: str) -> bool:
        """حذف وسم بالاسم"""
        before = len(self.tags)
        self.tags = [t for t in self.tags if t.name != tag_name]
        self.auto_tags = [t for t in self.auto_tags if t.name != tag_name]
        self.manual_tags = [t for t in self.manual_tags if t.name != tag_name]
        return len(self.tags) < before

    def to_dict(self) -> dict:
        return {
            "filepath": self.filepath,
            "tags": [t.to_dict() for t in self.tags],
            "lastUpdated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileTags":
        ft = cls(filepath=data.get("filepath", ""))
        for td in data.get("tags", []):
            ft.add_tag(Tag(
                name=td["name"],
                category=td.get("category", "general"),
                confidence=td.get("confidence", 1.0),
                source=td.get("source", "auto"),
            ))
        ft.last_updated = data.get("lastUpdated", "")
        return ft


# ---------------------------------------------------------------------------
# Auto-tagging rules
# ---------------------------------------------------------------------------

_EXTENSION_TAGS: dict[str, list[Tag]] = {
    ".pdf": [Tag("document/pdf", "document-type")],
    ".docx": [Tag("document/word", "document-type")],
    ".xlsx": [Tag("document/spreadsheet", "document-type")],
    ".jpg": [Tag("image/photograph", "document-type")],
    ".png": [Tag("image/screenshot", "document-type")],
    ".dicom": [Tag("medical/imaging/dicom", "medical")],
    ".dcm": [Tag("medical/imaging/dicom", "medical")],
    ".mp3": [Tag("audio/recording", "document-type")],
    ".wav": [Tag("audio/recording", "document-type")],
    ".mp4": [Tag("video/recording", "document-type")],
}

_CONTENT_KEYWORDS: dict[str, list[Tag]] = {
    # Arabic medical keywords → tags
    "مريض": [Tag("medical/patient-record", "medical", 0.7, "auto")],
    "تشخيص": [Tag("medical/diagnosis", "medical", 0.8, "auto")],
    "أشعة": [Tag("medical/imaging", "medical", 0.8, "auto")],
    "صورة أشعة": [Tag("medical/imaging/xray", "medical", 0.9, "auto")],
    "رنين مغناطيسي": [Tag("medical/imaging/mri", "medical", 0.9, "auto")],
    "تخطيط قلب": [Tag("medical/cardiology/ecg", "medical", 0.9, "auto")],
    "قلب": [Tag("medical/cardiology", "medical", 0.6, "auto")],
    "عظام": [Tag("medical/orthopedics", "medical", 0.7, "auto")],
    "أعصاب": [Tag("medical/neurology", "medical", 0.7, "auto")],
    "أطفال": [Tag("medical/pediatrics", "medical", 0.7, "auto")],
    "أدوية": [Tag("medical/pharmacology", "medical", 0.8, "auto")],
    "وصفة": [Tag("medical/prescription", "medical", 0.8, "auto")],
    "جراحة": [Tag("medical/surgery", "medical", 0.7, "auto")],
    "تقرير طبي": [Tag("medical/report", "medical", 0.9, "auto")],
    "نتيجة تحليل": [Tag("medical/lab-result", "medical", 0.9, "auto")],
    # English medical keywords
    "patient": [Tag("medical/patient-record", "medical", 0.7, "auto")],
    "diagnosis": [Tag("medical/diagnosis", "medical", 0.8, "auto")],
    "prescription": [Tag("medical/prescription", "medical", 0.8, "auto")],
    "x-ray": [Tag("medical/imaging/xray", "medical", 0.9, "auto")],
    "mri": [Tag("medical/imaging/mri", "medical", 0.9, "auto")],
    "ecg": [Tag("medical/cardiology/ecg", "medical", 0.9, "auto")],
    "cardiology": [Tag("medical/cardiology", "medical", 0.7, "auto")],
    "orthopedic": [Tag("medical/orthopedics", "medical", 0.7, "auto")],
    "surgery": [Tag("medical/surgery", "medical", 0.7, "auto")],
    "lab result": [Tag("medical/lab-result", "medical", 0.9, "auto")],
}

_FILENAME_PATTERNS: list[tuple[re.Pattern, list[Tag]]] = []
import re
_FILENAME_PATTERNS = [
    (re.compile(r"(?:تقرير|report)", re.I), [Tag("document/report", "document-type")]),
    (re.compile(r"(?:فاتورة|invoice)", re.I), [Tag("document/invoice", "document-type")]),
    (re.compile(r"(?:شهادة|certificate)", re.I), [Tag("document/certificate", "document-type")]),
    (re.compile(r"(?:إيصال|receipt)", re.I), [Tag("document/receipt", "document-type")]),
    (re.compile(r"(?:ميزان|balance)", re.I), [Tag("financial/balance-sheet", "financial")]),
]


class SmartTagger:
    """نظام الوسوم الذكي المتكامل.

    TagSpaces-compatible sidecar metadata:
      - Saves .json next to the file (e.g., report.pdf.json)
      - Compatible with TagSpaces tag format

    Auto-tagging sources:
      1. File extension → document-type tags
      2. Filename patterns → document-type tags
      3. Content keywords → medical tags
      4. Medical NER → medical entity tags
      5. Classifier → category tags
    """

    def __init__(self, tags_dir: str | None = None):
        self._tags_dir = Path(tags_dir) if tags_dir else None
        self._cache: dict[str, FileTags] = {}
        self._ner = None
        self._classifier = None

    def _init_ner(self):
        """Lazy-load ArabicMedicalNER."""
        if self._ner is not None:
            return
        try:
            from .medical_ner import ArabicMedicalNER
            self._ner = ArabicMedicalNER()
            logger.info("تم تحميل ArabicMedicalNER للوسوم الطبية")
        except Exception as exc:
            logger.debug(f"ArabicMedicalNER غير متاح: {exc}")

    def _init_classifier(self):
        """Lazy-load SmartFileClassifier."""
        if self._classifier is not None:
            return
        try:
            from .classifier import SmartFileClassifier
            self._classifier = SmartFileClassifier()
            logger.info("تم تحميل SmartFileClassifier للوسوم")
        except Exception as exc:
            logger.debug(f"SmartFileClassifier غير متاح: {exc}")

    def auto_tag(self, filepath: str, content: str = "") -> FileTags:
        """Auto-tag a file using all available sources.

        Args:
            filepath: Path to the file
            content: Optional text content (extracted if not provided)

        Returns:
            FileTags with all auto-generated tags
        """
        path = Path(filepath)
        ft = FileTags(filepath=str(path))

        # 1. Extension-based tags
        ext = path.suffix.lower()
        for tag in _EXTENSION_TAGS.get(ext, []):
            ft.add_tag(Tag(tag.name, tag.category, 1.0, "auto"))

        # 2. Filename pattern tags
        fname = path.stem.lower()
        for pattern, tags in _FILENAME_PATTERNS:
            if pattern.search(fname):
                for tag in tags:
                    ft.add_tag(Tag(tag.name, tag.category, 0.8, "auto"))

        # 3. Content keyword tags
        if not content:
            content = self._extract_content(str(path))
        if content:
            content_lower = content.lower()
            for keyword, tags in _CONTENT_KEYWORDS.items():
                if keyword.lower() in content_lower:
                    for tag in tags:
                        ft.add_tag(Tag(tag.name, tag.category, tag.confidence, "auto"))

        # 4. Medical NER tags
        if content:
            self._init_ner()
            if self._ner:
                try:
                    ner_result = self._ner.extract(content)
                    for entity in ner_result.entities:
                        tag_name = f"medical/{entity.entity_type}/{entity.text[:30]}"
                        ft.add_tag(Tag(tag_name, "medical", entity.confidence, "ner"))
                except Exception as exc:
                    logger.debug(f"NER tagging error: {exc}")

        # 5. Classifier tags
        self._init_classifier()
        if self._classifier:
            try:
                result = self._classifier.classify_file(str(path))
                category = result.get("category", "")
                if category:
                    ft.add_tag(Tag(f"category/{category}", "classification", 0.7, "classifier"))
            except Exception as exc:
                logger.debug(f"Classifier tagging error: {exc}")

        # 6. Language detection tag
        if content:
            lang = self._detect_language(content)
            if lang:
                ft.add_tag(Tag(f"language/{lang}", "language", 0.9, "auto"))

        # Cache and return
        self._cache[str(path)] = ft
        return ft

    def get_tags(self, filepath: str) -> FileTags:
        """Get tags for a file (from cache, sidecar, or auto-generate)."""
        path = str(filepath)
        if path in self._cache:
            return self._cache[path]

        # Try loading sidecar
        sidecar = self._sidecar_path(filepath)
        if sidecar and sidecar.exists():
            try:
                with open(sidecar, "r", encoding="utf-8") as f:
                    data = json.load(f)
                ft = FileTags.from_dict(data)
                self._cache[path] = ft
                return ft
            except Exception as exc:
                logger.debug(f"خطأ في تحميل sidecar: {exc}")

        # Auto-tag
        return self.auto_tag(filepath)

    def add_manual_tag(self, filepath: str, tag_name: str, category: str = "manual"):
        """Add a manual tag to a file."""
        ft = self.get_tags(filepath)
        ft.add_tag(Tag(tag_name, category, 1.0, "manual"))
        self._save_sidecar(filepath, ft)

    def remove_tag(self, filepath: str, tag_name: str) -> bool:
        """Remove a tag from a file."""
        ft = self.get_tags(filepath)
        removed = ft.remove_tag(tag_name)
        if removed:
            self._save_sidecar(filepath, ft)
        return removed

    def batch_tag(self, filepaths: list[str], tag_name: str, category: str = "manual") -> int:
        """Apply the same tag to multiple files."""
        count = 0
        for fp in filepaths:
            ft = self.get_tags(fp)
            ft.add_tag(Tag(tag_name, category, 1.0, "manual"))
            self._save_sidecar(fp, ft)
            count += 1
        return count

    def search_by_tag(self, directory: str, tag_name: str) -> list[str]:
        """Find all files in a directory that have a specific tag."""
        results = []
        dir_path = Path(directory)
        for item in dir_path.rglob("*"):
            if not item.is_file():
                continue
            ft = self.get_tags(str(item))
            for tag in ft.tags:
                if tag.name == tag_name or tag.name.startswith(tag_name + "/"):
                    results.append(str(item))
                    break
        return results

    def get_all_tags(self, directory: str) -> dict[str, int]:
        """Get tag frequency count across all files in a directory."""
        tag_counts: dict[str, int] = {}
        dir_path = Path(directory)
        for item in dir_path.rglob("*"):
            if not item.is_file():
                continue
            ft = self.get_tags(str(item))
            for tag in ft.tags:
                tag_counts[tag.name] = tag_counts.get(tag.name, 0) + 1
        return dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True))

    def _sidecar_path(self, filepath: str) -> Optional[Path]:
        """Get the TagSpaces-compatible sidecar path (.json next to file)."""
        path = Path(filepath)
        if self._tags_dir:
            return self._tags_dir / (path.name + ".json")
        return Path(str(path) + ".json")

    def _save_sidecar(self, filepath: str, ft: FileTags):
        """Save tags to a TagSpaces-compatible sidecar JSON file."""
        from datetime import datetime
        ft.last_updated = datetime.now().isoformat()
        sidecar = self._sidecar_path(filepath)
        if not sidecar:
            return
        try:
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            with open(sidecar, "w", encoding="utf-8") as f:
                json.dump(ft.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error(f"خطأ في حفظ sidecar: {exc}")

    def _extract_content(self, filepath: str) -> str:
        """Extract text content from a file for keyword matching."""
        path = Path(filepath)
        ext = path.suffix.lower()
        try:
            if ext in (".txt", ".md", ".csv", ".json", ".log"):
                return path.read_text(encoding="utf-8", errors="ignore")[:4000]
            elif ext == ".pdf":
                try:
                    import pdfplumber
                    with pdfplumber.open(filepath) as pdf:
                        return "\n".join(p.extract_text() or "" for p in pdf.pages)[:4000]
                except ImportError:
                    pass
            elif ext == ".docx":
                try:
                    from docx import Document
                    doc = Document(filepath)
                    return "\n".join(p.text for p in doc.paragraphs)[:4000]
                except ImportError:
                    pass
        except Exception:
            pass
        return ""

    def _detect_language(self, text: str) -> str:
        """Simple language detection for Arabic vs English."""
        arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
        latin_chars = sum(1 for c in text if "a" <= c.lower() <= "z")
        if arabic_chars > latin_chars and arabic_chars > 5:
            return "arabic"
        elif latin_chars > arabic_chars and latin_chars > 5:
            return "english"
        elif arabic_chars > 0 and latin_chars > 0:
            return "bilingual"
        return "unknown"
