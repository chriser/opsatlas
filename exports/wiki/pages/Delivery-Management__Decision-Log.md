# Decision Log

This page records key architecture, delivery, data, ethics and implementation decisions for the AI Knowledge and Analytics Assistant project.

## Purpose

The decision log provides traceability. It explains why major choices were made, what alternatives were considered and what impact the decision has on delivery, risk, ethics or technical design.

## Decision log

| ID | Date | Decision | Rationale | Alternatives considered | Impact | Status |
|---|---|---|---|---|---|---|
| DEC-001 | 2026-06-06 | Use Azure DevOps as the delivery governance platform | Provides backlog, repo, Wiki, test case and delivery plan evidence in one controlled environment | Local-only documentation; manual spreadsheet tracking | Stronger traceability and better DT602/DT603 evidence | Accepted |
| DEC-002 | 2026-06-06 | Use a modular monolith for the first implementation | Keeps delivery practical while preserving internal module boundaries | Microservices; single unstructured prototype | Reduces complexity and supports controlled iteration | Accepted |
| DEC-003 | 2026-06-06 | Use vertical delivery slices rather than horizontal module delivery | Allows the MVP to run end-to-end early, then harden progressively | Build all modules first, integrate later | Reduces late discovery risk | Accepted |
| DEC-004 | 2026-06-06 | Use anonymised or synthetic learning data for the PoC | Avoids exposing confidential, personal or commercially sensitive material outside approved controls | Use real internal data; use public generic data only | Supports ethical and policy-aligned delivery | Accepted |
| DEC-005 | 2026-06-06 | Use RAG as the core answer pattern | Keeps answers grounded in controlled source evidence rather than model memory | General chatbot; rules-only search | Reduces hallucination risk and improves explainability | Accepted |
| DEC-006 | 2026-06-06 | Treat voice as an optional interaction channel, not a separate answer pipeline | Ensures spoken answers use the same validated canonical response | Separate voice assistant flow | Avoids uncontrolled paraphrasing or bypassing validation | Accepted |
| DEC-007 | 2026-06-06 | Use Azure DevOps Wiki as the living architecture and evidence space | Keeps planning, architecture and delivery evidence visible and auditable | Word documents only; repo markdown only | Better governance and easier screenshots for assessment | Accepted |

## Future decision areas

| Area | Decision still required |
|---|---|
| Model runtime | Whether to use local model runtime only, cloud model, or hybrid provider abstraction during build |
| Vector store | Whether to use a local vector index, lightweight database or managed vector service |
| UI implementation | Whether the MVP uses API-only, simple web UI, or both |
| Logging implementation | Format and storage approach for trace logs and usage events |
| Analytics output | Whether to use Python notebook, CSV output, dashboard, or simple web report |
| Voice proof | Which speech-to-text and text-to-speech option is used for the proof |
