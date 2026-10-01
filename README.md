# OpsAtlas

> **Two versions since 26 September 2026.** This folder and branch are **OpsAtlas Sales**: it uses only the data derived from DT603, it has Tibi, and it starts with `scripts/start-tiberius-sales.sh` at http://127.0.0.1:8780.
>
> **OpsAtlas Classic**, the DT603 proof of concept described below, is preserved unchanged at tag `opsatlas-v1-dt603-final`. It runs from its own folder, with its own data, via `./scripts/dev.sh`. See [OpsAtlas Classic and OpsAtlas Sales](docs/opsatlas-classic-and-sales.md).

OpsAtlas is a local-first governed organisational knowledge and operating-intelligence platform. It combines approved document retrieval with a governed ontology to provide cited answers, structured process intelligence, Enterprise Activity Model views, knowledge-governance workflows, and analytics that identify knowledge demand, evidence weaknesses, and improvement opportunities.

The repository contains the delivered proof of concept. Core knowledge processing and model inference run locally; the optional Digital SME uses Anam as a managed avatar and speech-rendering layer.

Tibi, the voice companion that grew out of the [SME Interviewer initiative](docs/initiatives/sme-interviewer/README.md), is part of OpsAtlas Sales: local speech, conversation, sales rehearsal and process interviews. Every Tibi engine version passes a latency gate before it goes live; the versions and the gate are recorded under `docs/initiatives/sme-interviewer/`.

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
- **Knowledge review:** deterministic Quick Scan and a statement-level governance review with a local judge, with human disposition and no automatic alteration of approved knowledge. The exhaustive pairwise Full Governance Review stays in OpsAtlas Classic.
- **Identity and access:** personal accounts, roles and exact permissions per knowledge space, sessions with CSRF protection and a hash-chained audit; see [the IAM guide](docs/iam/README.md).
- **Knowledge spaces:** the Product Guide, the Sales Playbook, system settings and organisation spaces, each on its own partition; governed editing with drafts, versions and approval.
- **Written Query:** cited answers, confidence and grounding checks, retrieval traces, and evidence-based refusal.
- **Ontology-assisted investigation:** governed objects and links, structured query plans, relational traversal, bounded agent proposals, and audited human-approved actions.
- **Process intelligence:** Process Registry, structured roles/systems/controls/dependencies, and locally rendered deterministic process diagrams.
- **Enterprise Activity Model:** Activity, Accountability, Risk Heat, Relationship, and Digital System views over governed ontology evidence.
- **Analytics:** demand, answer outcomes, evidence paths, citations and grounding, recurring questions, failed retrieval, improvement actions, governance history, and process complexity. Assumption-led value modelling is parked in OpsAtlas Classic.
- **Digital SME:** presents the same validated OpsAtlas answer through Anam avatar and speech rendering. Anam does not independently determine the organisational answer. Voice-question input is outside the final scope.
- **Diagnostic tools:** the synthetic journey simulator and the Process Stress Lab are parked in OpsAtlas Classic, the DT603 version; OpsAtlas Sales no longer carries them.

## Architecture at a glance

| Concern | Implementation |
|---|---|
| Frontend | React, TypeScript, and Vite |
| Core API | Python and FastAPI |
| Source and process data | Controlled local files and JSON |
| Ontology | SQLite object/link store |
| Local AI runtime | Ollama |
| Answering | Hybrid document RAG and OAG-first routing |
| Governance review | Statement governance with a local judge by default; the compliance-reasoning service stays in OpsAtlas Classic |
| Process diagrams | Local deterministic FastAPI rendering service |
| Digital SME rendering | Anam managed avatar and speech rendering |
| External evidence | Bounded public GOV.UK and legislation.gov.uk sources |
| Delivery | Azure Pipelines lint, test, build, and GitHub mirror |

The FastAPI application remains authoritative for source approval and knowledge state. Supporting reasoning, diagram, and presentation services cannot approve or mutate governed knowledge independently.

## Quick start

### Prerequisites

