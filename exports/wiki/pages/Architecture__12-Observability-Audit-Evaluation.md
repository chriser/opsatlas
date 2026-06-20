# 12. Observability, audit and evaluation

The observability, audit and evaluation layer is separated because the assistant needs to be explainable after each interaction, not only during planned testing. It records the operational evidence needed to understand how an answer was produced, which evidence was retrieved, which model and prompt configuration were used, whether validation passed, and what improvement actions were identified.

This layer supports trust, governance and iterative improvement. It allows the build team and stakeholders to distinguish between a weak answer, a weak retrieval result, missing source material, a model limitation or a user experience issue. It also creates the evidence base for quality review and future backlog prioritisation.

| Capability | Purpose |
| --- | --- |
| Query and response logs | Record what was asked, what response was returned, when it happened and which user/session context was relevant within agreed privacy controls. |
| Retrieved evidence trace | Show which source sections, document records and metadata were used to support the answer. |
| Model and prompt version tracking | Record model name, provider route, prompt version, temperature/settings and response schema so behaviour can be reproduced and compared. |
| Validation results | Capture whether the answer passed support checks, citation checks, confidence checks and refusal rules. |
| Retrieval accuracy checks | Measure whether the system found the right evidence for golden questions and real user queries. |
| Error and failure monitoring | Capture failed retrievals, model errors, timeout issues, speech conversion problems and validation failures. |
| Audit trail | Preserve traceability across source processing, retrieval, model output, validation and response delivery. |
| Improvement backlog | Convert repeated failures, weak answers, missing sources and feedback patterns into governed improvement items. |
