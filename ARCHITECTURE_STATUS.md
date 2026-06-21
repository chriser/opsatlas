# Architecture status & module maturity

Modular-monolith backend under `src/assistant/`, React/TS control panel under `frontend/`.
Status: **Built** (in use + tested), **Partial** (works, planned depth to add), **Planned**.

| Module | Responsibility | Status | Key files |
|---|---|---|---|
| **Source & data governance** | Source register, upload, metadata, **approval gate** | Built | `sources/` (`register.py`, `service.py`, `models.py`) |
| **Ingestion & preparation** | Text extraction (.txt/.md/.json/.pdf/.docx), section builder | Built | `ingestion/` (`service.py`, `sections.py`, `store.py`) |
| **Knowledge & retrieval** | Hybrid BM25 + embeddings (RRF), query rewriting, relevance threshold, reranking | Built | `retrieval/` (`service.py`, `embedder.py`, `rewrite.py`, `rerank.py`) |
| **Model runtime** | Provider abstraction (embed/generate/health); swap models via env | Built | `models/provider.py` |
| **RAG / answer** | Evidence pack, constrained grounding prompt, full-context vs retrieval, citations | Built | `answer/` (`service.py`, `prompt.py`, `generator.py`) |
| **Guardrails (input)** | Manipulation, focus/off-topic, content-safety categories | Built | `guardrails/checker.py` |
| **Validation & response** | Refusal handling, confidence (grounded/unverified); answer-vs-evidence support check | Partial | `answer/service.py` (deeper groundedness scoring planned, #63/#643) |
| **Governance intelligence** | Compliance / Consistency (duplicates) / Correctness (conflicts, outdated) | Built | `governance/` (`intelligence.py`) |
| **Analytics & insight** | Usage log, scorecard (rates, gaps), topic classification | Built | `analytics/` (`log.py`, `classify.py`) |
| **Process registry** | Structured process knowledge (owners, systems, hand-offs) | Planned | (#608) |
| **Assistant API & UI** | FastAPI app + routes; React control panel (auth, pages) | Built | `api/`, `frontend/src/` |
| **Build, test & evaluation** | Question set, scoring, accuracy report; model A/B | Built | `eval/runner.py`, `automation/evaluate.py`, `docs/benchmark/` |
| **Voice interaction** | Speech-to-text / avatar over the validated answer | Out of scope (PoC exists in `poc/`) | `poc/supplier-avatar/` |
| **Delivery governance** | Azure DevOps backlog/wiki automation, CI pipeline | Built | `automation/`, `azure-pipelines.yml` |

## Design principles in force
- **Grounded** — answers only from approved, retrieved evidence; refuses otherwise.
- **Inspectable** — citations, confidence, retrieval mode, knowledge-intelligence issues.
- **Modular** — each module owns one responsibility with a clear interface.
- **Governed** — human approval gate before any source is queryable.
- **Iterative** — thin vertical slices; the full pipeline is end-to-end and benchmarked.

## Quality baseline
Automated eval on the supplier pack: **18/20 (90%)** with `qwen2.5:7b` + `nomic-embed-text`
(`docs/benchmark/eval-results-2026-06-20.json`); at parity with the commercial baseline on
the shared question set. Re-run on real packs and A/B larger models via `automation/evaluate.py`.
