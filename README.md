# AI Knowledge and Analytics Assistant

A governed, retrieval-augmented assistant that turns business-process knowledge into
**grounded, cited answers**, and an **analytics layer** that surfaces knowledge gaps and
content-quality issues. Built as a modular monolith, runs **fully local on open-source
models** (Ollama), and uses **synthetic/anonymised data only**.

> Academic proof of concept (DT602 planning → DT603 delivery). No confidential data, no
> paid/cloud models; everything runs and is stored locally.

## The knowledge lifecycle

```
Upload → Ingest → Approve (governance gate) → Retrieve → Ground → Answer → Guardrails → Analytics
```

- **Upload** a source document (`.txt .md .pdf .docx .json`) — stored + catalogued in the source register.
- **Ingest** — text extracted and split into metadata-tagged sections.
- **Approve** — human-in-the-loop gate; **only approved sources are queryable**.
- **Retrieve** — hybrid search (BM25 + local embeddings, RRF) with query rewriting, a
  relevance threshold, and reranking.
- **Answer** — a constrained, grounding-only prompt on a local LLM produces a cited answer
  that **refuses when the evidence is insufficient**; small KBs use full-context mode.
- **Guardrails** — input checks for manipulation, off-topic focus and content-safety.
- **Analytics** — every query logged → scorecard (answer/grounded/refusal rates), knowledge
  gaps and questions-by-topic.
- **Governance Knowledge Intelligence** — automated checks grouped into Compliance,
  Consistency (duplicates) and Correctness (conflicts, outdated).

See [ARCHITECTURE_STATUS.md](ARCHITECTURE_STATUS.md) for the module map and maturity.

## Quick start

