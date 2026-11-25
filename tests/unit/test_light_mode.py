"""اختبارات الوضع الخفيف بلا LLM (F005): التطبيق يعمل كاملاً بلا Ollama.

تغطي: حفظ/تحميل الراية في Config، مسار BM25 فقط في hybrid_search،
الإجابة الاستخلاصية في rag_engine بلا LLM، تعطيل ai_engine صريحًا،
والتراجع الرشيق عند غياب حزمة ollama نفسها (sys.modules trick).
"""
import sys

from src.core.ai_engine import AIEngine
from src.core.config import Config
from src.core.hybrid_search import HybridSearchEngine


# ── Config ──────────────────────────────────────────────

def test_config_light_mode_defaults_false_and_roundtrips(tmp_path):
    cfg = Config()
    assert cfg.light_mode is False
    cfg.light_mode = True
    path = tmp_path / "config.json"
    cfg.save(str(path))
    assert Config.load(str(path)).light_mode is True


# ── HybridSearchEngine (BM25 فقط) ──────────────────────

def _write_docs(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("تقرير طبي عن قصور القلب وعلاجه بالأدوية", encoding="utf-8")
    (docs / "b.txt").write_text("ملاحظات مشروع برمجي عن قواعد البيانات", encoding="utf-8")
    return docs


def test_hybrid_light_mode_indexes_and_searches_bm25_only(tmp_path):
    docs = _write_docs(tmp_path)
    eng = HybridSearchEngine(light_mode=True)
    assert eng.index_files(str(docs)) == 2
    results = eng.search("قصور القلب", top_k=5)
    assert results, "BM25 يجب أن يعيد نتائج في الوضع الخفيف"
    for r in results:
        assert r["engine"] == "bm25_only_light"
        assert r["semantic_rank"] == 0
        assert r["bm25_rank"] > 0


def test_hybrid_light_mode_reindex_is_clean(tmp_path):
    docs = _write_docs(tmp_path)
    eng = HybridSearchEngine(light_mode=True)
    assert eng.index_files(str(docs)) == 2
    assert eng.index_files(str(docs)) == 2  # reset=True: بلا تكرار
    assert eng.bm25.document_count == 2


def test_hybrid_normal_mode_keeps_hybrid_label():
    eng = HybridSearchEngine()
    eng.bm25.add_documents(["نص تجريبي عن القلب"])
    eng._doc_ids.append("d1")
    eng._doc_texts["d1"] = "نص تجريبي عن القلب"
    results = eng.search("القلب", top_k=3)
    assert results
    assert results[0]["engine"] == "hybrid_bm25+semantic_rrf"


# ── AIEngine ────────────────────────────────────────────

def test_ai_engine_light_mode_never_touches_ollama():
    eng = AIEngine(Config(light_mode=True))
    assert "الوضع الخفيف" in eng.chat("مرحبا")
    assert eng.list_models() == []
    assert eng._ollama is None  # لم يُستورد ollama إطلاقاً


def test_ai_engine_degrades_gracefully_without_ollama(monkeypatch):
    monkeypatch.setitem(sys.modules, "ollama", None)  # import ollama → ImportError
    eng = AIEngine(Config())
    assert "Ollama غير متاح" in eng.chat("مرحبا")
    assert eng.suggest_category("report.pdf", "report.pdf") == "أخرى"
    assert eng.extract_keywords("report.txt") == []


# ── RAGEngine ───────────────────────────────────────────

class _FakeCollection:
    name = "fake_col"

    def count(self):
        return 1

    def query(self, query_texts, n_results):
        return {
            "documents": [["مقطع طبي تجريبي عن قصور القلب"]],
            "metadatas": [[{"source": "x.pdf"}]],
            "distances": [[0.12]],
        }


class _FakeClient:
    def list_collections(self):
        return [_FakeCollection()]

    def get_collection(self, name):
        return _FakeCollection()


def _make_rag(light_mode):
    from src.core.rag_engine import RAGEngine

    rag = RAGEngine.__new__(RAGEngine)  # بلا تهيئة chroma (غير مطلوبة هنا)
    rag.config = Config(light_mode=light_mode)
    rag._model = None
    rag._client = _FakeClient()
    return rag


def test_rag_light_mode_answers_from_retrieved_segments_only(monkeypatch):
    monkeypatch.setitem(sys.modules, "ollama", None)
    rag = _make_rag(light_mode=True)
    out = rag.query("ما هو قصور القلب؟")
    assert "الوضع الخفيف" in out
    assert "مقطع طبي تجريبي" in out


def test_rag_degrades_gracefully_without_ollama(monkeypatch):
    monkeypatch.setitem(sys.modules, "ollama", None)
    rag = _make_rag(light_mode=False)
    out = rag.query("ما هو قصور القلب؟")
    assert "لا يمكن الاتصال بـ Ollama" in out
