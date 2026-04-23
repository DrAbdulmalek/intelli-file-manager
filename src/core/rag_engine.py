"""محرك RAG - توليد معزز بالاسترجاع للإجابة عن أسئلة الملفات"""
import logging
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class RAGEngine:
    """محرك RAG باستخدام ChromaDB

    يدعم طريقتين للتهيئة:
    - RAGEngine(persist_dir=..., model=...)  # مباشر
    - RAGEngine(config=..., ai_engine=...)  # عبر كائن الإعدادات
    """

    def __init__(self, persist_dir: str = None, model: str = None,
                 config=None, ai_engine=None):
        # دعم التوافق مع الإصدارات القديمة والجديدة
        if config is not None:
            self.config = config
        else:
            from .config import Config
            self.config = Config()

        self.ai_engine = ai_engine
        self._model = model  # None = سيستخدم Config.ai_model
        self._persist_dir = (
            persist_dir
            or getattr(self.config, 'vector_db_path', None)
            or "~/.intellifile/chroma_db"
        )
        self._client = None
        self._embedding_function = None
        self._init_chroma()
        self._init_embeddings()

    def _init_chroma(self):
        """تهيئة ChromaDB"""
        try:
            import chromadb
            self._client = chromadb.PersistentClient(
                path=str(Path(self._persist_dir).expanduser())
            )
            logger.info("تم تهيئة ChromaDB")
        except ImportError:
            logger.error("chromadb غير مثبت")
        except Exception as e:
            logger.error(f"خطأ في تهيئة ChromaDB: {e}")

    def _init_embeddings(self):
        """تهيئة دالة التضمين"""
        if not self._client:
            logger.warning("ChromaDB غير مهيأ، لن يتم استخدام التضمين")
            self._embedding_function = None
            return

        try:
            from chromadb.utils import embedding_functions
            self._embedding_function = (
                embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                )
            )
            logger.info("تم تهيئة دالة التضمين")
        except Exception as e:
            logger.warning(f"فشل تهيئة دالة التضمين: {e}")
            self._embedding_function = None

    def ingest_file(self, filepath: str, chunk_size: int = 500) -> int:
        """استيعاب ملف في قاعدة المعرفة"""
        if not self._client:
            return 0

        path = Path(filepath)
        collection_name = path.stem.replace(" ", "_")[:50]

        try:
            text = self._extract_text(filepath)
            if not text:
                return 0

            chunks = self._chunk_text(text, chunk_size)
            collection = self._client.get_or_create_collection(
                name=collection_name, metadata={"hnsw:space": "cosine"}
            )

            ids = [f"{collection_name}_{i}" for i in range(len(chunks))]
            metadatas = [{"source": str(path), "chunk": i} for i in range(len(chunks))]
            documents = chunks

            if ids:
                if self._embedding_function:
                    collection.add(
                        ids=ids, documents=documents,
                        metadatas=metadatas,
                    )
                else:
                    collection.add(
                        ids=ids, documents=documents,
                        metadatas=metadatas,
                    )
                logger.info(f"تم استيعاب {len(chunks)} مقطع من {path.name}")
            return len(chunks)
        except Exception as e:
            logger.error(f"خطأ في استيعاب {filepath}: {e}")
            return 0

    def query(self, question: str, n_results: int = 5) -> str:
        """البحث عن إجابة لسؤال"""
        if not self._client:
            return "خطأ: ChromaDB غير متاح"

        try:
            results_text = []
            for collection_name in self._list_collection_names():
                try:
                    collection = self._client.get_collection(collection_name)
                    results = collection.query(
                        query_texts=[question],
                        n_results=min(n_results, collection.count())
                    )
                    for doc in results["documents"][0]:
                        results_text.append(doc)
                except Exception:
                    continue

            if not results_text:
                return "لم يتم العثور على نتائج."

            context = "\n\n".join(
                f"[مقطع {i+1}]: {t}" for i, t in enumerate(results_text[:5])
            )
            prompt = (
                f"بناءً على المعلومات التالية، أجب عن السؤال:\n"
                f"السؤال: {question}\n\n"
                f"المعلومات:\n{context}\n\n"
                f"أجب باختصار ودقة بالعربية."
            )

            try:
                import ollama
                model_name = self._model or self.config.ai_model
                ollama_url = getattr(self.config, 'ollama_url', 'http://localhost:11434')
                client = ollama.Client(host=ollama_url)
                response = client.chat(model_name, messages=[
                    {"role": "system", "content": "أنت مساعد ذكي. أجب بالعربية بدقة."},
                    {"role": "user", "content": prompt}
                ])
                return response["message"]["content"]
            except Exception:
                return (
                    f"تم العثور على {len(results_text)} مقطع متعلق. "
                    "لكن لا يمكن الاتصال بـ Ollama."
                )

        except Exception as e:
            logger.error(f"خطأ في الاستعلام: {e}")
            return f"خطأ: {e}"

    def index_documents(self, filepaths: list, chunk_size: int = 500) -> int:
        """فهرسة مجموعة ملفات في قاعدة المعرفة

        المعاملات:
            filepaths: قائمة مسارات الملفات المراد فهرستها
            chunk_size: حجم المقطع النصي

        العائد:
            عدد المقاطع التي تم فهرستها
        """
        total_chunks = 0
        for filepath in filepaths:
            try:
                count = self.ingest_file(filepath, chunk_size=chunk_size)
                total_chunks += count
            except Exception as e:
                logger.error(f"خطأ في فهرسة {filepath}: {e}")
        logger.info(f"تم فهرسة {total_chunks} مقطع من {len(filepaths)} ملف")
        return total_chunks

    def semantic_search(self, query: str, top_k: int = 5) -> list:
        """بحث دلالي في قاعدة المعرفة

        المعاملات:
            query: نص الاستعلام
            top_k: عدد النتائج المطلوبة

        العائد:
            قائمة قواميس تحتوي على النص والمسافة وبيانات إضافية
        """
        if not self._client:
            return []

        all_results = []
        for collection_name in self._list_collection_names():
            try:
                collection = self._client.get_collection(collection_name)
                results = collection.query(
                    query_texts=[query],
                    n_results=min(top_k, max(1, collection.count()))
                )
                if results and results.get("documents"):
                    for i, doc in enumerate(results["documents"][0]):
                        entry = {
                            "text": doc,
                            "collection": collection_name,
                        }
                        if results.get("metadatas") and results["metadatas"][0]:
                            entry["metadata"] = results["metadatas"][0][i]
                        if results.get("distances") and results["distances"][0]:
                            entry["distance"] = results["distances"][0][i]
                        all_results.append(entry)
            except Exception as e:
                logger.debug(f"خطأ في البحث في {collection_name}: {e}")
                continue

        # ترتيب حسب المسافة وقطع النتائج
        all_results.sort(key=lambda x: x.get("distance", float("inf")))
        return all_results[:top_k]

    def _list_collection_names(self) -> List[str]:
        """قائمة أسماء المجممعات"""
        if not self._client:
            return []
        try:
            return [c.name for c in self._client.list_collections()]
        except Exception:
            return []

    def _extract_text(self, filepath: str) -> str:
        """استخراج نص من ملف"""
        path = Path(filepath)
        ext = path.suffix.lower()
        try:
            if ext in (".txt", ".md", ".csv", ".json", ".yaml", ".yml"):
                return path.read_text(encoding="utf-8", errors="ignore")
            elif ext == ".pdf":
                import pdfplumber
                with pdfplumber.open(filepath) as pdf:
                    return "\n".join(p.extract_text() or "" for p in pdf.pages)
            elif ext == ".docx":
                from docx import Document
                doc = Document(filepath)
                return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            logger.debug(f"خطأ في قراءة {filepath}: {e}")
        return ""

    def _chunk_text(self, text: str, chunk_size: int) -> List[str]:
        """تقسيم النص إلى مقاطع"""
        if len(text) <= chunk_size:
            return [text]
        chunks = []
        words = text.split()
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
        return chunks
