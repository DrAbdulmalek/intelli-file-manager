# -*- coding: utf-8 -*-
"""قاعدة البيانات - وحدات إدارة البيانات

يوفر هذا الوحدة النوى لإدارة قاعدة البيانات المتجهية (ChromaDB)
بما في ذلك المخططات (schemas) ومدير الاتصال بقاعدة البيانات.
"""

from .chroma_db import ChromaDBManager
from .schemas import FileMetadata, FileRecord

__all__ = ["ChromaDBManager", "FileMetadata", "FileRecord"]
