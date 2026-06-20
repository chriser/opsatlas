# 4. Diagram element glossary

The diagram is intentionally high level, but every element has a specific purpose. This section acts as a legend so that the architecture can be understood by non-specialist stakeholders as well as technical reviewers.

| Element | Purpose |
| --- | --- |
| Anonymised process maps | Business process diagrams with confidential names, system identifiers and sensitive operational detail removed or generalised. |
| SME interview notes | Structured knowledge captured from subject matter experts, sanitised before being used as source material. |
| Onboarding artefacts | Training packs, role guides and induction materials used by new joiners or cross-functional team members. |
| Operating model material | Documents that explain team ownership, market accountability, decision routes, hand-offs and system responsibilities. |
| Usage and feedback data | Questions, feedback ratings and evaluation comments generated through the pilot, stored in a controlled way for analytics. |
| Source register | A catalogue of every source used by the assistant, including source type, owner, sensitivity level, version, approval status and processing state. |
| Sanitisation and redaction | The process of removing or generalising confidential, personal, commercial or sensitive information before indexing. |
| Extraction and normalisation | Conversion of source files into consistent machine-readable text, tables and metadata so they can be searched reliably. |
| Section builder | Logic that splits long documents into meaningful sections, preserving headings, process steps and context rather than creating arbitrary chunks. |
| Metadata tagging | Labels such as process, team, market, source type, sensitivity, date and confidence that help retrieval and governance. |
| Document store | The controlled store of processed source sections and source metadata. |
| Vector index | A semantic search index that helps find relevant material even when the user uses different wording from the source document. |
| Lexical index | A keyword-style search fallback that supports precise phrase matching, IDs, names, terminology and deterministic retrieval. |
| Process registry | A structured catalogue of known processes, owners, systems, hand-offs and process variants. |
| Evidence metadata | Information attached to retrieved evidence so the assistant can cite source, section, date, process and confidence. |
| Web Q&A interface | The primary user interface for asking questions and viewing grounded answers, citations and optional diagnostics. |
| Voice input | An optional interaction channel where the user asks a question verbally. |
| Speech-to-text | The component that converts voice input into a text question before it enters the standard assistant pipeline. |
| Voice output | An optional channel for listening to the answer instead of only reading it. |
| Text-to-speech | The component that reads the final canonical answer after validation, avoiding unapproved paraphrasing. |
| Assistant API and session layer | The application boundary that receives requests, manages session context and returns structured responses. |
| RAG orchestration layer | The control layer that retrieves evidence, assembles context and builds the constrained prompt used by the model. |
| Model runtime layer | A provider abstraction for LLMs and embedding models, allowing local or cloud models to be evaluated without redesigning the system. |
| Validation and response layer | Checks whether the generated answer is supported by evidence and formats the final text, citations, confidence and speakable response. |
| Analytics and insight layer | Analyses usage, questions, feedback and process knowledge patterns to identify knowledge gaps and improvement opportunities. |
| Build, test and evaluation layer | Stores golden test questions, retrieval and answer benchmarks, model comparison tests, regression tests, feedback scoring and quality dashboards used to prove the assistant is improving safely. |
| Delivery governance layer | The Azure DevOps and documentation control plane covering backlog, pipelines, decision logs, module status, AI coding-agent usage logs and security/ethics controls. |
| Observability, audit and evaluation layer | Captures query and response logs, evidence retrieval traces, model and prompt versions, validation outcomes, retrieval accuracy checks, failure monitoring, audit trail and improvement backlog items. |
