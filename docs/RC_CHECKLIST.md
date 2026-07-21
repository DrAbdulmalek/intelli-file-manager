# RC Checklist — IntelliFile Manager

## Release Candidate Checklist

### P0 — Core File Management
- [x] Smart file classification (Magika + content-based)
- [x] Hybrid Search (BM25 + Semantic + RRF)
- [x] Smart Tagging (TagSpaces-compatible)
- [x] File Copilot (RAG chat)
- [x] File organization (dry-run + undo)
- [x] Multimodal processing (image/audio/video/document)
- [x] Named Entity Recognition (NER)
- [x] Arabic text normalization in all engines
- [x] Offline-first: all models run locally
- [x] Privacy: no data leaves device

### P1 — Security
- [x] API binds to 127.0.0.1 by default (not 0.0.0.0)
- [x] Optional API key authentication (INTELLIFILE_API_KEY)
- [x] CORS restricted to localhost origins
- [x] Path sandboxing (_validate_path)
- [x] No exec() or eval() in codebase
- [x] .gitignore properly configured
- [x] No hardcoded secrets

### P2 — Desktop Experience
- [x] PySide6 desktop GUI
- [x] CLI interface
- [x] Next.js web interface (optional)

### P3 — Documentation + Plugin System
- [x] README.md (bilingual, accurate)
- [x] CONTRIBUTING.md
- [x] docs/ROADMAP.md
- [x] Plugin system (src/plugins/)
- [x] Clean repository boundaries (no cross-repo coupling)

### Testing
- [x] Unit tests pass
- [x] Integration tests pass
- [x] API endpoints tested
- [x] Health endpoint returns engine availability
- [x] Hybrid search indexes and searches documents
- [x] Smart tagger auto-tags files
- [x] File Copilot conversation management works

### API Endpoints (verified)
- [x] `GET /api/health` — engine availability
- [x] `GET /api/stats` — categories and version
- [x] `POST /api/classify` — file classification
- [x] `POST /api/organize` — file organization
- [x] `POST /api/search` — hybrid/BM25/semantic search
- [x] `POST /api/search/index` — index directory
- [x] `POST /api/tags/auto` — auto-tag file
- [x] `POST /api/tags/add` — add manual tag
- [x] `POST /api/tags/batch` — batch tag files
- [x] `DELETE /api/tags/remove` — remove tag
- [x] `GET /api/tags/search` — search by tag
- [x] `GET /api/tags/all` — all tags in directory
- [x] `POST /api/copilot/chat` — RAG chat
- [x] `POST /api/copilot/index` — index files for copilot
- [x] `GET /api/copilot/conversations` — list conversations
- [x] `POST /api/copilot/summarize` — summarize file
- [x] `WS /api/copilot/ws` — WebSocket streaming chat
- [x] `POST /api/ner/extract` — NER extraction
- [x] `POST /api/process/image` — image processing
- [x] `POST /api/process/audio` — audio transcription
- [x] `POST /api/process/video` — video processing
- [x] `POST /api/process/document` — document processing
- [x] `POST /api/embed` — generate embeddings
- [x] `POST /api/embed/similarity` — compute similarity

### Security & Privacy
- [x] No data sent to external servers (offline-first)
- [x] Ollama runs locally only
- [x] ChromaDB stores vectors locally
- [x] No telemetry or analytics
- [x] CORS restricted to localhost:3000/3001/8420
- [x] API key authentication available
- [x] Path sandboxing active
- [x] File uploads stored in ~/.intellifile/uploads/

### Arabic RTL Support
- [x] UI text in Arabic
- [x] NER extracts Arabic entities
- [x] Arabic text normalization
- [x] RTL-aware chunking in RAG engine
- [x] Bilingual search support

---

## Pre-Release Sign-off

| Criterion | Status |
|-----------|--------|
| Core features complete | ✅ |
| Security audit passed | ✅ |
| Repository boundaries clean | ✅ |
| No cross-repo coupling | ✅ |
| Tests passing | ✅ |
| Documentation accurate | ✅ |
| Privacy requirements met | ✅ |
| Arabic RTL support verified | ✅ |

**Release Candidate: READY** ✅
