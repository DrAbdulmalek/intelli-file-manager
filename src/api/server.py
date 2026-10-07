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
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Security, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path sandboxing — security: only allow paths under configured directories
# ---------------------------------------------------------------------------

_ALLOWED_DIRS: list[Path] | None = None
_MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB
_MAX_WS_MESSAGE_SIZE = 10 * 1024  # 10 KB

# ---------------------------------------------------------------------------
# Optional API key authentication
# Set INTELLIFILE_API_KEY env var to enable. When not set, auth is skipped
# (safe for localhost-only use). When set, all endpoints require the header
# X-API-Key: <value>.
# ---------------------------------------------------------------------------
_API_KEY = os.environ.get("INTELLIFILE_API_KEY", "")
_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _verify_api_key(api_key: str = Security(_api_key_scheme)) -> str:
    """Dependency that enforces API key when INTELLIFILE_API_KEY is configured."""
    if not _API_KEY:
        # No API key configured — skip auth (localhost-only is the default)
        return "anonymous"
    if api_key == _API_KEY:
        return api_key[:4] + "..."
    raise HTTPException(
        status_code=401,
        detail="مفتاح API غير صالح — اضبط X-API-Key في رأس الطلب",
    )


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

# --- Training snippets (قصاصات قابلة للتدريب) --------------------------

class BBoxModel(BaseModel):
    x1: int = Field(ge=0)
    y1: int = Field(ge=0)
    x2: int = Field(ge=0)
    y2: int = Field(ge=0)

class SnippetCreate(BaseModel):
    source_image: str = Field(..., description="مسار الصورة الأصلية")
    bbox: BBoxModel
    level: str = Field("word", description="word | line | block | character")
    text: str = Field("", description="النص الصحيح")
    ocr_text: str = Field("", description="نص OCR الخام")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="0.0 = غير معروفة")
    language: str = Field("ar")
    category: str = Field("general", description="medical | general | formula | table")

class SnippetUpdate(BaseModel):
    bbox: Optional[BBoxModel] = None
    text: Optional[str] = None
    category: Optional[str] = None