**Prerequisites:** Python 3.11+, Node 18+, and [Ollama](https://ollama.com) with the models:
```bash
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text
ollama pull deepseek-r1:8b
ollama pull deepseek-r1:32b
```
The local Governance compliance review has three depths: **Fast triage** uses
deterministic checks, **Balanced** uses the lighter local reasoning profile, and
**Deep audit** uses the full DeepSeek-R1 32B profile. The default Governance page
load is deterministic and does not invoke a local LLM. Legacy internal
Governance contradiction checks can opt in separately with
`KP_GOVERNANCE_LLM_ENABLED=1` and `KP_GOVERNANCE_LLM_MODEL`.

To override the Governance Review Agent profiles:
```bash
KP_COMPLIANCE_BALANCED_LLM_MODEL=qwen2.5:7b-instruct \
KP_COMPLIANCE_DEEP_LLM_MODEL=deepseek-r1:32b \
./scripts/dev.sh
```

**One-time setup:**
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cd frontend && npm install && cd ..
```

**Run (compliance service + backend + control panel):**
```bash
./scripts/dev.sh
```
Open **http://localhost:5200/**, sign in with the operator password (default
`knowledge-demo`), then: **Knowledge Sources → upload → Ingest → Governance → Approve →
Ask**.

Backend alone: `.venv/bin/python -m uvicorn assistant.api.app:app --app-dir src --port 8010`

Compliance reasoning alone:
`PYTHONPATH=. KP_COMPLIANCE_AGENT_ENABLED=1 .venv/bin/python -m uvicorn services.compliance_reasoning.app:app --host 127.0.0.1 --port 5310`

## Control panel pages
- **Dashboard** — assistant scorecard, knowledge gaps, questions by topic.
- **Knowledge Sources** — upload and manage source documents; ingest.
- **Ask Digital SME** — spoken grounded answers through the avatar renderer.
- **Written Query** — grounded written answers with citations, confidence and refusals.
- **Citation Check** — inspect retrieved source passages behind an answer.
- **Governance** — Knowledge Intelligence overview + per-source Approve/Reject.

## Configuration (environment variables)
| Variable | Default | Purpose |
|---|---|---|
| `KP_OPERATOR_PASSWORD` | `knowledge-demo` | Control-panel login |
| `KP_OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama endpoint |
| `KP_LLM_MODEL` | `qwen2.5:7b-instruct` | Answer model (swap to A/B) |
| `KP_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `KP_LLM_NUM_CTX` | `8192` | LLM context window |
| `KP_COMPLIANCE_AGENT_ENABLED` | `1` in `scripts/dev.sh` | Enable the bounded Governance Review Agent |
| `KP_COMPLIANCE_BALANCED_LLM_MODEL` | `deepseek-r1:8b` | Lighter local model for Balanced compliance/internal review |
| `KP_COMPLIANCE_DEEP_LLM_MODEL` | `KP_COMPLIANCE_LLM_MODEL` or `deepseek-r1:32b` | Full local model for Deep audit |
| `KP_COMPLIANCE_BALANCED_LLM_NUM_CTX` | `4096` | Balanced adjudication context window |
| `KP_COMPLIANCE_DEEP_LLM_NUM_CTX` | `KP_COMPLIANCE_LLM_NUM_CTX` or `KP_LLM_NUM_CTX` | Deep adjudication context window |
| `KP_COMPLIANCE_DEEP_THROTTLE` | `0` | Global switch that runs Deep audit with the throttled Ollama profile |
| `KP_COMPLIANCE_DEEP_THROTTLED_LLM_NUM_CTX` | `4096` | Context window used by the per-review `Throttle Deep` toggle |
| `KP_COMPLIANCE_DEEP_THROTTLED_LLM_NUM_GPU` | `0` | Throttled Deep GPU offload. `0` asks Ollama to avoid GPU offload; raise this only if you want partial GPU use |
| `KP_COMPLIANCE_DEEP_THROTTLED_LLM_NUM_BATCH` | `16` | Smaller Ollama batch for throttled Deep audit |
| `KP_COMPLIANCE_DEEP_THROTTLED_LLM_NUM_THREAD` | `4` | CPU thread cap for throttled Deep audit |
| `KP_COMPLIANCE_DEEP_THROTTLED_LLM_COOLDOWN_SECONDS` | `3` | Pause between local LLM calls in throttled Deep audit |
| `KP_COMPLIANCE_LLM_TIMEOUT` | `120` | Compliance adjudication timeout fallback in seconds |
| `KP_COMPLIANCE_PAIR_CACHE_PATH` | `data/compliance_reasoning_pair_cache.json` | Pair-result cache for unchanged compliance comparisons |
| `KP_GOVERNANCE_LLM_ENABLED` | `0` in `scripts/dev.sh` | Enable legacy model-backed Governance page-load contradiction checks |
| `KP_GOVERNANCE_LLM_MODEL` | empty in `scripts/dev.sh` | Optional model used for legacy internal Governance contradiction checks |
| `KP_MIN_SIMILARITY` | `0.45` | Relevance threshold (per embedding model) |
| `KP_QUERY_REWRITE` | `1` | Query rewriting (`0` to disable) |
| `KP_RERANK` | `1` | Reranking (`0` to disable) |
| `KP_VALIDATE_GROUNDING` | `1` | Validate answers are supported by cited evidence (`0` to disable) |
| `KP_DATA_DIR` | `data` | Local storage (git-ignored) |

## Evaluation

```bash
PYTHONPATH=src .venv/bin/python automation/evaluate.py \
    --pack docs/benchmark/supplier-setup-pack.md [--llm qwen3:30b-a3b] [--out report.json]
```
Loads packs, runs the question set (`docs/benchmark/questions.json`) through the full stack,
scores each response against the rubric, and prints accuracy + a per-question report.
Repeatable for real packs and for A/B-ing models. See `docs/benchmark/`.

## Project structure
```
src/assistant/        backend (modular monolith)
  sources/            source register + upload (governance)
  ingestion/          text extraction + section builder
  retrieval/          hybrid search, rewrite, threshold, rerank, embeddings
  answer/             constrained prompt + generation (RAG)
  guardrails/         input safety/focus checks
  governance/         knowledge-intelligence checks
  analytics/          usage log, scorecard, knowledge gaps, classification
  models/             provider abstraction (swap LLM/embeddings)
  eval/               scoring for the evaluation harness
  api/                FastAPI app + routes
frontend/             React + TypeScript + Vite control panel
automation/           Azure DevOps automation + evaluate.py
docs/                 architecture, benchmark, evidence, ways-of-working
tests/                pytest suite
```

## Testing & CI
- `.venv/bin/python -m pytest` — backend tests (hermetic; no Ollama needed).
- `cd frontend && npm run build` — frontend type-check + build.
- CI (`azure-pipelines.yml`) runs both on every push to `main`.

## Data & ethics
- **Synthetic / anonymised data only**; no real names, system names or commercial data.
- Data is stored **locally** under `data/` (git-ignored) — not committed, not cloud.
- The **approval gate** ensures a human authorises a source before the assistant can use it.

## Known limitations
- File-backed storage (JSON + files) — fits the PoC scale, not an enterprise datastore.
- Knowledge-intelligence and guardrails are heuristic/LLM v1; thresholds need tuning per corpus.
- Scanned-image PDFs are not OCR'd. Voice/avatar interaction is out of scope for this build.
