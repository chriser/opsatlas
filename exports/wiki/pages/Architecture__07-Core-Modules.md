# 7. Core modules and responsibilities

The proposed system should be built as a modular monolith first. This avoids premature microservice complexity but still gives enough separation to support safe, iterative development. Each module owns a clear responsibility and should expose stable schemas or contracts to the rest of the system.

| Module | Owns | Produces | Boundary rule |
| --- | --- | --- | --- |
| Source and Data Governance | Owns the source register, approval status, sensitivity classification and rules for what can be processed. | Raw sources with metadata and governance status. | Should not generate answers or analytics interpretations. |
| Ingestion and Preparation | Owns extraction, sanitisation, redaction, normalisation and section building. | Clean processed sections and metadata. | Should not decide final answer wording. |
| Knowledge and Indexing | Owns document store, vector index, lexical index and process registry. | Searchable evidence and process entities. | Should not call the LLM directly. |
| Assistant API and UI | Owns request handling, session state, user interface and response display. | Typed or spoken question; structured response. | Should not contain retrieval or model business logic. |
| RAG Orchestration | Owns query routing, retrieval strategy, evidence assembly and prompt construction. | Evidence pack and constrained prompt. | Should not store raw confidential sources. |
| Model Runtime | Owns model provider gateway, model configuration, embeddings and model comparison. | Draft answer and model diagnostics. | Should not be treated as source of truth. |
| Validation and Safety | Owns citation support checks, refusal rules, confidence markers and answer quality gates. | Validated final answer. | Should not rewrite source evidence. |
| Voice Services | Owns speech-to-text, text-to-speech and canonical speakable answer handling. | Voice input/output streams. | Should not produce a different answer from the validated text. |
| Analytics and Insight | Owns usage analytics, topic modelling, onboarding friction metrics, process gap analysis and commercial impact measures. | Dashboards, datasets and insight outputs. | Should not alter retrieval behaviour without controlled change. |
| Build and Evaluation | Owns test sets, golden questions, regression tests, model comparisons, feedback scoring and quality dashboards. | Evidence of build quality and improvement. | Should not make unreviewed production changes. |
| Delivery Governance | Owns Azure DevOps backlog, pipelines, decision logs, module status, security and AI-assistance usage log. | Auditable delivery trail. | Should not be bypassed for implementation shortcuts. |
| Observability, Audit and Evaluation | Owns query and response logs, retrieved evidence traces, model and prompt version tracking, validation outcomes, retrieval checks, error monitoring and audit records. | Traceable operating evidence, audit trail and improvement backlog inputs. | Should not directly change model behaviour or business logic without governed backlog approval. |
