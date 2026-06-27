# -*- coding: utf-8 -*-
"""مدير قاعدة بيانات ChromaDB - إدارة التخزين المتجهي للملفات

يوفر هذا الملف طبقة تجريد عالية المستوى للتعامل مع قاعدة بيانات ChromaDB
المتجهية، بما في ذلك إضافة الملفات والبحث الدلالي وإدارة السجلات.

الميزات الرئيسية:
- تهيئة كسولة (lazy initialization) لقاعدة البيانات
- إدارة الأخطاء الشاملة مع رسائل عربية
- تسجيل مفصل لجميع العمليات
- دعم البحث الدلالي والبحث بالبيانات الوصفية
- إحصائيات متقدمة لتحليل الملفات المخزنة
"""

import logging
import os
from typing import Optional, List, Dict, Any

from .schemas import FileMetadata, FileRecord

# إعداد المسجل للوحدة
logger = logging.getLogger(__name__)


class ChromaDBNotInstalledError(Exception):
    """استثناء يُرفع عندما لا تكون مكتبة ChromaDB مثبتة"""

    def __init__(self):
        super().__init__(
            "مكتبة chromadb غير مثبتة. يرجى تثبيتها بالأمر: pip install chromadb"
        )


class ChromaDBManager:
    """مدير قاعدة بيانات ChromaDB للملفات

    يوفر واجهة شاملة للتعامل مع قاعدة البيانات المتجهية ChromaDB
    لإدارة سجلات الملفات والبحث الدلالي فيها.

    الاستخدام الأساسي:
        >>> manager = ChromaDBManager()
        >>> manager.init_collection()
        >>> record = FileRecord(metadata=FileMetadata(file_name="test.pdf"))
        >>> manager.add_file(record)

    Attributes:
        persist_dir: مسار تخزين قاعدة البيانات على القرص
        _client: عميل ChromaDB (يتم تهيئته بشكل كسول)
        _collection: مجموعة ChromaDB الحالية
    """

    def __init__(self, persist_dir: str = "~/.intellifile/chroma_db"):
        """تهيئة مدير قاعدة البيانات

        Args:
            persist_dir: مسار تخزين البيانات على القرص.
                         يتم توسيع المسار النسبي (~) تلقائياً.
        """
        self.persist_dir: str = os.path.expanduser(persist_dir)
        self._client: Optional[Any] = None
        self._collection: Optional[Any] = None
        self._collection_name: str = ""
        logger.info(
            "تم تهيئة مدير ChromaDB بمسار التخزين: %s",
            self.persist_dir,
        )

    # ------------------------------------------------------------------
    # التهيئة والاتصال
    # ------------------------------------------------------------------

    def _check_chromadb_installed(self) -> bool:
        """التحقق من تثبيت مكتبة ChromaDB

        Returns:
            bool: True إذا كانت المكتبة مثبتة، False خلاف ذلك
        """
        try:
            import chromadb  # noqa: F401
            return True
        except ImportError:
            logger.error("مكتبة chromadb غير مثبتة في النظام")
            return False

    def _ensure_client(self):
        """التأكد من تهيئة عميل ChromaDB

        يقوم بتهيئة العميل بشكل كسول عند أول استخدام.
        يرفع استثناء إذا لم تكن المكتبة مثبتة.

        Raises:
            ChromaDBNotInstalledError: إذا لم تكن المكتبة مثبتة
        """
        if self._client is not None:
            return

        if not self._check_chromadb_installed():
            raise ChromaDBNotInstalledError()

        import chromadb

        # إنشاء مجلد التخزين إذا لم يكن موجوداً
        os.makedirs(self.persist_dir, exist_ok=True)

        try:
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            logger.info("تم الاتصال بقاعدة بيانات ChromaDB بنجاح")
        except Exception as e:
            logger.error("فشل الاتصال بقاعدة بيانات ChromaDB: %s", e)
            raise

    def init_collection(self, name: str = "files") -> bool:
        """تهيئة (أو الحصول على) مجموعة في قاعدة البيانات

        Args:
            name: اسم المجموعة (الافتراضي: "files")

        Returns:
            bool: True إذا نجحت العملية، False خلاف ذلك
        """
        self._ensure_client()

        try:
            self._collection = self._client.get_or_create_collection(
                name=name,
                metadata={
                    "description": "مجموعة ملفات IntelliFile - تصنيف وبحث دلالي",
                    "created_by": "IntelliFile",
                },
            )
            self._collection_name = name
            logger.info("تم تهيئة المجموعة '%s' بنجاح", name)
            return True
        except Exception as e:
            logger.error("فشل تهيئة المجموعة '%s': %s", name, e)
            return False

    def _ensure_collection(self):
        """التأكد من تهيئة المجموعة

        يتهيئة المجموعة الافتراضية إذا لم تكن مهيأة.

        Raises:
            RuntimeError: إذا لم تكن المجموعة مهيأة ولا يمكن تهيئتها
        """
        if self._collection is None:
            if not self.init_collection():
                raise RuntimeError(
                    "لم يتم تهيئة مجموعة قاعدة البيانات. "
                    "تأكد من تثبيت chromadb واستدعاء init_collection() أولاً."
                )

    # ------------------------------------------------------------------
    # عمليات الإضافة والتعديل
    # ------------------------------------------------------------------

    def add_file(self, record: FileRecord) -> bool:
        """إضافة سجل ملف إلى قاعدة البيانات

        يضيف الملف مع بياناته الوصفية وتضمينه (إن وُجد) ونصه المستخرج.

        Args:
            record: سجل الملف المراد إضافته

        Returns:
            bool: True إذا نجحت الإضافة، False خلاف ذلك
        """
        self._ensure_collection()

        if not record.id:
            logger.warning("تم تجاهل سجل ملف بدون معرف")
            return False

        try:
            # تجهيز بيانات الإدراج
            documents = []
            metadatas = []
            embeddings = []
            ids = []

            document_text = record.document_text or ""
            # بناء نص الوثيقة للبحث النصي
            if not document_text:
                document_text = self._build_searchable_text(record.metadata)
            documents.append(document_text)

            # تجهيز البيانات الوصفية - ChromaDB لا يدعم القوائم
            metadata_dict = self._prepare_metadata_for_chroma(record.metadata)
            metadatas.append(metadata_dict)

            # إضافة التضمين إذا كان متوفراً
            if record.has_embedding:
                embeddings.append(record.embedding)

            ids.append(record.id)

            # إدراج البيانات في المجموعة
            add_kwargs: Dict[str, Any] = {
                "ids": ids,
                "documents": documents,
                "metadatas": metadatas,
            }
            if embeddings:
                add_kwargs["embeddings"] = embeddings

            self._collection.add(**add_kwargs)

            logger.info(
                "تمت إضافة الملف '%s' بنجاح (المعرف: %s)",
                record.metadata.file_name,
                record.id,
            )
            return True

        except Exception as e:
            logger.error(
                "فشل إضافة الملف '%s' (المعرف: %s): %s",
                record.metadata.file_name,
                record.id,
                e,
            )
            return False

    def add_files(self, records: List[FileRecord]) -> int:
        """إضافة عدة ملفات دفعة واحدة

        Args:
            records: قائمة سجلات الملفات المراد إضافتها

        Returns:
            int: عدد الملفات التي تمت إضافتها بنجاح
        """
        self._ensure_collection()

        if not records:
            logger.warning("قائمة الملفات فارغة، لا شيء لإضافته")
            return 0

        success_count = 0
        for record in records:
            if self.add_file(record):
                success_count += 1

        logger.info(
            "تمت إضافة %d من %d ملف بنجاح",
            success_count,
            len(records),
        )
        return success_count

    def update_file(self, record: FileRecord) -> bool:
        """تحديث سجل ملف موجود في قاعدة البيانات

        Args:
            record: سجل الملف المحدث

        Returns:
            bool: True إذا نجح التحديث، False خلاف ذلك
        """
        self._ensure_collection()

        if not record.id:
            logger.warning("لا يمكن تحديث سجل بدون معرف")
            return False

        try:
            # تجهيز بيانات التحديث
            documents = []
            metadatas = []
            embeddings = []

            document_text = record.document_text or self._build_searchable_text(record.metadata)
            documents.append(document_text)

            metadata_dict = self._prepare_metadata_for_chroma(record.metadata)
            metadatas.append(metadata_dict)

            if record.has_embedding:
                embeddings.append(record.embedding)

            update_kwargs: Dict[str, Any] = {
                "ids": [record.id],
                "documents": documents,
                "metadatas": metadatas,
            }
            if embeddings:
                update_kwargs["embeddings"] = embeddings

            self._collection.update(**update_kwargs)

            logger.info(
                "تم تحديث الملف '%s' بنجاح (المعرف: %s)",
                record.metadata.file_name,
                record.id,
            )
            return True

        except Exception as e:
            logger.error(
                "فشل تحديث الملف '%s' (المعرف: %s): %s",
                record.metadata.file_name,
                record.id,
                e,
            )
            return False

    def upsert_file(self, record: FileRecord) -> bool:
        """إضافة أو تحديث سجل ملف (upsert)

        إذا كان الملف موجوداً يتم تحديثه، وإلا يتم إضافته.

        Args:
            record: سجل الملف

        Returns:
            bool: True إذا نجحت العملية، False خلاف ذلك
        """
        self._ensure_collection()

        try:
            documents = []
            metadatas = []
            embeddings = []

            document_text = record.document_text or self._build_searchable_text(record.metadata)
            documents.append(document_text)

            metadata_dict = self._prepare_metadata_for_chroma(record.metadata)
            metadatas.append(metadata_dict)

            if record.has_embedding:
                embeddings.append(record.embedding)

            upsert_kwargs: Dict[str, Any] = {
                "ids": [record.id],
                "documents": documents,
                "metadatas": metadatas,
            }
            if embeddings:
                upsert_kwargs["embeddings"] = embeddings

            self._collection.upsert(**upsert_kwargs)

            logger.info(
                "تمت إضافة/تحديث الملف '%s' بنجاح (المعرف: %s)",
                record.metadata.file_name,
                record.id,
            )
            return True

        except Exception as e:
            logger.error(
                "فشل إضافة/تحديث الملف '%s' (المعرف: %s): %s",
                record.metadata.file_name,
                record.id,
                e,
            )
            return False

    # ------------------------------------------------------------------
    # عمليات البحث
    # ------------------------------------------------------------------

    def search(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        where_filter: Optional[Dict[str, Any]] = None,
    ) -> List[FileRecord]:
        """بحث دلالي عن الملفات باستخدام متجه التضمين

        Args:
            query_embedding: متجه التضمين للاستعلام
            n_results: الحد الأقصى لعدد النتائج (الافتراضي: 10)
            where_filter: فلاتر إضافية للبحث بالبيانات الوصفية

        Returns:
            List[FileRecord]: قائمة سجلات الملفات المطابقة مرتبة حسب التشابه
        """
        self._ensure_collection()

        try:
            query_kwargs: Dict[str, Any] = {
                "query_embeddings": [query_embedding],
                "n_results": n_results,
            }
            if where_filter:
                query_kwargs["where"] = where_filter

            results = self._collection.query(**query_kwargs)

            return self._parse_query_results(results)

        except Exception as e:
            logger.error("فشل البحث الدلالي: %s", e)
            return []

    def search_by_text(
        self,
        query_text: str,
        n_results: int = 10,
        where_filter: Optional[Dict[str, Any]] = None,
    ) -> List[FileRecord]:
        """بحث نصي عن الملفات

        يقوم ChromaDB بتضمين النص تلقائياً والبحث عن المتجهات المشابهة.

        Args:
            query_text: نص الاستعلام
            n_results: الحد الأقصى لعدد النتائج
            where_filter: فلاتر إضافية

        Returns:
            List[FileRecord]: قائمة سجلات الملفات المطابقة
        """
        self._ensure_collection()

        try:
            query_kwargs: Dict[str, Any] = {
                "query_texts": [query_text],
                "n_results": n_results,
            }
            if where_filter:
                query_kwargs["where"] = where_filter

            results = self._collection.query(**query_kwargs)

            return self._parse_query_results(results)

        except Exception as e:
            logger.error("فشل البحث النصي '%s': %s", query_text, e)
            return []

    def search_by_metadata(
        self,
        query: str = "",
        n_results: int = 10,
        category: Optional[str] = None,
    ) -> List[FileRecord]:
        """بحث في البيانات الوصفية للملفات

        يدعم البحث النصي والفلترة حسب التصنيف.

        Args:
            query: نص الاستعلام (يبحث في الاسم والمسار والعلامات)
            n_results: الحد الأقصى لعدد النتائج
            category: فلتر التصنيف (اختياري)

        Returns:
            List[FileRecord]: قائمة سجلات الملفات المطابقة
        """
        self._ensure_collection()

        try:
            # بناء فلاتر البحث
            where_filter: Dict[str, Any] = {}
            if category:
                where_filter["category"] = category

            if query:
                # استخدام البحث النصي مع الفلتر
                results = self.search_by_text(
                    query_text=query,
                    n_results=n_results,
                    where_filter=where_filter if where_filter else None,
                )
            else:
                # جلب جميع الملفات مع تطبيق الفلتر فقط
                results = self._get_all_with_filter(where_filter)

            return results

        except Exception as e:
            logger.error("فشل البحث بالبيانات الوصفية: %s", e)
            return []

    # ------------------------------------------------------------------
    # عمليات القراءة
    # ------------------------------------------------------------------

    def get_file(self, file_id: str) -> Optional[FileRecord]:
        """الحصول على سجل ملف محدد بالمعرف

        Args:
            file_id: المعرف الفريد للملف

        Returns:
            Optional[FileRecord]: سجل الملف إذا وُجد، None خلاف ذلك
        """
        self._ensure_collection()

        try:
            results = self._collection.get(ids=[file_id])

            if not results or not results.get("ids"):
                logger.debug("الملف بالمعرف '%s' غير موجود", file_id)
                return None

            return self._parse_get_results(results)[0]

        except Exception as e:
            logger.error("فشل جلب الملف '%s': %s", file_id, e)
            return None

    def get_files_by_ids(self, file_ids: List[str]) -> List[FileRecord]:
        """الحصول على عدة سجلات ملفات بمعرفاتها

        Args:
            file_ids: قائمة المعرفات

        Returns:
            List[FileRecord]: قائمة سجلات الملفات الموجودة
        """
        self._ensure_collection()

        if not file_ids:
            return []

        try:
            results = self._collection.get(ids=file_ids)
            return self._parse_get_results(results)

        except Exception as e:
            logger.error("فشل جلب الملفات المحددة: %s", e)
            return []

    def get_all_files(self, category: Optional[str] = None) -> List[FileRecord]:
        """الحصول على جميع الملفات المخزنة

        Args:
            category: فلتر التصنيف (اختياري) - عند التحديد يُرجع
                      الملفات من هذا التصنيف فقط

        Returns:
            List[FileRecord]: قائمة جميع سجلات الملفات
        """
        self._ensure_collection()

        try:
            where_filter = None
            if category:
                where_filter = {"category": category}

            return self._get_all_with_filter(where_filter)

        except Exception as e:
            logger.error("فشل جلب جميع الملفات: %s", e)
            return []

    def get_files_by_category(self, category: str) -> List[FileRecord]:
        """الحصول على جميع الملفات في تصنيف محدد

        Args:
            category: اسم التصنيف

        Returns:
            List[FileRecord]: قائمة الملفات في التصنيف المحدد
        """
        return self.get_all_files(category=category)

    def get_files_by_extension(self, extension: str) -> List[FileRecord]:
        """الحصول على جميع الملفات بامتداد محدد

        Args:
            extension: الامتداد المطلوب (مثل 'pdf')

        Returns:
            List[FileRecord]: قائمة الملفات بالامتداد المحدد
        """
        self._ensure_collection()

        try:
            return self._get_all_with_filter({"extension": extension.lower()})
        except Exception as e:
            logger.error("فشل جلب الملفات بالامتداد '%s': %s", extension, e)
            return []

    def get_duplicates(self) -> List[FileRecord]:
        """الحصول على جميع الملفات المكررة

        Returns:
            List[FileRecord]: قائمة الملفات المكررة
        """
        return self._get_all_with_filter({"is_duplicate": True})

    def get_protected_files(self) -> List[FileRecord]:
        """الحصول على جميع الملفات المحمية

        Returns:
            List[FileRecord]: قائمة الملفات المحمية
        """
        return self._get_all_with_filter({"is_protected": True})

    def get_files_by_tag(self, tag: str) -> List[FileRecord]:
        """الحصول على الملفات التي تحتوي على علامة محددة

        ملاحظة: هذا يبحث في النص المخزن وليس في بيانات وصفية منفصلة
        لأن ChromaDB لا يدعم القوائم في البيانات الوصفية بشكل مباشر.

        Args:
            tag: العلامة المطلوبة

        Returns:
            List[FileRecord]: قائمة الملفات المطابقة
        """
        all_files = self.get_all_files()
        return [f for f in all_files if tag in f.metadata.tags]

    # ------------------------------------------------------------------
    # الإحصائيات والتقارير
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """الحصول على إحصائيات شاملة عن قاعدة البيانات

        يتضمن:
        - إجمالي عدد الملفات
        - عدد الملفات في كل تصنيف
        - عدد الملفات المكررة
        - عدد الملفات المحمية
        - متوسط مستوى الثقة

        Returns:
            dict: قاموس يحتوي على الإحصائيات
        """
        self._ensure_collection()

        try:
            all_files = self.get_all_files()
            total_files = len(all_files)

            # عدد الملفات في كل تصنيف
            category_counts: Dict[str, int] = {}
            for record in all_files:
                cat = record.metadata.category or "أخرى"
                category_counts[cat] = category_counts.get(cat, 0) + 1

            # عدد الملفات المكررة والمحمية
            duplicate_count = sum(1 for f in all_files if f.metadata.is_duplicate)
            protected_count = sum(1 for f in all_files if f.metadata.is_protected)

            # متوسط مستوى الثقة
            confidence_values = [
                f.metadata.confidence
                for f in all_files
                if f.metadata.confidence > 0
            ]
            avg_confidence = (
                sum(confidence_values) / len(confidence_values)
                if confidence_values
                else 0.0
            )

            # إجمالي حجم الملفات
            total_size = sum(f.metadata.file_size for f in all_files)

            stats = {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "category_counts": category_counts,
                "duplicate_count": duplicate_count,
                "protected_count": protected_count,
                "avg_confidence": round(avg_confidence, 4),
                "has_embeddings_count": sum(
                    1 for f in all_files if f.has_embedding
                ),
            }

            logger.debug("تم حساب الإحصائيات: %d ملف إجمالي", total_files)
            return stats

        except Exception as e:
            logger.error("فشل حساب الإحصائيات: %s", e)
            return {
                "total_files": 0,
                "total_size_bytes": 0,
                "category_counts": {},
                "duplicate_count": 0,
                "protected_count": 0,
                "avg_confidence": 0.0,
                "has_embeddings_count": 0,
                "error": str(e),
            }

    def get_collection_info(self) -> dict:
        """الحصول على معلومات عن المجموعة الحالية

        Returns:
            dict: معلومات المجموعة
        """
        self._ensure_collection()

        try:
            count = self._collection.count()
            return {
                "name": self._collection_name,
                "count": count,
                "persist_dir": self.persist_dir,
            }
        except Exception as e:
            logger.error("فشل الحصول على معلومات المجموعة: %s", e)
            return {
                "name": self._collection_name,
                "count": 0,
                "persist_dir": self.persist_dir,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # عمليات الحذف
    # ------------------------------------------------------------------

    def delete_file(self, file_id: str) -> bool:
        """حذف سجل ملف من قاعدة البيانات

        Args:
            file_id: المعرف الفريد للملف المراد حذفه

        Returns:
            bool: True إذا نجح الحذف، False خلاف ذلك
        """
        self._ensure_collection()

        try:
            # التحقق من وجود الملف أولاً
            existing = self.get_file(file_id)
            if existing is None:
                logger.warning("الملف بالمعرف '%s' غير موجود للحذف", file_id)
                return False

            self._collection.delete(ids=[file_id])
            logger.info("تم حذف الملف '%s' بنجاح", file_id)
            return True

        except Exception as e:
            logger.error("فشل حذف الملف '%s': %s", file_id, e)
            return False

    def delete_files(self, file_ids: List[str]) -> int:
        """حذف عدة ملفات دفعة واحدة

        Args:
            file_ids: قائمة المعرفات المراد حذفها

        Returns:
            int: عدد الملفات التي تم حذفها بنجاح
        """
        self._ensure_collection()

        if not file_ids:
            return 0

        try:
            self._collection.delete(ids=file_ids)
            logger.info("تم حذف %d ملف بنجاح", len(file_ids))
            return len(file_ids)
        except Exception as e:
            logger.error("فشل الحذف الجماعي: %s", e)
            return 0

    def delete_by_category(self, category: str) -> int:
        """حذف جميع الملفات في تصنيف محدد

        Args:
            category: اسم التصنيف

        Returns:
            int: عدد الملفات المحذوفة
        """
        files = self.get_files_by_category(category)
        if not files:
            return 0

        file_ids = [f.id for f in files]
        return self.delete_files(file_ids)

    def clear_collection(self) -> bool:
        """حذف جميع السجلات من المجموعة الحالية

        Returns:
            bool: True إذا نجحت العملية، False خلاف ذلك
        """
        self._ensure_collection()

        try:
            # الحصول على جميع المعرفات أولاً
            all_results = self._collection.get()
            if all_results and all_results.get("ids"):
                self._collection.delete(ids=all_results["ids"])
                deleted_count = len(all_results["ids"])
                logger.info(
                    "تم مسح %d سجل من المجموعة '%s'",
                    deleted_count,
                    self._collection_name,
                )
            else:
                logger.info("المجموعة '%s' فارغة بالفعل", self._collection_name)

            return True

        except Exception as e:
            logger.error("فشل مسح المجموعة '%s': %s", self._collection_name, e)
            return False

    def delete_collection(self) -> bool:
        """حذف المجموعة بالكامل من قاعدة البيانات

        Returns:
            bool: True إذا نجح الحذف، False خلاف ذلك
        """
        self._ensure_client()

        if not self._collection_name:
            logger.warning("لا توجد مجموعة محددة للحذف")
            return False

        try:
            self._client.delete_collection(name=self._collection_name)
            logger.info("تم حذف المجموعة '%s' بالكامل", self._collection_name)
            self._collection = None
            self._collection_name = ""
            return True
        except Exception as e:
            logger.error("فشل حذف المجموعة '%s': %s", self._collection_name, e)
            return False

    # ------------------------------------------------------------------
    # طرق مساعدة داخلية
    # ------------------------------------------------------------------

    def _prepare_metadata_for_chroma(self, metadata: FileMetadata) -> Dict[str, Any]:
        """تحضير البيانات الوصفية للتخزين في ChromaDB

        ChromaDB لا يدعم جميع أنواع البيانات (مثل القوائم) في البيانات الوصفية،
        لذا يتم تحويلها إلى صيغة مدعومة.

        Args:
            metadata: البيانات الوصفية الأصلية

        Returns:
            Dict[str, Any]: البيانات الوصفية المحضرة
        """
        meta_dict = metadata.to_dict()
        clean_meta: Dict[str, Any] = {}

        for key, value in meta_dict.items():
            # تخطي القوائم (ChromaDB لا يدعمها في البيانات الوصفية)
            if isinstance(value, list):
                if value:  # تحويل القوائم غير الفارغة إلى نص مفصول بفواصل
                    clean_meta[key] = ",".join(str(v) for v in value)
                continue
            # تخطي القيم None
            if value is None:
                continue
            # تحويل القيم المنطقية إلى نص
            if isinstance(value, bool):
                clean_meta[key] = value
                continue
            # تخطي القيم الرقمية الصفرية (اختياري - للحفاظ على البيانات)
            clean_meta[key] = value

        return clean_meta

    def _build_searchable_text(self, metadata: FileMetadata) -> str:
        """بناء نص قابل للبحث من البيانات الوصفية

        يجمع بين الاسم والمسار والتصنيف والعلامات في نص واحد
        يُستخدم للبحث النصي في ChromaDB.

        Args:
            metadata: البيانات الوصفية

        Returns:
            str: النص القابل للبحث
        """
        parts = [
            metadata.file_name,
            metadata.extension,
            metadata.category,
            metadata.parent_dir,
            metadata.mime_type,
            metadata.content_type,
        ]
        if metadata.tags:
            parts.extend(metadata.tags)

        return " ".join(p for p in parts if p)

    def _parse_query_results(self, results: Dict[str, Any]) -> List[FileRecord]:
        """تحليل نتائج استعلام ChromaDB إلى سجلات ملفات

        Args:
            results: النتائج الخام من ChromaDB

        Returns:
            List[FileRecord]: قائمة سجلات الملفات
        """
        if not results or not results.get("ids"):
            return []

        records: List[FileRecord] = []

        # ChromaDB يُرجع نتائج في قوائم متداخلة (batch)
        ids = results.get("ids", [[]])[0]
        metadatas = results.get("metadatas", [None])[0]
        documents = results.get("documents", [None])[0]
        embeddings = results.get("embeddings", [None])[0]
        distances = results.get("distances", [None])[0]

        for i, file_id in enumerate(ids):
            try:
                # استخراج البيانات الوصفية
                metadata_dict = {}
                if metadatas and i < len(metadatas) and metadatas[i]:
                    metadata_dict = dict(metadatas[i])
                    # استرجاع العلامات من النص المفصول بفواصل
                    if "tags" in metadata_dict and isinstance(metadata_dict["tags"], str):
                        tags_str = metadata_dict["tags"]
                        metadata_dict["tags"] = (
                            [t.strip() for t in tags_str.split(",") if t.strip()]
                            if tags_str
                            else []
                        )

                metadata = FileMetadata.from_dict(metadata_dict)

                # استخراج التضمين
                embedding = None
                if embeddings and i < len(embeddings) and embeddings[i]:
                    embedding = list(embeddings[i])

                # استخراج النص المستخرج
                document_text = ""
                if documents and i < len(documents) and documents[i]:
                    document_text = str(documents[i])

                record = FileRecord(
                    id=file_id,
                    metadata=metadata,
                    embedding=embedding,
                    document_text=document_text,
                )

                # تخزين المسافة للتشابه (إذا وُجدت)
                if distances and i < len(distances) and distances[i] is not None:
                    record._search_distance = distances[i]

                records.append(record)

            except Exception as e:
                logger.warning("فشل تحليل السجل '%s': %s", file_id, e)
                continue

        logger.debug("تم تحليل %d سجل من نتائج البحث", len(records))
        return records

    def _parse_get_results(self, results: Dict[str, Any]) -> List[FileRecord]:
        """تحليل نتائج get() من ChromaDB إلى سجلات ملفات

        يختلف عن parse_query_results لأن get() يُرجع نتائج مسطحة
        بدلاً من نتائج متداخلة.

        Args:
            results: النتائج الخام من ChromaDB get()

        Returns:
            List[FileRecord]: قائمة سجلات الملفات
        """
        if not results or not results.get("ids"):
            return []

        records: List[FileRecord] = []
        ids = results.get("ids", [])
        metadatas = results.get("metadatas", [])
        documents = results.get("documents", [])
        embeddings = results.get("embeddings", [])

        for i, file_id in enumerate(ids):
            try:
                metadata_dict = {}
                if metadatas and i < len(metadatas) and metadatas[i]:
                    metadata_dict = dict(metadatas[i])
                    # استرجاع العلامات
                    if "tags" in metadata_dict and isinstance(metadata_dict["tags"], str):
                        tags_str = metadata_dict["tags"]
                        metadata_dict["tags"] = (
                            [t.strip() for t in tags_str.split(",") if t.strip()]
                            if tags_str
                            else []
                        )

                metadata = FileMetadata.from_dict(metadata_dict)

                embedding = None
                if embeddings and i < len(embeddings) and embeddings[i]:
                    embedding = list(embeddings[i])

                document_text = ""
                if documents and i < len(documents) and documents[i]:
                    document_text = str(documents[i])

                record = FileRecord(
                    id=file_id,
                    metadata=metadata,
                    embedding=embedding,
                    document_text=document_text,
                )
                records.append(record)

            except Exception as e:
                logger.warning("فشل تحليل السجل '%s': %s", file_id, e)
                continue

        return records

    def _get_all_with_filter(
        self, where_filter: Optional[Dict[str, Any]] = None
    ) -> List[FileRecord]:
        """جلب جميع السجلات مع تطبيق فلتر اختياري

        Args:
            where_filter: فلتر البيانات الوصفية (اختياري)

        Returns:
            List[FileRecord]: قائمة السجلات
        """
        self._ensure_collection()

        try:
            get_kwargs: Dict[str, Any] = {}
            if where_filter:
                get_kwargs["where"] = where_filter

            # جلب دفعي - الحد الأقصى 10000 سجل
            all_records: List[FileRecord] = []
            batch_size = 5000
            offset = 0

            while True:
                batch_kwargs = dict(get_kwargs)
                batch_kwargs["limit"] = batch_size
                batch_kwargs["offset"] = offset

                results = self._collection.get(**batch_kwargs)
                if not results or not results.get("ids"):
                    break

                batch_records = self._parse_get_results(results)
                all_records.extend(batch_records)

                if len(batch_records) < batch_size:
                    break

                offset += batch_size

            return all_records

        except Exception as e:
            logger.error("فشل جلب السجلات مع الفلتر: %s", e)
            return []

    # ------------------------------------------------------------------
    # إدارة الاتصال والعمليات الأخرى
    # ------------------------------------------------------------------

    def count(self) -> int:
        """الحصول على عدد السجلات في المجموعة الحالية

        Returns:
            int: عدد السجلات
        """
        self._ensure_collection()

        try:
            return self._collection.count()
        except Exception as e:
            logger.error("فشل عد السجلات: %s", e)
            return 0

    def reset(self) -> bool:
        """إعادة تعيين مدير قاعدة البيانات بالكامل

        يحذف المجموعة ويعيد تهيئة الاتصال.

        Returns:
            bool: True إذا نجحت العملية
        """
        try:
            self.delete_collection()
            self._client = None
            self._collection = None
            self._collection_name = ""
            logger.info("تم إعادة تعيين مدير قاعدة البيانات")
            return True
        except Exception as e:
            logger.error("فشل إعادة التعيين: %s", e)
            return False

    def heartbeat(self) -> bool:
        """فحص حالة الاتصال بقاعدة البيانات

        Returns:
            bool: True إذا كانت قاعدة البيانات متاحة
        """
        try:
            self._ensure_collection()
            _ = self._collection.count()
            return True
        except Exception:
            return False

    def __repr__(self) -> str:
        """تمثيل نصي للمدير

        Returns:
            str: وصف مختصر للمدير
        """
        status = "متصل" if self._collection is not None else "غير متصل"
        return (
            f"ChromaDBManager(persist_dir='{self.persist_dir}', "
            f"collection='{self._collection_name}', status='{status}')"
        )
