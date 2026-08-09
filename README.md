# OpsAtlas

OpsAtlas is a local-first governed organisational knowledge and operating-intelligence platform. It combines approved document retrieval with a governed ontology to provide cited answers, structured process intelligence, Enterprise Activity Model views, knowledge-governance workflows, and analytics that identify knowledge demand, evidence weaknesses, and improvement opportunities.

The repository contains the delivered proof of concept. Core knowledge processing and model inference run locally; the optional Digital SME uses Anam as a managed avatar and speech-rendering layer.

## Knowledge lifecycle

```mermaid
flowchart LR
    A["Register source"] --> B["Extract and inspect"]
    B --> C["Govern and approve"]
    C --> D["Build document and ontology evidence"]
    D --> E["Ask or investigate"]
    E --> F["Validate, cite, or refuse"]
    F --> G["Record analytics"]
    G --> H["Raise governed improvement action"]
    H --> I["Update and reapprove knowledge"]
```

Only approved sources are available to answering and ontology synchronisation. Document RAG supplies narrative and contextual evidence; ontology-assisted generation (OAG) supplies structured objects and relationships; mixed questions can use both. The local language model interprets a bounded evidence pack and is not treated as organisational truth. Unsupported questions are refused rather than answered from model memory.

See [ARCHITECTURE_STATUS.md](ARCHITECTURE_STATUS.md) for the final module map and [the RAG/OAG design](docs/architecture/05-RAG-Framework.md) for the routing decision.

## Implemented capabilities

- **Source governance:** single and bulk source registration, metadata, extraction, ingestion, approval, rejection, and bounded GOV.UK or legislation.gov.uk snapshots.
- **Knowledge review:** deterministic Quick Scan and model-assisted Full Governance Review, with human disposition and no automatic alteration of approved knowledge.
- **Written Query:** cited answers, confidence and grounding checks, retrieval traces, and evidence-based refusal.
- **Ontology-assisted investigation:** governed objects and links, structured query plans, relational traversal, bounded agent proposals, and audited human-approved actions.
- **Process intelligence:** Process Registry, structured roles/systems/controls/dependencies, and locally rendered deterministic process diagrams.
- **Enterprise Activity Model:** Activity, Accountability, Risk Heat, Relationship, and Digital System views over governed ontology evidence.
- **Analytics:** demand, answer outcomes, evidence paths, citations and grounding, recurring questions, failed retrieval, improvement actions, governance history, process complexity, and assumption-led value modelling.
- **Digital SME:** presents the same validated OpsAtlas answer through Anam avatar and speech rendering. Anam does not independently determine the organisational answer. Voice-question input is outside the final scope.
- **Diagnostic tools:** a synthetic journey simulator and Process Stress Lab remain available as bounded exploratory tools; they do not create governed operating facts.

## Architecture at a glance

| Concern | Implementation |
|---|---|
| Frontend | React, TypeScript, and Vite |
| Core API | Python and FastAPI |
| Source and process data | Controlled local files and JSON |
| Ontology | SQLite object/link store |
| Local AI runtime | Ollama |
| Answering | Hybrid document RAG and OAG-first routing |
| Governance review | Local FastAPI compliance-reasoning service |
| Process diagrams | Local deterministic FastAPI rendering service |
| Digital SME rendering | Anam managed avatar and speech rendering |
| External evidence | Bounded public GOV.UK and legislation.gov.uk sources |
| Delivery | Azure Pipelines lint, test, build, and GitHub mirror |

