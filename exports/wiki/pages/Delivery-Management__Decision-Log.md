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
| DEC-008 | 2026-06-22 | Treat knowledge hygiene as a product capability | eGain's AI Knowledge Hub material shows that enterprise AI reliability depends on resolving content silos, inconsistent answers and compliance workflows before answer generation | Allow upload/search without source lifecycle controls; rely on manual document clean-up outside the product | Source register, ingestion status, governance issue detection, duplicate remediation and approved-source gating are part of the product surface | Accepted |
| DEC-009 | 2026-06-22 | Model process knowledge as structured semantic assets | Graphwise positions trusted enterprise AI around a semantic backbone, knowledge graphs, taxonomy/ontology management and compliance intelligence | Store process documents only as flat chunks; use generic tags without explicit process entities | Process Registry extraction, role/system/control/dependency metadata and process-complexity indicators are justified as analytics foundations | Accepted |
| DEC-010 | 2026-06-22 | Require permission-aware, cited retrieval for answers | Glean's Work AI messaging emphasises company context, permissions, explainability, observability and governance as enterprise requirements | Let the assistant answer from any indexed source; show answers without source evidence; defer access governance | Approved-source-only answering, refusal on missing evidence, citations and audit traces remain mandatory controls | Accepted |
| DEC-011 | 2026-06-22 | Measure ingestion and answer quality explicitly | LlamaIndex documentation treats ingestion as a pipeline and evaluation as response faithfulness plus retrieval-quality measurement | Use manual spot checks only; treat ingestion success as enough evidence of quality | Hallucination probes, grounding scores, faithfulness metadata and retriever evaluation become delivery evidence, not optional QA extras | Accepted |
| DEC-012 | 2026-06-22 | Keep agentic and voice channels behind the canonical validated answer flow | Dell-related industry coverage separates autonomous agents from chatbots and highlights sandboxing, guardrails and local control for enterprise agentic AI | Let voice, simulator or future agent channels call model prompts independently; introduce action-taking agents before validation controls | Voice, simulator and future agent-like experiences must reuse the validated answer service until explicit action governance exists | Accepted |
| DEC-013 | 2026-07-05 | Use `qwen2.5:14b-instruct` as the default Compliance Deep Audit model | #1117 compared DeepSeek-R1 8B/14B/32B and Qwen 2.5 7B/14B over three runs. Qwen 14B had the best clean consumer-rights holdout performance, 100% model-only holdout, 91.7% guarded holdout, 100% contradiction precision, 83.3% contradiction recall and 7.3s p95 latency. | Keep DeepSeek-R1 14B because it scored highest on the now-saturated training split; use DeepSeek-R1 32B for maximum reasoning capacity; keep Qwen 7B for speed. | Deep Audit defaults to Qwen 14B. DeepSeek 8B remains the Balanced same-obligation screen. The clean holdout is still small, so future regression runs should grow it; immediate improvement focus moves to guard refinement because guards reduced Qwen clean holdout from 100% model-only to 91.7% guarded. | Accepted |

## Future decision areas

| Area | Decision still required |
|---|---|
| Model runtime | Whether to use local model runtime only, cloud model, or hybrid provider abstraction during build |
| Vector store | Whether to use a local vector index, lightweight database or managed vector service |
| UI implementation | Whether the MVP uses API-only, simple web UI, or both |
| Logging implementation | Format and storage approach for trace logs and usage events |
| Analytics output | Whether to use Python notebook, CSV output, dashboard, or simple web report |
| Voice proof | Which speech-to-text and text-to-speech option is used for the proof |
