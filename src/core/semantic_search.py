"""محرك البحث الدلالي - بحث ذكي في الملفات"""
import json
import logging
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


class SemanticSearchEngine:
    """محرك بحث دلالي باستخدام embeddings"""

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
                 index_path: str = None,
                 glossary_terms: dict = None):
        self.model_name = model_name
        self._model = None
        self._index_path = Path(index_path or "~/.intellifile/search_index").expanduser()
        self._embeddings = {}
        self._file_texts = {}
        self._field_extractor = None
        self._glossary_terms = glossary_terms or {}

    def _init_field_extractor(self):
        """Try to import field_extractor from omni-medical-suite."""
        if self._field_extractor is not None:
            return
        try:
            from src.ocr.field_extractor import extract_fields, build_template_signature
            self._field_extractor = {
                "extract_fields": extract_fields,
                "build_template_signature": build_template_signature,
            }
            logger.info("تم تحميل field_extractor من omni-medical-suite")
        except ImportError:
            logger.debug("field_extractor غير متاح")
            self._field_extractor = None

    def _enrich_with_glossary(self, text: str) -> str:
        """Enrich text with glossary terms for better search matching.

        Appends normalized glossary terms found in the text, enabling
        bilingual search (Arabic query matching English terms and vice versa).
        """
        if not self._glossary_terms:
            return text

        enriched_parts = [text]
        text_lower = text.lower()

        for arabic_term, english_term in self._glossary_terms.items():
            if arabic_term in text or english_term.lower() in text_lower:
                enriched_parts.append(f"[{arabic_term} = {english_term}]")

        enriched = " ".join(enriched_parts)
        return enriched[:3000]  # Limit length

    def _load_model(self):
        """تحميل نموذج embeddings"""
        if self._model is not None:
            return True
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            logger.info(f"تم تحميل نموذج: {self.model_name}")
            return True
        except ImportError:
            logger.error("sentence-transformers غير مثبت")
            return False
        except Exception as e:
            logger.error(f"خطأ في تحميل النموذج: {e}")
            return False

    def _extract_text(self, filepath: str) -> str:
        """استخراج نص من الملف"""
        path = Path(filepath)
        ext = path.suffix.lower()

        try:
            if ext in (".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml",
                        ".py", ".js", ".ts", ".html", ".css", ".sh", ".bat", ".log"):
                return path.read_text(encoding="utf-8", errors="ignore")[:2000]
            elif ext == ".pdf":
                import pdfplumber
                with pdfplumber.open(filepath) as pdf:
                    return "\n".join(p.extract_text() or "" for p in pdf.pages)[:2000]
            elif ext in (".docx",):
                from docx import Document
                doc = Document(filepath)
                return "\n".join(p.text for p in doc.paragraphs)[:2000]
        except Exception as e:
            logger.debug(f"لا يمكن قراءة {filepath}: {e}")
        return path.name

    def index_files(self, directory: str) -> int:
        """فهرسة الملفات في مجلد"""
        if not self._load_model():
            return 0

        dir_path = Path(directory)
        count = 0
        for item in dir_path.rglob("*"):
            if item.is_file() and not item.name.startswith("."):
                try:
                    text = self._extract_text(str(item))
                    # Enrich with glossary terms
                    text = self._enrich_with_glossary(text)
                    if text.strip():
                        emb = self._model.encode(text)
                        self._embeddings[str(item)] = emb.tolist()
                        self._file_texts[str(item)] = text
                        count += 1
                except Exception:
                    continue

        logger.info(f"تم فهرسة {count} ملف من {directory}")
        return count

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """بحث دلالي في الملفات المفهرسة"""
        if not self._load_model() or not self._embeddings:
            return []

        try:
            query_enriched = self._enrich_with_glossary(query)
            query_emb = self._model.encode(query_enriched)
            results = []
            for filepath, emb_list in self._embeddings.items():
                # حساب التشابه الجيبي
                import numpy as np
                a = np.array(query_emb)
                b = np.array(emb_list)
                sim = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
                results.append((filepath, sim))
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]
        except Exception as e:
            logger.error(f"خطأ في البحث: {e}")
            return []

    def build_knowledge_graph(self) -> dict:
        """بناء رسم بياني معرفي للعلاقات بين الملفات"""
        import networkx as nx
        graph = nx.Graph()

        for filepath, text in self._file_texts.items():
            path = Path(filepath)
            graph.add_node(str(path), type="file", name=path.name,
                           extension=path.suffix, size=path.stat().st_size
                           if path.exists() else 0)

        # ربط الملفات بناءً على التشابه
        filepaths = list(self._embeddings.keys())
        for i in range(len(filepaths)):
            for j in range(i + 1, len(filepaths)):
                try:
                    import numpy as np
                    a = np.array(self._embeddings[filepaths[i]])
                    b = np.array(self._embeddings[filepaths[j]])
                    sim = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
                    if sim > 0.7:
                        graph.add_edge(filepaths[i], filepaths[j],
                                      weight=sim, type="similarity")
                except Exception:
                    continue

        return nx.node_link_data(graph)

    def save_index(self):
        """حفظ الفهرس"""
        self._index_path.mkdir(parents=True, exist_ok=True)
        data = {"embeddings": self._embeddings, "texts": self._file_texts}
        with open(self._index_path / "index.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        logger.info(f"تم حفظ الفهرس: {len(self._embeddings)} ملف")

    def load_index(self) -> bool:
        """تحميل الفهرس"""
        index_file = self._index_path / "index.json"
        if not index_file.exists():
            return False
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._embeddings = data.get("embeddings", {})
            self._file_texts = data.get("texts", {})
            logger.info(f"تم تحميل الفهرس: {len(self._embeddings)} ملف")
            return True
        except Exception as e:
            logger.error(f"خطأ في تحميل الفهرس: {e}")
            return False