The FastAPI application remains authoritative for source approval and knowledge state. Supporting reasoning, diagram, and presentation services cannot approve or mutate governed knowledge independently.

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 20+
- [Ollama](https://ollama.com)

Pull the local models used by the default answer and governance profiles:

```bash
ollama pull qwen2.5:7b-instruct
ollama pull qwen2.5:14b-instruct
ollama pull nomic-embed-text
ollama pull deepseek-r1:8b
```

Install dependencies once:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cd frontend
npm install
cd ..
```

Start the local compliance service, core API, and Control Panel:

```bash
./scripts/dev.sh
```

| Service | Local address |
|---|---|
| Control Panel | `http://localhost:5200/` |
| Core API | `http://127.0.0.1:8010/` |
| Compliance reasoning | `http://127.0.0.1:5310/` |

The Process Registry can start its local diagram sidecar through System Overview. It can also be started directly:

```bash
.venv/bin/python -m uvicorn services.process_diagram.app:app --host 127.0.0.1 --port 5300
```

### Optional Digital SME

Digital SME rendering requires an Anam account and two uncommitted environment variables:

```text
ANAM_API_KEY
ANAM_PERSONA_ID
```

Without those values, written answering and all local knowledge capabilities remain available.

### Core configuration

| Variable | Default | Purpose |
|---|---|---|
| `KP_OPERATOR_PASSWORD` | `knowledge-demo` | Local Control Panel login |
| `KP_DATA_DIR` | `data` | Git-ignored local runtime state |
| `KP_OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama endpoint |
| `KP_LLM_MODEL` | `qwen2.5:7b-instruct` | Written answer model |
| `KP_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `KP_MIN_SIMILARITY` | `0.55` | Retrieval relevance threshold |
| `KP_COMPLIANCE_BALANCED_LLM_MODEL` | `deepseek-r1:8b` | Bounded same-obligation screen |
| `KP_COMPLIANCE_DEEP_LLM_MODEL` | `qwen2.5:14b-instruct` | Full-review adjudicator |
| `PROCESS_DIAGRAM_SERVICE_URL` | `http://127.0.0.1:5300` | Local diagram sidecar |

Additional bounded review, retrieval, and reduced-load options are defined in the corresponding service code and can be overridden through environment variables.

## Evaluation evidence

The accepted decision-grade RAG/OAG benchmark contains 69 labelled questions, three configurations, three repeated runs, and 621 total executions. On the untouched 24-question holdout, OAG-first achieved `68/72` (94.44%) versus RAG-only at `53/72` (73.61%) and OAG-only at `48/72` (66.67%). OAG-first was also faster than RAG-only in this measured local proof-of-concept workload.

The result supports a hybrid route: prefer ontology evidence for structured organisational facts, while retaining document RAG for narrative, nuanced, and mixed questions. It is not a universal enterprise-performance claim.

- [Benchmark method and decision](docs/benchmark/oag/README.md)
- [Final human-readable result](docs/benchmark/oag/rag-vs-oag-final-benchmark.md)
- [Final raw result](docs/benchmark/oag/rag-vs-oag-final-benchmark.json)
- Reproducible harness: `scripts/evaluate_rag_vs_oag.py`

## Repository structure

```text
src/assistant/              Core backend modules
frontend/                   React and TypeScript Control Panel
services/                   Compliance and process-diagram sidecars
scripts/                    Startup, evaluation, import, and data tools
tests/                      Automated backend and evaluation tests
config/                     EAM and simulator configuration
automation/azure_devops/    Reusable delivery automation
docs/architecture/          Final design and module documentation
docs/benchmark/             Current reproducible benchmark evidence
docs/data-and-governance/   Data-operation procedures
docs/validation/            Product validation records and methods
docs/ways-of-working/       Authentic delivery governance and handover history
```

## Testing and CI

Run the same core checks used by CI:

```bash
ruff check .
.venv/bin/python -m pytest
cd frontend
npm ci
npm run build
```

`azure-pipelines.yml` runs linting, backend tests, and the frontend production build. After CI, it mirrors the repository to GitHub using a protected pipeline secret.

## Data and governance boundaries

- Runtime data is stored locally under the git-ignored `data/` directory.
- The repository uses anonymised, synthetic, or generalised demonstration material; confidential enterprise source data is not committed.
- Human approval is required before a source becomes usable knowledge.
- Model-generated governance findings require human review and cannot silently modify approved knowledge.
- Analytics and value outputs are decision support, not automatic organisational decisions.

## Known limitations

- The corpus and evaluation data are anonymised, synthetic, or generalised rather than live enterprise data.
- There are no direct live enterprise-system integrations.
- Evaluation is local and single-user; enterprise concurrency, high availability, managed storage, SSO, and role-based access control are not implemented.
- Ontology quality depends on approved source quality, extraction coverage, reconciliation rules, and schema coverage.
- External knowledge review is bounded to explicitly registered public sources.
- Exhaustive pairwise governance review scales quadratically and can take many hours on local hardware.
- Business-value outputs are assumption-led and require validation against operational baselines.
- Scanned-image PDF OCR and voice-question input are outside the final scope.
- Digital SME rendering depends on the managed Anam service when enabled.
