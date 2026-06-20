# 10. Proposed technology approach

The technical stack should stay flexible while still being specific enough to support planning. The table below describes technology categories rather than forcing final vendor choices too early.

| Area | Candidate approach |
| --- | --- |
| Application/API layer | FastAPI or equivalent Python service framework for clear endpoints, testing and future UI integration. |
| User interface | Lightweight web interface for Q&A, evidence display, feedback capture and diagnostics. |
| Knowledge preparation | Python-based document processing, redaction helpers, metadata extraction and section-building scripts. |
| Search and retrieval | Vector database or vector index combined with lexical fallback search to improve reliability. |
| RAG orchestration | Custom orchestration code or lightweight framework to control query routing, retrieval, evidence assembly and prompting. |
| Model runtime | Provider abstraction supporting local model runtime, approved cloud model, embedding model and model evaluation configuration. |
| Voice services | Speech-to-text and text-to-speech components integrated as optional channels rather than as core dependencies. |
| Analytics | Python, SQL and dashboard tooling to analyse usage, feedback, process gaps and business impact measures. |
| DevOps | Azure DevOps for backlog, repository, pipelines, test evidence, documentation and controlled delivery. |
| Observability and audit | Structured application logging, evidence trace records, model/prompt version metadata, validation outcome tracking, error monitoring and audit dashboards. |
