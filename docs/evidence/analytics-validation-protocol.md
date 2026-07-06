# Analytics and Model Validation Protocol

The validation protocol records how analytics and AI-assisted behaviours are checked before
they are used as evidence. It is available through `/api/analytics/validation-evidence` and
the Analytics page.

## Protocol catalogue

| Protocol | Component | Validation method | Boundary |
|---|---|---|---|
| VAL-RAG-001 | Grounded answer generation | Benchmark questions, expected behaviours, grounding metadata and citations | Does not prove factual completeness beyond approved source coverage |
| VAL-OAG-001 | Ontology-assisted generation routing | RAG-only versus OAG-first benchmark over tuning/holdout process-question labels | Validates structured process routing, not complete process knowledge |
| VAL-SIM-001 | Synthetic persona simulator | Seeded scenario selection, replay fingerprints and expectation matching | Synthetic outcomes test behaviour boundaries, not real adoption |
| VAL-VALUE-001 | Value analytics | Assumptions ledger validation and observed value-event aggregation | Illustrative until validated with live commercial telemetry |
| VAL-REG-001 | Regulatory impact simulation | Deterministic term scan over approved sources and dated public snapshots | Not legal advice or proof that an operating procedure changed |
| VAL-PROC-001 | Process analytics | Parser, registry and rubric tests for complexity/key-person-risk indicators | Diagnostic indicator only, not operational risk proof |

Current OAG evidence is recorded in
`docs/benchmark/oag/oag-benchmark-method-and-decision.md` and the July 6
holdout scorecard
`docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-2026-07-06T19-47-56+00-00.md`.

## Operating rule

Every analytics claim must point to one of:

- A deterministic test or evaluation command.
- A governed source or assumptions ledger.
- An aggregate event ledger fact.
- A UAT screenshot or Azure Test Plans result.

Claims without one of those evidence types should stay marked as `requires_validation`.
