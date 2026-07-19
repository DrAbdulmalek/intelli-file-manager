"""
File Copilot — chat with a single file.

This is a STUB file proposing the API for the "File as Copilot" feature
described in docs/DEVELOPMENT_ROADMAP.md (Task 2.2).

The copilot lets a user ask questions about a specific file (PDF, document,
spreadsheet, etc.) and get answers grounded strictly in that file's content
(no hallucination).
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
import asyncio
import hashlib


class FileCopilot:
    """
    File-as-Copilot: per-file chat sessions grounded in file content via RAG.
    """

    def __init__(self, rag_engine, llm_client):
        self.rag = rag_engine
        self.llm = llm_client
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    async def start_session(self, file_path: str) -> str:
        """Start a new chat session for a file. Returns session_id."""
        # Index the file in RAG if not already indexed
        if not self.rag.is_indexed(file_path):
            await self.rag.index_file(file_path)

        session_id = self._make_session_id(file_path)
        self.active_sessions[session_id] = {
            "file_path": file_path,
            "history": [],
            "context": self.rag.get_file_context(file_path),
            "started_at": datetime.utcnow().isoformat(),
        }
        return session_id

    async def ask(self, session_id: str, question: str) -> str:
        """Ask a question in an existing session."""
        session = self.active_sessions.get(session_id)
        if session is None:
            return "Error: Session not found. Call start_session(file_path) first."

        # Retrieve relevant chunks from the file
        relevant_chunks = self.rag.retrieve(
            session["file_path"],
            question,
            top_k=5,
        )
        context = "\n\n".join(chunk.get("text", "") for chunk in relevant_chunks)

        prompt = self._build_prompt(context=context, question=question)
        response = await self.llm.generate_async(prompt)

        session["history"].append({
            "question": question,
            "answer": response,
            "timestamp": datetime.utcnow().isoformat(),
        })
        return response

    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        session = self.active_sessions.get(session_id)
        return session["history"] if session else []

    def end_session(self, session_id: str) -> bool:
        return self.active_sessions.pop(session_id, None) is not None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _make_session_id(self, file_path: str) -> str:
        digest = hashlib.sha1(file_path.encode("utf-8")).hexdigest()[:8]
        return f"copilot_{digest}"

    def _build_prompt(self, context: str, question: str) -> str:
        return (
            "You are an AI assistant helping a user understand a document. "
            "Answer the user's question based ONLY on the provided context. "
            'If the answer is not in the context, say "I don\'t have enough '
            'information to answer that."\n\n'
            f"Context from the document:\n{context}\n\n"
            f"User Question: {question}\n\n"
            "Answer:"
        )
