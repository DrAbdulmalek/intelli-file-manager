"""خادم API لـ IntelliFile Manager — FastAPI + WebSocket

REST API + WebSocket endpoints for the IntelliFile Manager:
  - File management: classify, organize, search
  - Hybrid search: BM25 + Semantic + RRF
  - Smart tagging: auto-tag, manual tags, tag search
  - File Copilot: RAG chat with files (WebSocket for streaming)
  - Multimodal processing: images, audio, video, documents
  - Medical NER: extract medical entities from Arabic text
  - Health check: engine availability

All endpoints support Arabic RTL content natively.
Privacy-first: all processing is local, no data leaves the device.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path sandboxing — security: only allow paths under configured directories
# ---------------------------------------------------------------------------

_ALLOWED_DIRS: list[Path] | None = None
_MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB
_MAX_WS_MESSAGE_SIZE = 10 * 1024  # 10 KB


def _get_allowed_dirs() -> list[Path]:
    """Get and cache the list of allowed directories."""
    global _ALLOWED_DIRS
    if _ALLOWED_DIRS is not None:
        return _ALLOWED_DIRS
    dirs_str = os.environ.get(
        "INTELLIFILE_ALLOWED_DIRS",
        os.path.join(os.getcwd(), "data"),
    )
    _ALLOWED_DIRS = [
        Path(d.strip()).resolve()
        for d in dirs_str.split(",")
        if d.strip()
    ]
    _ALLOWED_DIRS.append(Path.cwd().resolve())
    return _ALLOWED_DIRS


def _validate_path(path_str: str, must_exist: bool = True) -> Path:
    """Validate that a path is within allowed directories (sandboxing).

    Raises HTTPException(403) if the path escapes the sandbox.
    """
    resolved = Path(path_str).resolve()
    allowed = _get_allowed_dirs()
    if not any(resolved.is_relative_to(allowed_dir) for allowed_dir in allowed):
        raise HTTPException(
            status_code=403,
            detail="المسار خارج المجلدات المسموح بها",
        )
    if must_exist and not resolved.exists():
        raise HTTPException(status_code=400, detail=f"المسار غير موجود: {resolved}")
    return resolved


def _sanitize_filename(filename: str) -> str:
    """Sanitize an uploaded filename to prevent path traversal.

    Strips directory components and rejects suspicious names.
    """
    # Strip directory components
    safe_name = Path(filename).name
    # Replace non-alphanumeric (except dots, dashes, underscores, Arabic chars)
    safe_name = re.sub(r'[^\w\.\-\u0600-\u06FF]', '_', safe_name)
    if not safe_name or safe_name.startswith('.'):
        raise HTTPException(400, "اسم الملف غير صالح")
    return safe_name


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ClassifyRequest(BaseModel):
    path: str = Field(..., description="مسار الملف أو المجلد")
    recursive: bool = Field(True, description="تصنيف متكرر")

class ClassifyResponse(BaseModel):
    results: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="نص البحث")
    top_k: int = Field(10, ge=1, le=100)
    engine: str = Field("hybrid", description="hybrid | bm25 | semantic")

class TagRequest(BaseModel):
    filepath: str = Field(..., description="مسار الملف")
    tag: str = Field(..., description="اسم الوسم")
    category: str = Field("manual", description="فئة الوسم")

class BatchTagRequest(BaseModel):
    filepaths: list[str] = Field(..., description="قائمة مسارات الملفات")
    tag: str = Field(..., description="اسم الوسم")
    category: str = Field("manual", description="فئة الوسم")

class CopilotMessage(BaseModel):
    message: str = Field(..., min_length=1, description="رسالة المستخدم")
    conversation_id: Optional[str] = Field(None, description="معرف المحادثة")

class NerRequest(BaseModel):
    text: str = Field(..., min_length=1, description="النص الطبي")
    use_llm: bool = Field(False, description="استخدام LLM للتحسين")

class OrganizeRequest(BaseModel):
    source_dir: str = Field(..., description="مجلد المصدر")
    target_dir: str = Field("", description="مجلد الهدف")
    dry_run: bool = Field(True, description="عرض فقط بدون نقل")
    move_files: bool = Field(False, description="نقل بدلاً من نسخ")

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "2.0.0"
    engines: dict[str, bool] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Create the IntelliFile Manager FastAPI application."""
    _app = FastAPI(
        title="IntelliFile Manager API",
        description="إدارة ملفات ذكية — بحث هجين، وسوم ذكية، مساعد ملفات، NER طبي",
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    _app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:8420",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Lazy-loaded engines
    _engines: dict[str, Any] = {}

    def _get_engine(name: str):
        if name in _engines:
            return _engines[name]

        if name == "classifier":
            from src.core.classifier import SmartFileClassifier
            _engines[name] = SmartFileClassifier()

        elif name == "hybrid_search":
            from src.core.hybrid_search import HybridSearchEngine
            _engines[name] = HybridSearchEngine()

        elif name == "tagger":
            from src.core.smart_tagger import SmartTagger
            _engines[name] = SmartTagger()

        elif name == "copilot":
            from src.core.file_copilot import FileCopilot
            _engines[name] = FileCopilot()

        elif name == "multimodal":
            from src.core.enhanced_multimodal import EnhancedMultimodalProcessor
            _engines[name] = EnhancedMultimodalProcessor()

        elif name == "ner":
            from src.core.medical_ner import ArabicMedicalNER
            _engines[name] = ArabicMedicalNER()

        elif name == "file_handler":
            from src.core.file_handler import FileHandler
            _engines[name] = FileHandler()

        return _engines.get(name)

    # -------------------------------------------------------------------
    # Health
    # -------------------------------------------------------------------

    @_app.get("/api/health", response_model=HealthResponse)
    async def health():
        engines = {}
        for name in ["classifier", "hybrid_search", "tagger", "copilot", "multimodal", "ner"]:
            try:
                eng = _get_engine(name)
                engines[name] = eng is not None
            except Exception:
                engines[name] = False

        # Check Ollama (async)
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                r = await client.get("http://localhost:11434/api/tags", timeout=3.0)
                engines["ollama"] = r.status_code == 200
        except Exception:
            engines["ollama"] = False

        return HealthResponse(status="ok", version="2.0.0", engines=engines)

    # -------------------------------------------------------------------
    # Classify
    # -------------------------------------------------------------------

    @_app.post("/api/classify", response_model=ClassifyResponse)
    async def classify(req: ClassifyRequest):
        clf = _get_engine("classifier")
        if not clf:
            raise HTTPException(500, "Classifier engine unavailable")

        # Security: validate path is within allowed directories
        path = _validate_path(req.path)

        if path.is_file():
            result = clf.classify_file(str(path))
            return ClassifyResponse(results=[result], total=1)
        elif path.is_dir():
            results = clf.batch_classify(str(path)) if req.recursive else []
            return ClassifyResponse(results=results, total=len(results))
        else:
            raise HTTPException(400, "المسار ليس ملفاً أو مجلداً")

    # -------------------------------------------------------------------
    # Hybrid Search
    # -------------------------------------------------------------------

    @_app.post("/api/search")
    async def search(req: SearchRequest):
        search_eng = _get_engine("hybrid_search")
        if not search_eng:
            raise HTTPException(500, "Search engine unavailable")

        if req.engine == "bm25":
            results = search_eng.bm25.search(req.query, top_k=req.top_k)
            doc_ids = search_eng._doc_ids
            doc_texts = search_eng._doc_texts
            formatted = []
            for idx, score in results:
                if idx < len(doc_ids):
                    doc_id = doc_ids[idx]
                    formatted.append({
                        "id": doc_id,
                        "text": doc_texts.get(doc_id, "")[:500],
                        "score": round(score, 4),
                        "engine": "bm25",
                    })
            return {"query": req.query, "results": formatted, "engine": "bm25", "total": len(formatted)}

        elif req.engine == "semantic":
            results = search_eng.semantic.search(req.query, top_k=req.top_k)
            formatted = []
            for doc_id, score in results:
                formatted.append({
                    "id": doc_id,
                    "text": search_eng._doc_texts.get(doc_id, "")[:500],
                    "score": round(score, 4),
                    "engine": "semantic",
                })
            return {"query": req.query, "results": formatted, "engine": "semantic", "total": len(formatted)}

        else:  # hybrid (default)
            results = search_eng.search(req.query, top_k=req.top_k)
            return {"query": req.query, "results": results, "engine": "hybrid", "total": len(results)}

    @_app.post("/api/search/index")
    async def index_directory(directory: str = Query(...), extensions: str = Query("")):
        search_eng = _get_engine("hybrid_search")
        if not search_eng:
            raise HTTPException(500, "Search engine unavailable")
        # Security: validate directory path
        _validate_path(directory)
        exts = tuple(extensions.split(",")) if extensions else None
        count = search_eng.index_files(directory, extensions=exts)
        return {"indexed": count, "directory": directory}

    # -------------------------------------------------------------------
    # Smart Tags
    # -------------------------------------------------------------------

    @_app.post("/api/tags/auto")
    async def auto_tag(filepath: str = Query(...)):
        tagger = _get_engine("tagger")
        if not tagger:
            raise HTTPException(500, "Tagger engine unavailable")
        # Security: validate path
        _validate_path(filepath)
        ft = tagger.auto_tag(filepath)
        return ft.to_dict()

    @_app.post("/api/tags/add")
    async def add_tag(req: TagRequest):
        tagger = _get_engine("tagger")
        if not tagger:
            raise HTTPException(500, "Tagger engine unavailable")
        # Security: validate path
        _validate_path(req.filepath)
        tagger.add_manual_tag(req.filepath, req.tag, req.category)
        ft = tagger.get_tags(req.filepath)
        return ft.to_dict()

    @_app.post("/api/tags/batch")
    async def batch_tag(req: BatchTagRequest):
        tagger = _get_engine("tagger")
        if not tagger:
            raise HTTPException(500, "Tagger engine unavailable")
        # Security: validate all paths
        for fp in req.filepaths:
            _validate_path(fp)
        count = tagger.batch_tag(req.filepaths, req.tag, req.category)
        return {"tagged": count, "tag": req.tag}

    @_app.delete("/api/tags/remove")
    async def remove_tag(filepath: str = Query(...), tag: str = Query(...)):
        tagger = _get_engine("tagger")
        if not tagger:
            raise HTTPException(500, "Tagger engine unavailable")
        # Security: validate path
        _validate_path(filepath)
        removed = tagger.remove_tag(filepath, tag)
        return {"removed": removed}

    @_app.get("/api/tags/search")
    async def search_tags(directory: str = Query(...), tag: str = Query(...)):
        tagger = _get_engine("tagger")
        if not tagger:
            raise HTTPException(500, "Tagger engine unavailable")
        # Security: validate directory
        _validate_path(directory)
        files = tagger.search_by_tag(directory, tag)
        return {"tag": tag, "files": files, "count": len(files)}

    @_app.get("/api/tags/all")
    async def get_all_tags(directory: str = Query(...)):
        tagger = _get_engine("tagger")
        if not tagger:
            raise HTTPException(500, "Tagger engine unavailable")
        # Security: validate directory
        _validate_path(directory)
        return tagger.get_all_tags(directory)

    # -------------------------------------------------------------------
    # File Copilot (RAG Chat)
    # -------------------------------------------------------------------

    @_app.post("/api/copilot/chat")
    async def copilot_chat(req: CopilotMessage):
        copilot = _get_engine("copilot")
        if not copilot:
            raise HTTPException(500, "Copilot engine unavailable")
        return copilot.chat(req.message, req.conversation_id)

    @_app.post("/api/copilot/index")
    async def copilot_index(filepaths: list[str]):
        copilot = _get_engine("copilot")
        if not copilot:
            raise HTTPException(500, "Copilot engine unavailable")
        # Security: validate all file paths
        for fp in filepaths:
            _validate_path(fp)
        count = copilot.index_files(filepaths)
        return {"indexed": count}

    @_app.get("/api/copilot/conversations")
    async def copilot_conversations():
        copilot = _get_engine("copilot")
        if not copilot:
            raise HTTPException(500, "Copilot engine unavailable")
        return copilot.list_conversations()

    @_app.post("/api/copilot/summarize")
    async def copilot_summarize(filepath: str = Query(...)):
        copilot = _get_engine("copilot")
        if not copilot:
            raise HTTPException(500, "Copilot engine unavailable")
        # Security: validate path
        _validate_path(filepath)
        return {"summary": copilot.summarize_file(filepath)}

    # WebSocket for streaming copilot chat
    @_app.websocket("/api/copilot/ws")
    async def copilot_ws(websocket: WebSocket):
        # Security: validate origin
        origin = websocket.headers.get("origin", "")
        allowed_origins = ["http://localhost:3000", "http://localhost:3001", "http://localhost:8420"]
        if origin and origin not in allowed_origins:
            await websocket.close(code=4003, reason="Origin not allowed")
            return

        await websocket.accept()
        copilot = _get_engine("copilot")
        try:
            while True:
                data = await websocket.receive_json()
                message = data.get("message", "")
                # Security: limit message size
                if len(message) > _MAX_WS_MESSAGE_SIZE:
                    await websocket.send_json({"error": "Message too large"})
                    continue
                conv_id = data.get("conversation_id")
                if copilot and message:
                    result = copilot.chat(message, conv_id)
                    await websocket.send_json(result)
                else:
                    await websocket.send_json({"error": "Invalid message"})
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as exc:
            logger.error("WebSocket error: %s", exc)

    # -------------------------------------------------------------------
    # Multimodal Processing
    # -------------------------------------------------------------------

    @_app.post("/api/process/image")
    async def process_image(filepath: str = Query(...), fix_scan: bool = Query(True)):
        mm = _get_engine("multimodal")
        if not mm:
            raise HTTPException(500, "Multimodal processor unavailable")
        # Security: validate path
        _validate_path(filepath)
        return mm.process_image(filepath, fix_scan=fix_scan)

    @_app.post("/api/process/audio")
    async def process_audio(filepath: str = Query(...)):
        mm = _get_engine("multimodal")
        if not mm:
            raise HTTPException(500, "Multimodal processor unavailable")
        # Security: validate path
        _validate_path(filepath)
        return mm.process_audio(filepath)

    @_app.post("/api/process/video")
    async def process_video(filepath: str = Query(...)):
        mm = _get_engine("multimodal")
        if not mm:
            raise HTTPException(500, "Multimodal processor unavailable")
        # Security: validate path
        _validate_path(filepath)
        return mm.process_video(filepath)

    @_app.post("/api/process/document")
    async def process_document(filepath: str = Query(...)):
        mm = _get_engine("multimodal")
        if not mm:
            raise HTTPException(500, "Multimodal processor unavailable")
        # Security: validate path
        _validate_path(filepath)
        return mm.process_document(filepath)

    @_app.post("/api/process/upload")
    async def upload_and_process(file: UploadFile = File(...)):
        """Upload a file and process it based on its type."""
        # Security: sanitize filename to prevent path traversal
        safe_name = _sanitize_filename(file.filename)

        # Check file size
        content = await file.read()
        if len(content) > _MAX_UPLOAD_SIZE:
            raise HTTPException(400, "حجم الملف يتجاوز الحد المسموح (100MB)")

        tmp_dir = Path.home() / ".intellifile" / "uploads"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / safe_name
        with open(tmp_path, "wb") as f:
            f.write(content)

        mm = _get_engine("multimodal")
        if not mm:
            raise HTTPException(500, "Multimodal processor unavailable")

        ext = Path(safe_name).suffix.lower()
        try:
            if ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp", ".gif"):
                return mm.process_image(str(tmp_path))
            elif ext in (".mp3", ".wav", ".ogg", ".flac", ".m4a"):
                return mm.process_audio(str(tmp_path))
            elif ext in (".mp4", ".avi", ".mkv", ".mov"):
                return mm.process_video(str(tmp_path))
            elif ext in (".pdf", ".docx", ".xlsx", ".txt"):
                return mm.process_document(str(tmp_path))
            else:
                return {"path": str(tmp_path), "type": "unknown", "name": safe_name}
        finally:
            # Clean up temp file after processing
            try:
                tmp_path.unlink()
            except Exception:
                pass

    # -------------------------------------------------------------------
    # Medical NER
    # -------------------------------------------------------------------

    @_app.post("/api/ner/extract")
    async def ner_extract(req: NerRequest):
        ner = _get_engine("ner")
        if not ner:
            raise HTTPException(500, "NER engine unavailable")
        if req.use_llm:
            result = ner.extract_with_llm(req.text)
        else:
            result = ner.extract(req.text)
        return {
            "entities": [{"text": e.text, "type": e.entity_type,
                          "confidence": e.confidence, "source": e.source}
                         for e in result.entities],
            "patient_name": result.patient_name,
            "patient_id": result.patient_id,
            "diagnosis": result.diagnosis,
            "medications": result.medications,
            "procedures": result.procedures,
            "summary": result.summary,
        }

    # -------------------------------------------------------------------
    # Organize
    # -------------------------------------------------------------------

    @_app.post("/api/organize")
    async def organize(req: OrganizeRequest):
        fh = _get_engine("file_handler")
        clf = _get_engine("classifier")
        if not fh or not clf:
            raise HTTPException(500, "File handler or classifier unavailable")

        # Security: validate paths are within allowed directories
        source = _validate_path(req.source_dir)
        target = _validate_path(req.target_dir, must_exist=False) if req.target_dir else source

        if not source.is_dir():
            raise HTTPException(400, f"مجلد المصدر غير موجود: {req.source_dir}")

        organized: dict[str, list[str]] = {}
        errors: list[str] = []
        total = 0

        for item in source.iterdir():
            if not item.is_file():
                continue
            total += 1
            try:
                result = clf.classify_file(str(item))
                category = result.get("category", "أخرى")
                # Security: sanitize category for use as path component
                if not _SAFE_CATEGORY_RE.match(category):
                    category = "أخرى"
                organized.setdefault(category, []).append(item.name)

                if not req.dry_run:
                    fh.move_file(str(item), category, str(target))
            except Exception:
                errors.append(f"{item.name}: error during processing")

        return {
            "organized": organized,
            "dry_run": req.dry_run,
            "total_files": total,
            "errors": errors,
        }

    # -------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------

    @_app.get("/api/stats")
    async def get_stats():
        from src.core.config import CATEGORIES
        return {
            "categories": CATEGORIES,
            "version": "2.0.0",
        }

    return _app


# Safe category pattern (Arabic + alphanumeric + dash/underscore)
_SAFE_CATEGORY_RE = re.compile(r"^[\w\-\u0600-\u06FF]+$")


# When run directly: uvicorn src.api.server:app --port 8421
app = create_app()
