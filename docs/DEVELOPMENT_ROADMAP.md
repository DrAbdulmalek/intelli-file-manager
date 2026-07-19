# IntelliFile — Development Roadmap

> **Status:** Proposal (not yet merged into `main`)
> **Branch:** `docs/development-roadmap`
> **Source:** Community analysis + open-source benchmarks (LlamaFS, Rememex, AmazeSort, Flamehaven-Filesearch, TagSpaces, Xplorer, Docspell, OpenDMS, Wolfe)
> **Last updated:** 2026-07-20

---

## Table of Contents

1. [Project Analysis](#1-project-analysis)
2. [Reference Projects & Lessons Learned](#2-reference-projects--lessons-learned)
3. [Phase 1 — Strengthen Existing Features](#3-phase-1--strengthen-existing-features)
4. [Phase 2 — New Features](#4-phase-2--new-features)
5. [Phase 3 — Scale & Outreach](#5-phase-3--scale--outreach)
6. [Additional Improvements](#6-additional-improvements)
7. [Test Plan](#7-test-plan)
8. [Dependencies](#8-dependencies)
9. [Executive Summary](#9-executive-summary)

---

## 1. Project Analysis

### 1.1 Strengths to Preserve

| Aspect | Current State |
|---|---|
| **Modular structure** | Files organized in `core/`, `ai/`, `db/`, `gui/`, `utils/` |
| **Ollama integration** | Local model execution — key competitive advantage |
| **Dual interface** | PySide6 desktop + Next.js web |
| **Test coverage** | 173 tests — must be preserved during development |
| **Multi-modal support** | Images, audio, video, text |
| **Google Magika** | Accurate file-type detection |
| **Arabic voice control** | Unique feature for Arabic-speaking users |

### 1.2 Areas Requiring Development

| File | Gap |
|---|---|
| `src/core/semantic_search.py` | Lacks hybrid search (BM25 + semantic), limited file-type support |
| `src/core/rag_engine.py` | No full multimodal retrieval |
| `src/core/multimodal_processor.py` | Limited image analysis, no advanced OCR |
| `src/ai/classifier.py` / `src/core/classifier.py` | AI-only — no rule-based or hybrid modes |
| Desktop UI | Performance needs improvement |

---

## 2. Reference Projects & Lessons Learned

### 2.1 LlamaFS
- **URL:** https://github.com/collisioncataclysm/Filellama
- **Lessons:** Moondream for image analysis, Whisper for audio, semantic folder creation
- **Application in IntelliFile:** Enhance `multimodal_processor.py` with Moondream + Whisper support

### 2.2 Rememex
- **URL:** https://github.com/illegal-instruction-co/rememex
- **Lessons:** 120+ file types, advanced OCR, full privacy (nothing leaves the device)
- **Application:** Expand `semantic_search.py` for more file types + add OCR

### 2.3 AmazeSort
- **URL:** https://github.com/AmazeContinuityProjects/AmazeSort
- **Lessons:** Three organization modes — rule-based, hybrid, AI-only
- **Application:** Add hybrid and rule-based modes to classifier

### 2.4 Flamehaven-Filesearch
- **URL:** https://github.com/flamehaven01/Flamehaven-Filesearch
- **Lessons:** Hybrid search (BM25 + semantic), 34 file formats, FastAPI
- **Application:** Implement Hybrid Search in `semantic_search.py`

### 2.5 TagSpaces
- **URL:** https://github.com/tagspaces/tagspaces
- **Lessons:** Tag-based organization instead of folders-only
- **Application:** New smart tagging system

### 2.6 Xplorer
- **URL:** https://github.com/kimlimjustin/xplorer
- **Lessons:** Tauri (Rust backend + React frontend) for high performance
- **Application:** Study desktop UI rewrite with Tauri

### 2.7 Docspell
- **URL:** https://github.com/eikek/docspell
- **Lessons:** Integrated document management system with ML for tags and recipients
- **Application:** Expand toward full DMS

### 2.8 Wolfe
- **URL:** (semantic search project)
- **Lessons:** Multimodal semantic search running fully locally
- **Application:** Improve `semantic_search.py` for more file types

### 2.9 OpenDMS
- **Lessons:** AI-driven document lifecycle automation
- **Application:** Add workflow and electronic signature features

---

## 3. Phase 1 — Strengthen Existing Features

### Task 1.1: Hybrid Search in `semantic_search.py`

**Target file:** `src/core/semantic_search.py` (extend) or `src/ai/hybrid_search.py` (new — see stub)

**Changes:**
- Add `BM25Okapi` index alongside the existing vector DB
- Implement Reciprocal Rank Fusion (RRF) to merge BM25 + semantic results
- Add `alpha` parameter to control the weight of semantic vs. keyword search

**Dependencies:** `rank-bm25`, `jieba` (or `nltk`), `numpy`

**Stub file:** [`src/ai/hybrid_search.py`](../src/ai/hybrid_search.py)

---

### Task 1.2: Enhanced Multimodal Processor

**Target file:** `src/core/multimodal_processor.py` (extend) or `src/ai/multimodal_enhanced.py` (new — see stub)

**Changes:**
- Integrate Moondream (`vikhyatk/moondream2`) for image captioning
- Integrate OpenAI Whisper for audio transcription
- Add Tesseract OCR for text extraction from images
- Auto-extract tags from image descriptions

**Dependencies:** `torch`, `torchvision`, `pillow`, `openai-whisper`, `moondream`, `pytesseract`

**Stub file:** [`src/ai/multimodal_enhanced.py`](../src/ai/multimodal_enhanced.py)

---

### Task 1.3: Classifier Modes (Rule-based + Hybrid + AI-only)

**Target file:** `src/ai/classifier.py` (extend) or `src/ai/classifier_modes.py` (new — see stub)

**Changes:**
- Introduce `ClassificationMode` enum: `RULE_BASED`, `HYBRID`, `AI_ONLY`
- Load rules from `rules.json` (with sensible defaults)
- Hybrid mode: try rules first, fall back to AI when confidence < 0.8

**Stub file:** [`src/ai/classifier_modes.py`](../src/ai/classifier_modes.py)

---

## 4. Phase 2 — New Features

### Task 2.1: Smart Tagging System

**New file:** `src/ai/tagging.py`

**Features:**
- Auto-generate tags from content (KeyBERT), file type, context, and AI analysis
- Store tags in DB; query files by tag
- Inspired by TagSpaces

**Dependencies:** `keybert`

**Stub file:** [`src/ai/tagging.py`](../src/ai/tagging.py)

---

### Task 2.2: File as Copilot

**New file:** `src/ai/file_copilot.py`

**Features:**
- Chat with a specific file (PDF, document, etc.)
- Per-file session context with history
- Uses RAG engine for retrieval
- Strict context-grounded answers (no hallucination)

**Stub file:** [`src/ai/file_copilot.py`](../src/ai/file_copilot.py)

---

### Task 2.3: Multi-language Voice Control

**Goal:** Extend existing Arabic voice control to support English and other languages.

**Target file:** `src/core/voice_controller.py` (extend in future task)

---

### Task 2.4: UI/UX Improvements

**New file:** `src/gui/theme_manager.py`

**Features:**
- Multiple themes: `dark`, `light`, `high_contrast`
- Save user preference
- PySide6 `QPalette`-based

**Stub file:** [`src/gui/theme_manager.py`](../src/gui/theme_manager.py)

---

## 5. Phase 3 — Scale & Outreach

### Task 3.1: Cross-Platform Support

**New file:** `src/utils/platform_utils.py`

**Features:**
- Detect platform (Linux / macOS / Windows)
- Return platform-appropriate paths (Downloads, app data dir)
- Stub for Windows registry reading

**Stub file:** [`src/utils/platform_utils.py`](../src/utils/platform_utils.py)

---

### Task 3.2: Plugin System

**New file:** `src/core/plugin_manager.py`

**Features:**
- Discover plugins from `plugins/` directory via `manifest.json`
- Hook system: `register_hook(name, callback)` / `trigger_hook(name, *args)`
- Sandbox plugin failures (one bad plugin does not crash the app)

**Stub file:** [`src/core/plugin_manager.py`](../src/core/plugin_manager.py)

**Example plugin manifest:**
```json
{
    "name": "PDFAnnotator",
    "version": "1.0.0",
    "description": "Adds PDF annotation capabilities",
    "author": "Your Name",
    "hooks": ["on_file_open", "on_file_save"]
}
```

---

### Task 3.3: Community Building

- Improve `CONTRIBUTING.md`
- Create Discord/Slack channel
- Publish tutorials (student files, personal archive, dev projects)

---

## 6. Additional Improvements

### 6.1 Async Indexing

**New file:** `src/core/async_indexer.py`

**Features:**
- `asyncio.Queue`-based indexing pipeline
- `ThreadPoolExecutor` for CPU-bound work
- Non-blocking file ingestion

**Stub file:** [`src/core/async_indexer.py`](../src/core/async_indexer.py)

---

## 7. Test Plan

### 7.1 New Test Stubs

| File | Tests |
|---|---|
| `tests/unit/test_hybrid_search.py` | BM25 indexing, hybrid search, RRF |
| `tests/unit/test_tagging.py` | Keyword extraction, tag generation |

---

## 8. Dependencies

### Additions to `requirements.txt`

```
# Hybrid search
rank-bm25>=0.2.0
jieba>=0.42.1
nltk>=3.8.0

# Multimodal (Phase 1)
torch>=2.0.0
openai-whisper>=20231117
moondream>=0.0.1
pytesseract>=0.3.10

# Smart tagging
keybert>=0.8.0

# Async indexing
aiofiles>=23.0.0
pytest-asyncio>=0.21.0
```

---

## 9. Executive Summary

| Priority | Task | File(s) | Est. Days |
|---|---|---|---|
| 1 | Hybrid search | `src/core/semantic_search.py` (extend) / `src/ai/hybrid_search.py` (stub) | 3 |
| 2 | Enhanced multimodal processor | `src/core/multimodal_processor.py` (extend) / `src/ai/multimodal_enhanced.py` (stub) | 2 |
| 3 | Classifier modes | `src/ai/classifier.py` (extend) / `src/ai/classifier_modes.py` (stub) | 2 |
| 4 | Smart tagging | `src/ai/tagging.py` (new) | 3 |
| 5 | File as Copilot | `src/ai/file_copilot.py` (new) | 4 |
| 6 | Cross-platform utils | `src/utils/platform_utils.py` (new) | 2 |
| 7 | Plugin system | `src/core/plugin_manager.py` (new) | 3 |
| 8 | UI themes | `src/gui/theme_manager.py` (new) | 2 |
| 9 | Async indexer | `src/core/async_indexer.py` (new) | 2 |
| 10 | Tests | `tests/unit/test_hybrid_search.py`, `tests/unit/test_tagging.py` | 3 |

**Total estimated effort:** ~26 developer-days for full implementation.

---

## Implementation Notes

- All code stubs in this branch are **starting points** — they contain the proposed class skeletons with `pass` / `...` placeholders for methods that require project-specific integration.
- Stub files use **new filenames** (e.g., `hybrid_search.py` instead of overwriting `semantic_search.py`) to avoid breaking existing tests. When the actual implementation begins, the developer should decide whether to merge stubs into existing files or keep them as companions.
- The existing 173 tests **must keep passing**. New tests should be added under `tests/unit/`.
- Dependencies added to `requirements.txt` are **additive** — no existing dependency was removed.
