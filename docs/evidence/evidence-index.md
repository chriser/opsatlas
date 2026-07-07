# Evidence Index

Last updated: 2026-07-06

This index points to the current evidence artefacts for OpsAtlas. It separates
decision-grade evidence from older benchmark history so the DT603 write-up can
cite the right files without losing the audit trail.

## Architecture and Build Governance

| Evidence | File or location | Use |
|---|---|---|
| Architecture status reality pass | `docs/architecture/architecture-status-2026-07-06.md` | Current module map, decisions and limitations |
| Core modules | `docs/architecture/07-Core-Modules.md` | Current architecture module catalogue |
| RAG and OAG architecture | `docs/architecture/05-RAG-Framework.md` | RAG baseline, OAG-first routing and benchmark interpretation |
| Enterprise Activity Model architecture | `docs/architecture/enterprise-activity-model.md` | Ontology-backed operating-intelligence canvas, validation and boundaries |
| Build governance | `docs/ways-of-working/Build-Governance.md` | AI-assisted delivery control and review approach |
| Agent handover log | `docs/ways-of-working/Agent-Handover-Log.md` | Chronological delivery, test and decision trail |

## Current Benchmark Evidence

| Evidence | File or location | Current interpretation |
|---|---|---|
| Governance reasoning benchmark and model decision | `docs/benchmark/compliance/reasoning-engine-benchmarking-and-tuning-2026-07-05.md` | Accepted decision: Full Governance Review defaults to `qwen2.5:14b-instruct`; `deepseek-r1:8b` remains the same-obligation screen |
| OAG benchmark method and decision | `docs/benchmark/oag/oag-benchmark-method-and-decision.md` | Current OAG validation method and decision summary |
| OAG-6 holdout scorecard | `docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-2026-07-06T19-47-56+00-00.md` | Decision evidence for structured OAG holdout: OAG-first 67/72 (93%) versus RAG-only 47/72 (65%) |
| OAG labels | `tests/evaluation/rag_vs_oag_questions.json` | Tuning/holdout split for RAG-vs-OAG evaluation |
| OAG harness | `scripts/evaluate_rag_vs_oag.py` | Repeatable benchmark runner |
| Compliance labels | `tests/evaluation/compliance_reasoning_labels.json` | Training/holdout labels for governance reasoning evaluation |
| Compliance harness | `scripts/evaluate_compliance_reasoning.py` | Repeatable governance reasoning benchmark runner |

Older OAG and compliance scorecards are kept under `docs/benchmark/oag/old/`
and `docs/benchmark/compliance/Old/`. They are useful for the evaluation story
and benchmark-learning narrative, but they should not be cited as the current
decision unless the write-up is describing the iteration history.

## Product Evidence

| Evidence | File or endpoint | Use |
|---|---|---|
| Grounded answer evidence | `docs/evidence/grounded-evidence.md` | Approved-source answering, citations and screenshot checklist |
| Analytics validation protocol | `docs/evidence/analytics-validation-protocol.md` | Current validation protocol catalogue |
| Analytics DT603 traceability matrix | `docs/evidence/analytics-dt603-traceability-matrix.md` | Maps analytics surfaces to MLO/KSB/S52/S53 evidence and screenshot checklist |
| Live validation report | `/api/analytics/validation-evidence` | UI/API evidence for KSB mapping and validation protocols |
| Analytics markdown export | `/api/analytics/report.md` | Exportable evidence report |
| Analytics PDF export | `/api/analytics/report.pdf` | Submission-friendly analytics evidence report |
| Value hypothesis | `docs/evidence/value-hypothesis.md` | Assumption-led value case and limitations |
| Process stress method | `docs/evidence/process-stress-test-method.md` | Diagnostic stress-test methodology |
| Process Stress Lab learning overview | `docs/evidence/process-stress-lab-learning-overview.md` | Lay explanation of the stress-lab page |
| Custom SVG process renderer | `docs/architecture/custom-process-svg-renderer.md` | Process map rendering handover |
| Enterprise Activity Model validation | `docs/architecture/enterprise-activity-model.md` and `VAL-EAM-001` | EAM projection, four SVG views, scale fixture, provenance and dynamic-update evidence |

## UAT and Pipeline Evidence

| Evidence | Location | Current status |
|---|---|---|
| Sprint 3 UAT | Azure Test Plans / ADO comments | Human reported all UAT scenarios passed on 2026-07-06 |
| Latest OAG delivery pipeline | Azure Pipeline build after commit `4ba9ed2` | Passed (`#394`) |
| Pipeline definition | `azure-pipelines.yml` | Python 3.11, ruff, pytest, Node 20 frontend build and GitHub mirror |
| Manual screenshots | Operator captured in Control Panel | Still operator-owned for final submission evidence |

## Known Limitations To Preserve

- Governance reasoning outputs are review candidates, not legal determinations.
- OAG-first is validated for structured process facts; narrative questions still
  need document RAG.
- OAG-only is not a target user mode.
- Enterprise Activity Model coverage is evidence breadth from approved ontology
  evidence, not proof of live operational completeness.
- Process Stress Lab is deterministic scenario triage, not an operational
  forecast.
- Value analytics are assumption-led until live telemetry exists.

## Recommended Citation Pattern

For the final submission, cite current evidence first:

1. Architecture status reality pass.
2. Evidence index.
3. Current validation report.
4. Current OAG and compliance benchmark decision records.
5. Current UAT/pipeline artefacts.

Use older scorecards only to explain the learning journey: baseline, leakage
detection, benchmark saturation, holdout rotation and final model/architecture
decision.
