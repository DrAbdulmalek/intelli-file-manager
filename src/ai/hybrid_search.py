"""
Hybrid Search Engine — combines BM25 keyword search with semantic vector search.

This is a STUB file proposing the API for the hybrid search feature described in
docs/DEVELOPMENT_ROADMAP.md (Task 1.1).

When implementing, decide whether to:
  (a) Merge this class into src/core/semantic_search.py, or
  (b) Keep it as a companion module that wraps the existing semantic_search.

Inspired by: Flamehaven-Filesearch (BM25 + semantic + RRF fusion).
"""

from typing import List, Tuple, Dict, Any, Optional

import numpy as np

# Lazy imports — these are heavy and only needed at runtime
# from rank_bm25 import BM25Okapi
# import jieba  # for Chinese tokenization; use nltk for English


class HybridSearchEngine:
    """
    Hybrid search engine combining BM25 (keyword) and semantic (vector) search.

    alpha: weight of semantic search
        - 0.0 = BM25 only
        - 1.0 = semantic only
        - 0.5 = balanced (default)
    """

    def __init__(self, vector_db, ollama_client, alpha: float = 0.5):
        self.vector_db = vector_db
        self.ollama = ollama_client
        self.alpha = alpha
        self.bm25_index = None
        self.documents: List[str] = []
        self.doc_ids: List[str] = []

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------
    def index_documents(self, file_paths: List[str], contents: List[str]) -> None:
        """Index documents for both BM25 and vector search."""
        # Store documents for BM25
        self.documents = contents
        self.doc_ids = file_paths

        # Tokenize (use jieba for Chinese, nltk.word_tokenize for English)
        tokenized_docs = [self._tokenize(doc) for doc in contents]
        # self.bm25_index = BM25Okapi(tokenized_docs)  # uncomment when implementing

        # Index vectors (reuse existing vector_db logic)
        for path, content in zip(file_paths, contents):
            embedding = self.ollama.embed(content)
            self.vector_db.add(path, embedding)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        alpha: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run hybrid search and return merged results.

        Returns a list of dicts:
            [{"file_path": str, "score": float, "source": "bm25"|"semantic"|"hybrid"}, ...]
        """
        if alpha is None:
            alpha = self.alpha

        # 1. Semantic search
        query_embedding = self.ollama.embed(query)
        semantic_results = self.vector_db.search(query_embedding, top_k=top_k * 2)

        # 2. BM25 search
        tokenized_query = self._tokenize(query)
        # bm25_scores = self.bm25_index.get_scores(tokenized_query)
        bm25_scores: List[float] = []  # placeholder

        # 3. Reciprocal Rank Fusion
        merged = self._reciprocal_rank_fusion(
            semantic_results=semantic_results,
            bm25_scores=bm25_scores,
            alpha=alpha,
        )
        return merged[:top_k]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text. Use jieba for Chinese, nltk for English, or a simple split fallback."""
        # Lazy load to avoid import cost when not used
        # import jieba
        # return jieba.lcut(text)
        return text.lower().split()

    def _reciprocal_rank_fusion(
        self,
        semantic_results: List[Dict[str, Any]],
        bm25_scores: List[float],
        alpha: float,
        k: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        Reciprocal Rank Fusion (RRF).

        For each result, score = alpha * (1 / (k + rank_semantic))
                                + (1 - alpha) * (1 / (k + rank_bm25))
        """
        # TODO: implement RRF
        # 1. Build rank maps for both result sets
        # 2. For each unique doc_id, sum the RRF scores
        # 3. Sort by fused score descending
        return semantic_results  # placeholder
