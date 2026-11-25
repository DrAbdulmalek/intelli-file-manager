# DrAbdulmalek Omni Intelligence Roadmap

**Status:** Proposal / planning only  
**Date:** 2026-11-23  
**Scope:** Cross-repository architecture and staged development proposals. This document does not authorize implementation, data migration, new repository creation, or changes to clinical workflows.

## 1. Purpose

Turn the extracted ClipboardPro development ideas into a coordinated roadmap for the existing DrAbdulmalek repositories. The intent is to reuse existing capabilities, avoid duplicated engines, preserve local-first operation, and require evidence before accepting AI-generated conclusions.

This is a planning document, not a claim that the proposed components already exist.

## 2. Existing repository allocation

| Capability | Primary repository | Integration targets | Status |
|---|---|---|---|
| Intelligent file classification, user preferences, feedback UI | `intelli-file-manager` | AlphaCode / MCP clients | Proposal; inspect existing modules before implementation |
| OCR correction feedback, medical terminology, CER/WER evaluation | `ocr-core` | `omni-medical-suite`, `medical-rag-ar` | Proposal; reuse current OCR engines and benchmark contracts |
| Medical workflow feedback and quality reporting | `omni-medical-suite` | `ocr-core`, provider layer | Proposal |
| Provider-neutral model routing, MCP boundary, privacy policy enforcement | `omni-llm-provider-layer` | All local applications | Proposal; respect existing LOCAL_ONLY / explicit remote policy |
| DICOM metadata and processing safeguards | `Faris-DICOM-Studio` | Local security components | Proposal; preserve DICOM identifiers and clinical disclaimers |
| Read-only system diagnostics and explainable maintenance feedback | `manjaro-care` | Local reporting tools | Proposal; preserve scan → preview → explicit apply |
| Arabic medical RAG | `medical-rag-ar` | `ocr-core`, glossary, corrections | Respect its documented 12-week freeze; no implementation changes in this phase |

## 3. Shared architecture proposals

### 3.1 Preference Engine

A local component that stores explicit user preferences and distinguishes:
- one-file correction;
- folder-specific preference;
- document-type preference;
- reusable user-wide rule.

Requirements:
- provenance and timestamp for every learned preference;
- confidence and evidence count;
- conflict detection and explainable precedence;
- user review, disable, undo, and deletion;
- no silent conversion of one correction into a global rule;
- no training or remote transmission by default.

### 3.2 Feedback Engine

Normalize application feedback into a versioned, privacy-aware event schema:
- application and component;
- event category and severity;
- expected versus observed result;
- reproducibility information;
- sanitized diagnostic context;
- evidence status;
- user correction / acceptance / rejection;
- lifecycle state.

Separate three stores or namespaces: user preferences, product-behavior corrections, and engineering defects. Do not mix them into one undifferentiated learning dataset.

### 3.3 Sensitive Data Security Boundary

A reusable policy concept for inputs before OCR, RAG, LLM, indexing, MCP tool execution, or export:
1. identify and validate the input type;
2. canonicalize and validate paths, including symlinks;
3. classify sensitivity;
4. evaluate local/remote processing policy;
5. issue an explicit allow/deny decision;
6. record a minimal audit event without copying sensitive content.

A BLOCKED result must be tested at the actual boundary: the protected payload must not be opened by the downstream processor or transmitted. Secrets remain blocked. Medical data stays local unless a separately authorized, explicit workflow permits otherwise. No cloud fallback.

### 3.4 MCP integration

Expose narrow, typed, least-privilege tools rather than unrestricted filesystem or shell access. Tools should default to read-only. Any mutating action requires a preview, explicit user approval, bounded paths, and an auditable result. Tool outputs must distinguish observed facts from model-generated suggestions.

### 3.5 Evidence and quality model

Use explicit evidence labels:
- Proven
- Partially Proven
- Unproven
- Contradicted
- BLOCKED

AI triage and root-cause analysis are hypotheses until validated. Preserve source evidence, file/line references, test output, and reproducibility details.

## 4. Proposed future shared projects — not created

These ideas may become separate repositories only after a duplication and dependency audit:

1. **omni-feedback-engine** — shared feedback schema, deduplication, privacy filtering, evidence tracking, and export adapters.
2. **omni-sensitive-data-security-engine** — reusable local input-policy and data-boundary library.
3. **omni-security-intelligence** — authorized repository security triage and evidence-based reporting.
4. **omni-performance-lab** — profiling, hotspot detection, benchmark harnesses, and optional Rust optimization experiments.
5. **omni-dataset-intelligence** — dataset quality, duplication, class balance, distribution shift, and leakage analysis.

Do not create these repositories until existing code and open PRs have been audited for equivalent functionality.

## 5. Performance engineering

Use profiling before rewriting code. Candidate areas include OCR image processing, file indexing, medical data processing, and RAG retrieval. A Rust implementation is acceptable only when:
- a reproducible baseline exists;
- behavioral equivalence tests pass;
- representative benchmarks show a meaningful improvement;
- resource use and failure modes are measured;
- the Python implementation remains available until review and acceptance.

## 6. Dataset intelligence

For OCR and medical datasets, report language/script balance, printed versus handwritten proportions, image quality distribution, class imbalance, near-duplicates, outliers, and train/test leakage. Reports must avoid exposing patient data and must not silently modify source datasets.

## 7. Delivery and governance

- Work on dedicated branches; never commit directly to `main`.
- Use focused pull requests, preferably one concern per PR.
- Keep PRs draft until documentation, tests, security review, and scope are checked.
- Do not merge automatically.
- Do not rewrite history, force-push, or amend existing commits.
- No external code execution or cloud processing of sensitive data without explicit authorization.
- Do not upload ClipboardPro backups, credentials, local paths, patient data, or raw diagnostic dumps.
- Existing open PRs and repository-specific freezes take precedence; avoid overlapping work.
- Every implementation phase must include acceptance criteria, negative tests, rollback strategy, and evidence.

## 8. Suggested phases

| Phase | Deliverable | Gate |
|---|---|---|
| 0 | Inventory current modules, open PRs, tests, policies, and overlaps | Read-only audit |
| 1 | IntelliFile preference/feedback design and UI contract | Schema and threat-model review |
| 2 | OCR correction feedback contract | CER/WER regression tests and human review |
| 3 | Medical workflow feedback integration | No clinical claims without validation |
| 4 | Provider/MCP policy boundary | Deny-by-default and exfiltration tests |
| 5 | DICOM and Manjaro adapters | Domain-specific safety tests |
| 6 | Decide whether shared engines deserve separate repositories | Duplication and maintenance-cost review |
| 7 | Performance and dataset intelligence | Reproducible benchmarks and data-governance review |

## 9. Non-goals

This roadmap does not authorize autonomous file movement/deletion, system repair, clinical decision-making, silent model training, cloud fallback, automatic PR merging, or bulk changes across repositories.

## 10. First recommended action

Perform a read-only inventory of the current code and all open pull requests in each target repository. Map every proposed capability to existing files and tests. Only then create implementation issues or follow-up PRs.
