"""
Tests for SmartTaggingSystem — see docs/DEVELOPMENT_ROADMAP.md (Task 2.1).

These tests are STUBS — they exercise the API surface without requiring
KeyBERT or an actual LLM client.
"""

import pytest

from src.ai.tagging import SmartTaggingSystem


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeAI:
    def __init__(self, response: str = '["alpha", "beta"]'):
        self.response = response

    def generate(self, prompt: str) -> str:
        return self.response


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tagger():
    return SmartTaggingSystem(ai_client=_FakeAI(), db_client=None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTagging:
    def test_get_type_tags_returns_extension_tag(self, tagger):
        tags = tagger._get_type_tags("/tmp/example.pdf")
        assert tags == ["type:pdf"]

    def test_get_type_tags_returns_empty_for_no_extension(self, tagger):
        tags = tagger._get_type_tags("/tmp/Makefile")
        assert tags == []

    def test_get_context_tags_extracts_folder_and_date(self, tagger):
        tags = tagger._get_context_tags({
            "folder": "Projects",
            "year": 2025,
            "month": 7,
        })
        assert "folder:Projects" in tags
        assert "year:2025" in tags
        assert "month:7" in tags

    def test_ai_generate_tags_parses_json_list(self, tagger):
        tags = tagger._ai_generate_tags("Some long content. " * 50)
        assert tags == ["alpha", "beta"]

    def test_ai_generate_tags_handles_invalid_json(self, tagger):
        tagger.ai = _FakeAI(response="not json")
        tags = tagger._ai_generate_tags("Some long content. " * 50)
        assert tags == []

    def test_store_and_search_by_tags(self, tagger):
        tagger._store_tags("/tmp/a.txt", {"python", "ai"})
        tagger._store_tags("/tmp/b.txt", {"rust", "ai"})
        tagger._store_tags("/tmp/c.txt", {"rust"})

        # search_by_tags = ANY match
        results = tagger.search_by_tags(["rust"])
        assert "/tmp/b.txt" in results
        assert "/tmp/c.txt" in results
        assert "/tmp/a.txt" not in results

        # search_by_all_tags = ALL match
        all_results = tagger.search_by_all_tags(["rust", "ai"])
        assert "/tmp/b.txt" in all_results
        assert "/tmp/c.txt" not in all_results
