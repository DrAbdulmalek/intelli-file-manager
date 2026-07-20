# RC Checklist — IntelliFile Manager v2.0

## Release Candidate Checklist

### P0 — Integration with omni-medical-suite
- [x] scanner_fixer integrated into `classifier.py` (`_init_scanner_fixer()`)
- [x] scanner_fixer integrated into `enhanced_multimodal.py` (fixed import path, dict-based API)
- [x] field_extractor integrated into `semantic_search.py` (`_init_field_extractor()`)
- [x] glossary-api integrated into `semantic_search.py` (`_enrich_with_glossary()`)
- [x] RTL support added to `rag_engine.py` (`_normalize_arabic()`, `_fix_rtl_text()`)

### P1 — Core Enhancements
- [x] Hybrid Search (BM25 + Semantic + RRF) — `hybrid_search.py`
- [x] Multimodal (Moondream + Whisper + OCR + Tesseract) — `enhanced_multimodal.py`
- [x] Smart Tagging (TagSpaces-compatible) — `smart_tagger.py`
- [x] File Copilot (RAG chat) — `file_copilot.py`
- [x] Medical NER (7 entity types) — `medical_ner.py`
- [x] Arabic text normalization in all engines
- [x] Offline-first: all models run locally
- [x] Privacy: no data leaves device

### P2 — Mobile + Deployment
- [x] Kivy mobile app (`mobile/main.py`)
- [x] buildozer.spec for Android APK
- [x] PWA manifest (`public/manifest.json`)
- [x] Service Worker (`public/sw.js`)
- [x] CI/CD workflow (`.github/workflows/build-apk.yml`)

### P3 — Documentation + Plugin System
- [x] README.md (comprehensive, bilingual)
- [x] CONTRIBUTING.md (with Arabic RTL guidelines)
- [x] docs/ROADMAP.md (v2.1, v3.0)
- [x] Plugin system (`src/plugins/`)
- [x] Sample medical plugin

### Testing
- [x] 241 tests pass (217 unit + 24 integration)
- [x] All 22 API endpoints tested manually
- [x] Health endpoint returns engine availability
- [x] Medical NER extracts Arabic medical entities
- [x] Hybrid search indexes and searches documents
- [x] Smart tagger auto-tags medical files
- [x] File Copilot conversation management works

### API Endpoints (22 verified)
- [x] `GET /api/health` — engine availability
- [x] `GET /api/stats` — categories and version
- [x] `POST /api/classify` — file classification
- [x] `POST /api/organize` — file organization (dry run)
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
- [x] `POST /api/ner/extract` — medical NER extraction
- [x] `POST /api/process/image` — image processing
- [x] `POST /api/process/audio` — audio transcription
- [x] `POST /api/process/video` — video processing
- [x] `POST /api/process/document` — document processing

### Security & Privacy
- [x] No data sent to external servers (offline-first)
- [x] Ollama runs locally only
- [x] ChromaDB stores vectors locally
- [x] No telemetry or analytics
- [x] CORS restricted to localhost:3000/3001/8420
- [x] File uploads stored in ~/.intellifile/uploads/

### Arabic RTL Support
- [x] UI text in Arabic
- [x] Medical NER extracts Arabic entities
- [x] Arabic text normalization (أإآ→ا, ى→ي, ة→ه)
- [x] RTL-aware chunking in RAG engine
- [x] Bilingual search (Arabic + English glossary)
- [x] PWA manifest with dir: "rtl", lang: "ar"

---

## Pre-Release Sign-off

| Criterion | Status |
|-----------|--------|
| All P0 tasks complete | ✅ |
| All P1 tasks complete | ✅ |
| All P2 tasks complete | ✅ |
| All P3 tasks complete | ✅ |
| 241+ tests passing | ✅ |
| No critical bugs | ✅ |
| Documentation complete | ✅ |
| API endpoints verified | ✅ |
| Privacy requirements met | ✅ |
| Arabic RTL support verified | ✅ |

**Release Candidate: READY** ✅
