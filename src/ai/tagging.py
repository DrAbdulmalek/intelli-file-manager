"""
Smart Tagging System — auto-generate descriptive tags for files.

This is a STUB file proposing the API for the smart tagging system described
in docs/DEVELOPMENT_ROADMAP.md (Task 2.1).

Inspired by: TagSpaces (tag-based organization).
"""

import json
from typing import List, Dict, Any, Set, Optional


class SmartTaggingSystem:
    """
    Smart tagging system inspired by TagSpaces.

    Tags come from 4 sources:
      1. Content keywords (KeyBERT)
      2. File type
      3. Context (folder, date, etc.)
      4. AI-generated tags (LLM call on long content)
    """

    def __init__(self, ai_client=None, db_client=None):
        self.ai = ai_client
        self.db = db_client
        self.tag_library: Dict[str, Dict[str, Any]] = {}  # {tag_name: tag_info}
        self.file_tags: Dict[str, Set[str]] = {}           # {file_path: {tag, ...}}

    # ------------------------------------------------------------------
    # Tag generation
    # ------------------------------------------------------------------
    def generate_tags(
        self,
        file_path: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Generate smart tags for a file from all 4 sources."""
        metadata = metadata or {}
        tags: Set[str] = set()

        # 1. Content keywords
        tags.update(self._extract_keywords(content))

        # 2. File-type tags
        tags.update(self._get_type_tags(file_path))

        # 3. Context tags (folder, date, etc.)
        tags.update(self._get_context_tags(metadata))

        # 4. AI-generated tags for long content
        if len(content) > 100:
            tags.update(self._ai_generate_tags(content))

        # Persist
        self._store_tags(file_path, tags)
        return list(tags)

    # ------------------------------------------------------------------
    # Tag sources
    # ------------------------------------------------------------------
    def _extract_keywords(self, text: str, top_k: int = 5) -> List[str]:
        """Extract keywords using KeyBERT.

        TODO: lazy-import keybert and run extraction.
        """
        if not text:
            return []
        # from keybert import KeyBERT
        # kw_model = KeyBERT()
        # keywords = kw_model.extract_keywords(
        #     text,
        #     keyphrase_ngram_range=(1, 2),
        #     stop_words='english',
        #     top_n=top_k,
        # )
        # return [kw for kw, score in keywords]
        return []  # placeholder

    def _get_type_tags(self, file_path: str) -> List[str]:
        """Derive tags from file extension."""
        import os
        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
        if not ext:
            return []
        return [f"type:{ext}"]

    def _get_context_tags(self, metadata: Dict[str, Any]) -> List[str]:
        """Derive tags from metadata (folder, date, etc.)."""
        tags: List[str] = []
        if "folder" in metadata:
            tags.append(f"folder:{metadata['folder']}")
        if "year" in metadata:
            tags.append(f"year:{metadata['year']}")
        if "month" in metadata:
            tags.append(f"month:{metadata['month']}")
        return tags

    def _ai_generate_tags(self, content: str) -> List[str]:
        """Ask the LLM to produce 3-5 descriptive tags."""
        if self.ai is None:
            return []
        prompt = (
            "Generate 3-5 descriptive tags for the following text content. "
            "Tags should be single words or short phrases. "
            "Return only the tags as a JSON list.\n\n"
            f"Content: {content[:500]}"
        )
        response = self.ai.generate(prompt)
        try:
            tags = json.loads(response)
            if isinstance(tags, list):
                return [str(t) for t in tags]
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    # ------------------------------------------------------------------
    # Tag storage & search
    # ------------------------------------------------------------------
    def _store_tags(self, file_path: str, tags: Set[str]) -> None:
        self.file_tags[file_path] = tags
        # TODO: persist to self.db

    def search_by_tags(self, tags: List[str]) -> List[str]:
        """Return file paths that have ANY of the given tags."""
        result: List[str] = []
        for file_path, file_tags in self.file_tags.items():
            if any(tag in file_tags for tag in tags):
                result.append(file_path)
        return result

    def search_by_all_tags(self, tags: List[str]) -> List[str]:
        """Return file paths that have ALL of the given tags."""
        tags_set = set(tags)
        return [
            file_path
            for file_path, file_tags in self.file_tags.items()
            if tags_set.issubset(file_tags)
        ]