- Python 3.12 (what CI and the running Mac use)
- Node.js 20+
- [Ollama](https://ollama.com)

Pull the local models OpsAtlas Sales uses:

```bash
ollama pull qwen3.5:4b            # Product Guide answers
ollama pull qwen2.5:7b-instruct   # Tibi's conversation
ollama pull qwen2.5:14b-instruct  # the governance review's judge
ollama pull qwen3.5:35b-a3b       # the second opinion on a conflict; Tibi's process interviews
ollama pull nomic-embed-text      # embeddings
```

OpsAtlas Classic also needs `deepseek-r1:8b` for its compliance review.

Install dependencies once:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock   # the exact, tested versions; requirements-dev.txt states the minimums
cd frontend
npm install
cd ..
```

Start OpsAtlas Sales (the workspace app, which serves the Control Panel and one core per knowledge space):

```bash
./scripts/start-tiberius-sales.sh
```

| Service | Local address |
|---|---|
| Control Panel and API | `http://127.0.0.1:8780/` |
| Tibi voice companion | `http://127.0.0.1:8773/` |
| Process diagrams | `http://127.0.0.1:5300/` |

OpsAtlas Classic, the DT603 version with the compliance-reasoning service, runs from its own folder and data; see
[docs/opsatlas-classic-and-sales.md](docs/opsatlas-classic-and-sales.md).

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
| `KP_DATA_DIR` | `data` | Runtime state of a lone core; the Sales workspace keeps its own under `.runtime/opsatlas-sales/` |
| `KP_OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama endpoint |
| `KP_LLM_MODEL` | `qwen2.5:7b-instruct` | Written answer model; the Sales workspace uses `qwen3.5:4b` |
| `KP_LLM_THINK` | `0` | Whether the answer model may reason before answering (`0`, `1`, `auto`); off keeps answers to seconds |
| `KP_LLM_NUM_PREDICT` | `1536` | The longest answer, in tokens (`0` for no bound) |
| `KP_LLM_TIMEOUT` | `120` | Seconds a generation may take |
| `KP_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `KP_MIN_SIMILARITY` | `0.55` | Retrieval relevance threshold |
| `PROCESS_DIAGRAM_SERVICE_URL` | `http://127.0.0.1:5300` | Local diagram sidecar |

Additional bounded review, retrieval, and reduced-load options are defined in the corresponding service code and can be overridden through environment variables.

People sign in with personal accounts. The first administrator is created on the host with `python -m assistant.iam bootstrap`; see [the IAM guide](docs/iam/README.md). `KP_OPERATOR_PASSWORD` only serves the single-password setup the tests use.

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
services/                   Sales workspace app, Tibi voice companion, process-diagram service
scripts/                    Startup, evaluation, import, and data tools
tests/                      Automated backend and evaluation tests
config/                     EAM configuration
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
cd ..
node --test tests/*.mjs
```

`azure-pipelines.yml` builds every branch on push, on Python 3.12: the pinned dependencies and their audit, Ruff, the backend tests, the control panel's production build and every JavaScript test. After a successful branch build it mirrors the branch to GitHub using a protected pipeline secret.

## Data and governance boundaries

- Runtime data is stored locally and is git-ignored: OpsAtlas Sales keeps its workspace under `.runtime/opsatlas-sales/`, and OpsAtlas Classic its `data/` folder in its own checkout.
- The accepted 21-document governed knowledge corpus uses anonymised/generalised learning material.
- Synthetic data is used separately for controlled analytics workloads, regression fixtures, and test activity.
- No confidential live enterprise source material is committed.
- Human approval is required before a source becomes usable knowledge.
- Model-generated governance findings require human review and cannot silently modify approved knowledge.
- Analytics outputs are decision support, not automatic organisational decisions.

## Known limitations

- The governed corpus is anonymised/generalised rather than live enterprise data; synthetic test activity is kept separate from observed/operator activity.
- The benchmark is bounded to the anonymised/generalised proof-of-concept knowledge domain.
- There are no direct live enterprise-system integrations.
- Personal accounts, roles and exact permissions exist, single-factor and local. SSO, multi-factor sign-in, enterprise concurrency, high availability and managed storage are not implemented.
- Ontology quality depends on approved source quality, extraction coverage, reconciliation rules, and schema coverage.
- External knowledge review is bounded to explicitly registered public sources.
- The statement-level governance review compares each statement with its nearest neighbours, not every document pair; OpsAtlas Classic's exhaustive pairwise review took more than 35 hours.
- Scanned-image PDF OCR and voice-question input are outside the final scope.
- Digital SME rendering depends on the managed Anam service when enabled.
