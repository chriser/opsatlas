# Final Analytics Method Write-Up

This project uses a layered analytics method for the AI Knowledge and Analytics Assistant.
The method is intentionally evidence-led: every claim should be traceable to a governed
source, deterministic test, aggregate event, UAT result or assumptions ledger.

## Analytics layers

| Layer | Purpose | Implemented evidence |
|---|---|---|
| Descriptive | Show what happened across usage, source lifecycle and governance | Scorecard, charts, event history, governance history |
| Diagnostic | Explain likely causes and risk indicators | Knowledge-gap clusters, process complexity, key-person-risk indicators |
| Simulation | Test expected behaviours before live deployment | Synthetic persona simulator, replay fingerprints, regulatory impact triage |
| Value | Show how benefit would be measured | Assumptions ledger, scenario metrics, observed aggregate value events |
| Validation | Keep claims disciplined | KSB traceability matrix, validation protocol catalogue, regression tests |

## Evidence boundary

The platform demonstrates a working method for turning governed knowledge into analytics.
It does not yet prove final ROI, legal compliance, operational risk reduction or enterprise
adoption. Those claims require live telemetry, sponsor-approved assumptions and human review.

## Exportable report

The Analytics page now exposes an export action backed by `/api/analytics/report.md`.
The report is markdown so it can be attached to ADO, copied into Wiki pages or used as UAT
evidence. It avoids raw source text, generated answers and full prompt/answer traces.

## Validation protocol

The active validation protocols are:

- `VAL-RAG-001`: grounded answer generation.
- `VAL-SIM-001`: synthetic persona simulation.
- `VAL-VALUE-001`: value analytics.
- `VAL-REG-001`: regulatory impact simulation.
- `VAL-PROC-001`: process analytics.

Each protocol has a method, metric, acceptance rule, current evidence, cadence and boundary
statement in the `/api/analytics/validation-evidence` response.
