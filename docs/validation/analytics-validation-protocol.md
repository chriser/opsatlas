# Analytics and Model Validation Protocol

This protocol records how OpsAtlas analytics and AI-assisted behaviours are
checked before their outputs are used for operational review. The live protocol
catalogue is available through `/api/analytics/validation-evidence` and the
Analytics interface.

## Protocol catalogue

| Protocol | Component | Validation method | Boundary |
| --- | --- | --- | --- |
| VAL-RAG-001 | Grounded answer generation | Labelled questions, expected behaviours, grounding metadata and citations | Does not prove completeness beyond approved source coverage |
| VAL-OAG-001 | Ontology-assisted routing | Three-run RAG-only, OAG-first and OAG-only comparison using tuning and holdout labels | Validates the bounded question set, not universal process knowledge |
| VAL-EAM-001 | Enterprise Activity Model projection | Deterministic ontology projection, scale fixtures and renderer/update tests | Visual analysis of approved ontology evidence, not proof of live operating completeness |
| VAL-SIM-001 | Synthetic persona simulator | Seeded scenarios, replay fingerprints and expectation matching | Synthetic outcomes test boundaries, not real adoption |
| VAL-VALUE-001 | Value analytics | Versioned assumptions, scenario calculations and observed/synthetic event separation | Illustrative until validated with live commercial telemetry |
| VAL-REG-001 | Regulatory impact review | Bounded public-source snapshots, screening and model adjudication with human disposition | Not legal advice and cannot approve organisational knowledge |
| VAL-PROC-001 | Process analytics | Parser, registry and deterministic complexity/risk rubric tests | Diagnostic indicators, not operational risk proof |

Current OAG method and result evidence is recorded in
`docs/benchmark/oag/README.md` and
`docs/benchmark/oag/rag-vs-oag-final-benchmark.json`.

Current EAM evidence is recorded in
`docs/architecture/enterprise-activity-model.md`, `tests/test_eam_scale.py`,
`tests/test_eam_dynamic_update.py` and the current EAM classification report
under `docs/benchmark/eam/`.

## Operating rule

Every analytics claim must point to at least one of:

- a deterministic test or repeatable evaluation command;
- a governed source or versioned assumptions ledger;
- an aggregate event-ledger fact;
- a recorded human review or acceptance result.

Claims without an appropriate evidence type remain marked as requiring
validation. Model findings are review candidates and cannot change approved
knowledge automatically.
