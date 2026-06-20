# 14. Modular build methodology

The build method should combine Agile delivery with architecture governance, but the backlog should now be organised primarily by vertical delivery slices rather than isolated technical modules. Azure DevOps Epics represent the major delivery slices. Features represent the capabilities needed to achieve the slice outcome. User Stories describe small testable outcomes within each slice, and Tasks describe the implementation work needed to deliver them. This structure supports rapid prototyping because the MVP is tested by Sprint 3 and later sprints harden or extend an already-working path.

| Delivery artefact | Current use in the sliced plan | Evidence value |
| --- | --- | --- |
| Epics | Represent Slice 0 to Slice 6, from governance foundation through MVP, hardening, analytics, voice, evaluation and final submission pack. | Shows the delivery model is iterative and value-led rather than a late-integrated module build. |
| Features | Represent the major capability increments inside each slice, such as synthetic data, ingestion/indexing, MVP RAG response, retrieval hardening, validation, analytics, voice proof and final evidence. | Shows how architecture modules are delivered through practical increments. |
| User Stories | Define testable user or reviewer outcomes, such as creating the source register, producing a cited answer, validating retrieval quality or proving voice uses the canonical answer path. | Shows that work is decomposed into verifiable outcomes. |
| Technical Tasks | Define implementation activities scoped to a module and slice, such as schemas, adapters, placeholders, tests, evidence capture and documentation updates. | Shows controlled build execution and prevents uncontrolled AI-assisted edits across the whole solution. |
| Delivery Plan markers | Highlight important milestones such as governance start, MVP achieved, validation complete, analytics proof, voice proof and final evidence complete. | Makes the roadmap understandable in one view for assessors and stakeholders. |
| Quality Gates | Retrieval checks, golden questions, grounded-answer validation, refusal tests, voice contract tests, analytics checks and regression tests. | Shows quality is evaluated throughout delivery rather than only at the end. |
| Decision and Risk Logs | Capture architecture choices, ethical constraints, data assumptions, model decisions, AI-coding use and delivery risks. | Provides auditability and supports DT602 ethics/governance evidence. |
| Evidence Index | Collects screenshots, pipeline outputs, Wiki pages, test evidence, logs and limitations against each slice. | Creates a clear route into DT603 build evidence and DT604 retrospective evaluation. |
