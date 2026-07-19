"""
Tests for HybridSearchEngine — see docs/DEVELOPMENT_ROADMAP.md (Task 1.1).

These tests are STUBS — they exercise the API surface but use mocks for the
vector DB and Ollama client. Real integration tests should be added when the
hybrid search is wired into the actual services.
"""

import pytest

from src.ai.hybrid_search import HybridSearchEngine


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeVectorDB:
    def __init__(self):
        self.store = {}

    def add(self, path, embedding):
        self.store[path] = embedding

    def search(self, embedding, top_k=10):
        # Return all stored paths with a fake score — order doesn't matter here
        return [{"file_path": p, "score": 1.0} for p in list(self.store)[:top_k]]


class _FakeOllama:
    def embed(self, text):
        # Deterministic fake embedding based on text length
        return [float(len(text))]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return HybridSearchEngine(vector_db=_FakeVectorDB(), ollama_client=_FakeOllama())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHybridSearch:
    def test_engine_initializes_with_defaults(self, engine):
        assert engine.alpha == 0.5
        assert engine.bm25_index is None
        assert engine.documents == []

    def test_index_documents_stores_metadata(self, engine):
        docs = ["This is a test document", "Another document for testing"]
        engine.index_documents(["file1.txt", "file2.txt"], docs)
        assert len(engine.documents) == 2
        assert len(engine.doc_ids) == 2

    @pytest.mark.asyncio
    async def test_hybrid_search_returns_list(self, engine):
        # Index a couple of docs first
        engine.index_documents(
            ["file1.txt", "file2.txt"],
            ["machine learning basics", "deep learning fundamentals"],
        )
        results = engine.hybrid_search("learning", top_k=5)
        assert isinstance(results, list)
        assert len(results) <= 5

    def test_tokenize_fallback_splits_on_whitespace(self, engine):
        tokens = engine._tokenize("hello world from intellifile")
        assert tokens == ["hello", "world", "from", "intellifile"]