class SnippetReview(BaseModel):
    verified_by: str = Field("", description="من راجع القصاصة")
    reason: str = Field("", description="سبب الرفض (للرفض فقط)")

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
        description="إدارة ملفات ذكية — بحث هجين، وسوم ذكية، مساعد ملفات",
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
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["X-API-Key", "Content-Type"],
    )

    # -----------------------------------------------------------------
    # Lightweight mode (وضع خفيف بلا LLM) — INTELLIFILE_LIGHTWEIGHT=1
    # يمنع تهيئة محركات الـLLM/التضمين؛ البحث يعمل BM25 فقط والتصنيف
    # بالقواعد. مفيد للأجهزة الضعيفة أو أول تشغيل قبل تنزيل Ollama.
    # -----------------------------------------------------------------
    lightweight = os.environ.get("INTELLIFILE_LIGHTWEIGHT", "").strip() in ("1", "true", "yes")

    # -----------------------------------------------------------------
    # Simple in-process rate limiting (slowapi-free, per-client sliding window)
    # -----------------------------------------------------------------
    _rate_buckets: dict[str, list[float]] = {}
    _RATE_LIMIT = int(os.environ.get("INTELLIFILE_RATE_LIMIT", "120"))  # requests
    _RATE_WINDOW = float(os.environ.get("INTELLIFILE_RATE_WINDOW", "60.0"))  # seconds

    @ _app.middleware("http")
    async def _rate_limit_middleware(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            client = request.client.host if request.client else "unknown"
            now = time.time()
            bucket = _rate_buckets.setdefault(client, [])
            # drop stale entries
            bucket[:] = [t for t in bucket if now - t < _RATE_WINDOW]
            if len(bucket) >= _RATE_LIMIT:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "تم تجاوز حد الطلبات — حاول لاحقًا (rate limit)"},
                )
            bucket.append(now)
        return await call_next(request)

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
            if lightweight:
                _engines[name] = None  # وضع خفيف — بلا LLM
            else:
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

        elif name == "embeddings":
            if lightweight:
                _engines[name] = None  # وضع خفيف — بلا تضمينات دلالية
            else:
                from src.ai.embeddings import EmbeddingEngine
                _engines[name] = EmbeddingEngine(model_name="paraphrase-multilingual-MiniLM-L12-v2")

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

        # Check EmbeddingEngine (sentence-transformers)
        try:
            emb = _get_engine("embeddings")
            if emb:
                emb.load()
                engines["embeddings"] = emb.is_loaded
                engines["embedding_model"] = emb.model_name
                engines["embedding_dimension"] = emb.dimension
            else:
                engines["embeddings"] = False
        except Exception:
            engines["embeddings"] = False

        # Check Ollama (async) — skipped entirely in lightweight mode
        engines["ollama"] = False
        if not lightweight:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    r = await client.get("http://localhost:11434/api/tags", timeout=3.0)
                    engines["ollama"] = r.status_code == 200
            except Exception:
                engines["ollama"] = False
        engines["lightweight_mode"] = lightweight

        return HealthResponse(status="ok", version="2.1.0", engines=engines)

    # -------------------------------------------------------------------
    # Lightweight-mode flag is exposed via /api/health engines dict
    # (checked by the web app to hide LLM-only features).
    # -------------------------------------------------------------------
    @_app.get("/api/health/mode")
    async def health_mode():
        return {"lightweight": lightweight}

    # -------------------------------------------------------------------
    # Embeddings (sentence-transformers)
    # -------------------------------------------------------------------

    @_app.post("/api/embed")
    async def embed_texts(texts: list[str], _auth: str = Depends(_verify_api_key)):
        """توليد التمثيلات المتجهية للنصوص باستخدام sentence-transformers.

        يدعم العربية والإنجليزية مع نموذج paraphrase-multilingual-MiniLM-L12-v2.
        """
        emb = _get_engine("embeddings")
        if not emb:
            raise HTTPException(503, "محرك التمثيل المتجهي غير متاح. ثبّت sentence-transformers.")
        try:
            emb.load()
            vectors = emb.encode_batch(texts)
            return {
                "embeddings": vectors,
                "count": len(vectors),
                "model": emb.model_name,
                "dimension": emb.dimension,
            }
        except Exception as exc:
            raise HTTPException(500, f"فشل التمثيل المتجهي: {exc}")

    @_app.post("/api/embed/similarity")
    async def compute_similarity(text1: str = Query(...), text2: str = Query(...), _auth: str = Depends(_verify_api_key)):
        """حساب التشابه الدلالي بين نصين."""
        emb = _get_engine("embeddings")
        if not emb:
            raise HTTPException(503, "محرك التمثيل المتجهي غير متاح")
        try:
            emb.load()
            sim = emb.similarity(text1, text2)
            return {"similarity": sim, "text1": text1[:50], "text2": text2[:50]}
        except Exception as exc:
            raise HTTPException(500, f"فشل حساب التشابه: {exc}")

    # -------------------------------------------------------------------
    # Classify
    # -------------------------------------------------------------------

    @_app.post("/api/classify", response_model=ClassifyResponse)
    async def classify(req: ClassifyRequest, _auth: str = Depends(_verify_api_key)):
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
    async def search(req: SearchRequest, _auth: str = Depends(_verify_api_key)):
        search_eng = _get_engine("hybrid_search")
        if not search_eng:
            raise HTTPException(500, "Search engine unavailable")

        # Auto-wire sentence-transformers for semantic search
        if req.engine in ("semantic", "hybrid"):
            try:
                emb = _get_engine("embeddings")
                if emb and emb.is_loaded and hasattr(search_eng, 'wire_embeddings'):
                    search_eng.wire_embeddings(emb.encode, emb.dimension)
            except Exception:
                pass

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
    async def index_directory(directory: str = Query(...), extensions: str = Query(""), _auth: str = Depends(_verify_api_key)):
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
    async def auto_tag(filepath: str = Query(...), _auth: str = Depends(_verify_api_key)):
        tagger = _get_engine("tagger")
        if not tagger:
            raise HTTPException(500, "Tagger engine unavailable")
        # Security: validate path
        _validate_path(filepath)
        ft = tagger.auto_tag(filepath)
        return ft.to_dict()

    @_app.post("/api/tags/add")
    async def add_tag(req: TagRequest, _auth: str = Depends(_verify_api_key)):
        tagger = _get_engine("tagger")
        if not tagger:
            raise HTTPException(500, "Tagger engine unavailable")
        # Security: validate path
        _validate_path(req.filepath)
        tagger.add_manual_tag(req.filepath, req.tag, req.category)
        ft = tagger.get_tags(req.filepath)
        return ft.to_dict()

    @_app.post("/api/tags/batch")
    async def batch_tag(req: BatchTagRequest, _auth: str = Depends(_verify_api_key)):
        tagger = _get_engine("tagger")
        if not tagger:
            raise HTTPException(500, "Tagger engine unavailable")
        # Security: validate all paths
        for fp in req.filepaths:
            _validate_path(fp)
        count = tagger.batch_tag(req.filepaths, req.tag, req.category)
        return {"tagged": count, "tag": req.tag}

    @_app.delete("/api/tags/remove")
    async def remove_tag(filepath: str = Query(...), tag: str = Query(...), _auth: str = Depends(_verify_api_key)):
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
    async def copilot_chat(req: CopilotMessage, _auth: str = Depends(_verify_api_key)):
        copilot = _get_engine("copilot")
        if not copilot:
            raise HTTPException(500, "Copilot engine unavailable")
        return copilot.chat(req.message, req.conversation_id)

    @_app.post("/api/copilot/index")
    async def copilot_index(filepaths: list[str], _auth: str = Depends(_verify_api_key)):
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
    async def copilot_summarize(filepath: str = Query(...), _auth: str = Depends(_verify_api_key)):
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
    async def process_image(filepath: str = Query(...), fix_scan: bool = Query(True), _auth: str = Depends(_verify_api_key)):
        mm = _get_engine("multimodal")
        if not mm:
            raise HTTPException(500, "Multimodal processor unavailable")
        # Security: validate path
        _validate_path(filepath)
        return mm.process_image(filepath, fix_scan=fix_scan)

    @_app.post("/api/process/audio")
    async def process_audio(filepath: str = Query(...), _auth: str = Depends(_verify_api_key)):
        mm = _get_engine("multimodal")
        if not mm:
            raise HTTPException(500, "Multimodal processor unavailable")
        # Security: validate path
        _validate_path(filepath)
        return mm.process_audio(filepath)

    @_app.post("/api/process/video")
    async def process_video(filepath: str = Query(...), _auth: str = Depends(_verify_api_key)):
        mm = _get_engine("multimodal")
        if not mm:
            raise HTTPException(500, "Multimodal processor unavailable")
        # Security: validate path
        _validate_path(filepath)
        return mm.process_video(filepath)

    @_app.post("/api/process/document")
    async def process_document(filepath: str = Query(...), _auth: str = Depends(_verify_api_key)):
        mm = _get_engine("multimodal")
        if not mm:
            raise HTTPException(500, "Multimodal processor unavailable")
        # Security: validate path
        _validate_path(filepath)
        return mm.process_document(filepath)

    @_app.post("/api/process/upload")
    async def upload_and_process(file: UploadFile = File(...), _auth: str = Depends(_verify_api_key)):
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
    async def ner_extract(req: NerRequest, _auth: str = Depends(_verify_api_key)):
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
    async def organize(req: OrganizeRequest, _auth: str = Depends(_verify_api_key)):
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
    async def get_stats(_auth: str = Depends(_verify_api_key)):
        from src.core.config import CATEGORIES
        return {
            "categories": CATEGORIES,
            "version": "2.0.0",
        }

    # -------------------------------------------------------------------
    # File serving for the OCR snippet editor (sandboxed by _validate_path)
    # -------------------------------------------------------------------

    @_app.get("/api/file/serve")
    async def file_serve(filepath: str = Query(..., description="مسار الصورة داخل المجلدات المسموحة")):
        """يخدم صورة من المجلدات المسموحة لمحرر القصاصات (لا يخرج عن الـsandbox)."""
        from fastapi.responses import FileResponse
        try:
            validated = _validate_path(filepath, must_exist=True)
        except HTTPException:
            raise
        suffix = validated.suffix.lower()
        media = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".bmp": "image/bmp", ".gif": "image/gif",
            ".tif": "image/tiff", ".tiff": "image/tiff",
        }.get(suffix)
        if media is None:
            raise HTTPException(400, "الملف ليس صورة مدعومة")
        return FileResponse(validated, media_type=media)

    # -------------------------------------------------------------------
    # Training snippets (قصاصات قابلة للتدريب) + المسارد الطبية
    # -------------------------------------------------------------------

    @_app.post("/api/snippets")
    async def create_snippet(req: SnippetCreate, _auth: str = Depends(_verify_api_key)):
        from src.db.snippet_db import SnippetDB, TrainingSnippet
        if req.bbox.x2 <= req.bbox.x1 or req.bbox.y2 <= req.bbox.y1:
            raise HTTPException(400, "bbox غير صالح — يتطلب x2 > x1 و y2 > y1")
        db = SnippetDB()
        snippet = TrainingSnippet(
            source_image=req.source_image,
            level=req.level,  # type: ignore[arg-type]
            bbox=(req.bbox.x1, req.bbox.y1, req.bbox.x2, req.bbox.y2),
            text=req.text, ocr_text=req.ocr_text,
            confidence=req.confidence, language=req.language,
            category=req.category,
        )
        snippet_id = db.insert(snippet)
        return {"id": snippet_id, **db.to_dict(snippet) | {"id": snippet_id}}

    @_app.get("/api/snippets")
    async def list_snippets(
        status: str = Query("", description="فلترة بالحالة: pending|approved|rejected"),
        source_image: str = Query("", description="فلترة بالصورة المصدر"),
        limit: int = Query(100, ge=1, le=1000),
        _auth: str = Depends(_verify_api_key),
    ):
        from src.db.snippet_db import SnippetDB
        db = SnippetDB()
        if source_image:
            snippets = db.get_by_source(source_image)
        elif status:
            snippets = db.list_by_status(status)  # type: ignore[arg-type]
        else:
            conn = db._connect()
            rows = conn.execute("SELECT * FROM snippets ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            conn.close()
            snippets = [db._row_to_snippet(r) for r in rows]
        return {"items": [db.to_dict(s) for s in snippets[:limit]], "count": len(snippets)}

    @_app.get("/api/snippets/stats")
    async def snippet_stats(_auth: str = Depends(_verify_api_key)):
        from src.db.snippet_db import SnippetDB
        return SnippetDB().stats()

    @_app.patch("/api/snippets/{snippet_id}")
    async def update_snippet(snippet_id: int, req: SnippetUpdate, _auth: str = Depends(_verify_api_key)):
        from src.db.snippet_db import SnippetDB
        db = SnippetDB()
        changed = False
        if req.bbox is not None:
            if req.bbox.x2 <= req.bbox.x1 or req.bbox.y2 <= req.bbox.y1:
                raise HTTPException(400, "bbox غير صالح — يتطلب x2 > x1 و y2 > y1")
            changed |= db.update_bbox(
                snippet_id, (req.bbox.x1, req.bbox.y1, req.bbox.x2, req.bbox.y2)
            )
        if req.text is not None:
            changed |= db.update_text(snippet_id, req.text)
        if req.category is not None:
            changed |= db.update_category(snippet_id, req.category)
        if not changed:
            raise HTTPException(404, "القصاصة غير موجودة أو لا توجد تغييرات")
        updated = db.get(snippet_id)
        return {"ok": True, "id": snippet_id, "snippet": db.to_dict(updated) if updated else None}

    @_app.post("/api/snippets/{snippet_id}/approve")
    async def approve_snippet(snippet_id: int, req: SnippetReview, _auth: str = Depends(_verify_api_key)):
        from src.db.snippet_db import SnippetDB
        if not SnippetDB().approve(snippet_id, req.verified_by):
            raise HTTPException(404, "القصاصة غير موجودة")
        return {"ok": True, "status": "approved"}

    @_app.post("/api/snippets/{snippet_id}/reject")
    async def reject_snippet(snippet_id: int, req: SnippetReview, _auth: str = Depends(_verify_api_key)):
        from src.db.snippet_db import SnippetDB
        if not SnippetDB().reject(snippet_id, req.reason):
            raise HTTPException(404, "القصاصة غير موجودة")
        return {"ok": True, "status": "rejected"}

    @_app.delete("/api/snippets/{snippet_id}")
    async def delete_snippet(snippet_id: int, _auth: str = Depends(_verify_api_key)):
        from src.db.snippet_db import SnippetDB
        if not SnippetDB().delete(snippet_id):
            raise HTTPException(404, "القصاصة غير موجودة")
        return {"ok": True, "deleted": snippet_id}

    @_app.post("/api/snippets/export-hf")
    async def export_snippets_hf(
        include_unchanged: bool = Query(False),
        _auth: str = Depends(_verify_api_key),
    ):
        """تصدير القصاصات المعتمدة محليًا JSONL — الرفع إلى HF خطوة منفصلة صريحة."""
        from src.services.hf_exporter import HFExporter
        from src.db.snippet_db import SnippetDB
        exporter = HFExporter(SnippetDB())
        out = exporter.export(include_unchanged=include_unchanged)
        return {"ok": True, "export_path": str(out)}

    @_app.post("/api/snippets/export-hf/push")
    async def push_snippets_hf(token: str = Query(..., min_length=8), _auth: str = Depends(_verify_api_key)):
        """رفع صريح إلى HuggingFace — يتطلب توكن في الطلب (لا يُخزَّن أبدًا)."""
        from src.services.hf_exporter import HFExporter
        from src.db.snippet_db import SnippetDB
        try:
            url = HFExporter(SnippetDB()).push_to_hf(token)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(400, str(exc))
        return {"ok": True, "url": url}

    @_app.get("/api/snippets/lines")
    async def snippet_lines(
        source_image: str = Query(..., description="مسار الصورة الأصلية"),
        approved_only: bool = Query(False, description="المعتمدات فقط"),
        _auth: str = Depends(_verify_api_key),
    ):
        """تجميع القصاصات في سطور بترتيب RTL الصحيح — معاينة قبل التصدير.

        المرحلة 3 (محادثة DeepSeek): line_aggregator يرتب الكلمات داخل كل سطر
        بحسب x2 تنازليًا (يمين ← يسار) لتفادي النص المقلوب.
        """
        from src.db.snippet_db import SnippetDB
        from src.services.line_aggregator import LineAggregator
        db = SnippetDB()
        snippets = db.get_by_source(source_image)
        if approved_only:
            snippets = [s for s in snippets if s.status == "approved"]
        rows = [
            {
                "id": s.id,
                "bbox": list(s.bbox),
                "text": s.text or s.ocr_text,
                "confidence": s.confidence,
                "source": "snippet-db",
            }
            for s in snippets
        ]
        lines = LineAggregator().aggregate(rows, reading_direction="rtl")
        return {
            "lines": [ln.to_dict() for ln in lines],
            "count": len(lines),
            "words": sum(ln.word_count for ln in lines),
        }

    @_app.post("/api/snippets/validate")
    async def validate_snippets(
        source_image: str = Query(..., description="مسار الصورة الأصلية"),
        approved_only: bool = Query(True, description="المعتمدات فقط (افتراضي)"),
        _auth: str = Depends(_verify_api_key),
    ):
        """بوابات الجودة قبل التصدير — bbox/نص/ثقة/أرقام/وحدات طبية.

        المرحلة 3 (محادثة DeepSeek): dataset_validator يفحص أن الأرقام لم
        تتغير بين ocr_text والنص المصحح (guardrails) ووحدات الجرعات الطبية.
        """
        from src.db.snippet_db import SnippetDB
        from src.services.dataset_validator import DatasetValidator
        db = SnippetDB()
        snippets = db.get_by_source(source_image)
        if approved_only:
            snippets = [s for s in snippets if s.status == "approved"]
        rows = [
            {
                "id": s.id,
                "bbox": list(s.bbox),
                "text": s.text,
                "ocr_text": s.ocr_text,
                "confidence": s.confidence,
                "category": s.category,
            }
            for s in snippets
        ]
        result = DatasetValidator().validate_all(rows, source_image)
        return result.to_dict()

    @_app.get("/api/glossary/suggest")
    async def glossary_suggest(
        text: str = Query(..., min_length=1, description="نص جزئي للبحث"),
        limit: int = Query(8, ge=1, le=25),
        _auth: str = Depends(_verify_api_key),
    ):
        """اقتراحات المسرد الطبي (عربي/إنجليزي) لمحرر OCR — دون اتصال."""
        from src.core.glossary_service import get_glossary_service
        suggestions = get_glossary_service().suggest(text, limit=limit)
        return {"suggestions": suggestions, "count": len(suggestions)}

    @_app.get("/api/glossary/info")
    async def glossary_info(_auth: str = Depends(_verify_api_key)):
        from src.core.glossary_service import get_glossary_service
        svc = get_glossary_service()
        return {"path": str(svc.path), "terms": svc.size}

    return _app


# Safe category pattern (Arabic + alphanumeric + dash/underscore)
_SAFE_CATEGORY_RE = re.compile(r"^[\w\-\u0600-\u06FF]+$")


# When run directly: uvicorn src.api.server:app --port 8421
app = create_app()
