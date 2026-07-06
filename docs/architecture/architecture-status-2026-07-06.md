# Architecture Status - 2026-07-06

## Purpose

This note is the current architecture reality pass for OpsAtlas. It is intended
to stop the DT603 submission and ADO Wiki from describing an older version of
the platform.

## Current Product Shape

OpsAtlas is now a local governed knowledge platform with five main capability
areas:

| Area | Current status | Primary evidence |
|---|---|---|
| Source governance | Implemented. Internal uploads, bulk upload, external public snapshots, approval and ingestion states are tracked before content is used. | `src/assistant/sources/register.py`, `src/assistant/ingestion/service.py`, Governance and System UI |
| Grounded answering | Implemented. Written Query uses approved-source retrieval, citations, guardrails, answer-path telemetry and optional ontology evidence. | `src/assistant/answer/service.py`, `docs/evidence/grounded-evidence.md` |
| Process intelligence | Implemented. Process Registry extracts roles, systems, controls, dependencies, business rules and local SVG process diagrams from approved sources. | `src/assistant/process/registry.py`, `src/assistant/process/diagram.py`, `docs/architecture/custom-process-svg-renderer.md` |
| Governance reasoning | Implemented. Quick Scan is deterministic; Full Governance Review uses pairwise reasoning through a standalone local microservice and a benchmark-selected adjudicator. | `docs/benchmark/compliance/reasoning-engine-benchmarking-and-tuning-2026-07-05.md`, `docs/data-and-governance/compliance-reasoning-service.md` |
| Ontology-assisted answering | Implemented for structured process questions. OAG-first routes structured process facts through the governed ontology, while narrative questions keep document RAG as the baseline. | `src/assistant/ontology/*`, `docs/benchmark/oag/oag-benchmark-method-and-decision.md` |
| Enterprise Activity Model | Implemented. EAM projects ontology process evidence into Activity, Accountability, Risk Heat and Relationship views, with scale and provenance tests. | `src/assistant/eam/*`, `docs/architecture/enterprise-activity-model.md` |

Supporting capabilities include Analytics evidence reports, validation protocol
catalogues, value analytics, governance history, simulator controls, Avatar Lab
proof-of-concept flows and Process Stress Lab diagnostics.

## Core Runtime Boundary

The main app remains the system of record for source registration, ingestion,
retrieval, analytics, process extraction and ontology state. The compliance
reasoning service is deliberately separate because pairwise governance
reasoning is slower, model-dependent and more experimental than the rest of the
control panel.

The practical boundary is:

- main API: source, governance UI, retrieval, analytics, process registry,
  ontology query/actions and answer orchestration;
- compliance reasoning service: long-running internal/external review jobs,
  same-obligation screening, LLM adjudication, markdown export and cancellation;
- local model runtime: Ollama models used by answer generation, embeddings and
  governance adjudication.

## Current Architecture Decisions

1. Document RAG remains the baseline for narrative answers.
2. OAG-first is the production Ask routing mode for structured process facts.
3. OAG-only is a benchmark boundary probe, not a user-facing operating mode.
4. Governance review exposes two operator modes: Quick Scan and Full Governance
   Review. Balanced remains an internal screen/compatibility mode.
5. Full Governance Review defaults to `qwen2.5:14b-instruct`; the same-obligation
   screen remains `deepseek-r1:8b`.
6. The earlier Operating Model page is retired in favour of the Enterprise
   Activity Model. EAM is the current operating-intelligence canvas and is
   validated by `VAL-EAM-001`.
7. Process Stress Lab is a scenario-planning diagnostic. It is not used as proof
   of live operational risk.

## Current Validation Evidence

| Evidence | Current reference | Status |
|---|---|---|
| Compliance reasoning benchmark and decision | `docs/benchmark/compliance/reasoning-engine-benchmarking-and-tuning-2026-07-05.md` | Accepted |
| OAG holdout scorecard | `docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-2026-07-06T19-47-56+00-00.md` | Accepted for OAG-6 structured holdout evidence |
| OAG method and decision note | `docs/benchmark/oag/oag-benchmark-method-and-decision.md` | Current |
| Grounded answer evidence | `docs/evidence/grounded-evidence.md` | Current but screenshot evidence still operator-owned |
| Analytics validation protocol | `docs/evidence/analytics-validation-protocol.md` and `/api/analytics/validation-evidence` | Current after this pass |
| Enterprise Activity Model validation | `VAL-EAM-001`, `tests/test_eam_scale.py`, `tests/test_eam_dynamic_update.py` | Current EAM projection/scale/provenance evidence |
| Pipeline | `azure-pipelines.yml` | Runs ruff, pytest, frontend build and GitHub mirror |

## Known Limitations

- OAG-first is strong for structured process facts but still depends on document
  RAG for narrative and mixed reasoning.
- The latest OAG holdout run is decision-grade for the OAG-6 slice, but it is
  not a universal claim that every future question should bypass documents.
- Governance reasoning is a review queue, not legal advice or automated policy
  approval.
- External-source snapshots provide dated review evidence; they do not prove
  that all current law or guidance has been captured.
- Value analytics remain assumption-led until live telemetry validates the
  estimates.
- Process Stress Lab scores are deterministic heuristics, not operational
  forecasts.
- EAM coverage shows evidence breadth in approved ontology evidence, not live
  operating-model completeness.

## Next Readiness Work

`#1174` should capture the final regression, pipeline and UAT evidence after the
remaining product-polish slices are complete. The final submission pack should
then reuse this status note, the evidence index and the validation report rather
than rewriting the architecture story from scratch.
