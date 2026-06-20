# 6. Functional flow

| Step | Flow | Responsible architecture module |
| --- | --- | --- |
| 1 | Business knowledge sources are identified and selected for use, such as anonymised process maps, SME interview notes, onboarding artefacts, operating model material and feedback data. | 1. Source Knowledge Layer |
| 2 | Each source is registered so the system knows what the document is, where it came from, what type of content it contains and whether it is approved for use. | 2. Ingestion & Governance Layer |
| 3 | Sensitive or unsuitable content is removed, redacted, anonymised or generalised before being used by the assistant. | 2. Ingestion & Governance Layer |
| 4 | Prepared content is extracted, normalised, split into meaningful sections and tagged with metadata such as process area, source type, owner, date and sensitivity. | 2. Ingestion & Governance Layer |
| 5 | Cleaned and sectioned content is stored in the knowledge layer, including the document store, vector index, lexical index, process registry and evidence metadata. | 3. Knowledge & Index Layer |
| 6 | A user asks a question through the web interface, either by typing or using voice input. | 4. Interaction Channels |
| 7 | If the user speaks, the voice input is converted into text before it is processed by the same assistant flow as a typed question. | 4. Interaction Channels |
| 8 | The assistant receives the request, manages session context, applies access assumptions and routes the request into the correct assistant flow. | 5. Assistant API & Session Layer |
| 9 | The RAG layer analyses the question and decides which retrieval strategy and evidence sources are required. | 6. RAG Orchestration Layer |
| 10 | The RAG layer searches the knowledge indexes and retrieves the most relevant source sections. | 6. RAG Orchestration Layer and 3. Knowledge & Index Layer |
| 11 | Retrieved evidence is assembled into a controlled evidence pack and constrained prompt context for the language model. | 6. RAG Orchestration Layer |
| 12 | The selected model is called to generate a draft answer using only the retrieved evidence. This may use a local model runtime or an approved cloud/enterprise model. | 7. Model Runtime Layer |
| 13 | The draft answer is checked against the retrieved evidence. Unsupported claims, weak confidence, refusal conditions, citation support and canonical response text are handled here. | 8. Validation & Response Layer |
| 14 | A final response is produced for the user, including a clear answer, supporting evidence, confidence markers, citations, or a refusal if the available knowledge is insufficient. | 8. Validation & Response Layer |
| 15 | The answer is returned to the user through the interaction channel. If voice output is enabled, the validated canonical answer is converted into speech. | 4. Interaction Channels |
| 16 | Usage data is captured, including question topic, process area, repeated themes, onboarding friction and documentation gaps. | 9. Analytics & Insight Layer |
| 17 | The analytics layer produces insight into knowledge demand, process confusion, documentation quality, process inefficiency, commercial impact and possible future demand. | 9. Analytics & Insight Layer |
| 18 | Test cases, benchmark questions, regression tests, model comparisons and feedback scores are used to check whether the assistant is improving over time. | 10. Build, Test & Evaluation Layer |
| 19 | System behaviour is monitored and audited, including query logs, retrieved evidence traces, model/prompt versions, validation results, failures and improvement actions. | 12. Observability, Audit & Evaluation |
| 20 | Issues, improvements, risks and future build tasks are added into the delivery backlog and managed through Azure DevOps governance. | 11. Delivery Governance Layer |
| 21 | Future development is planned and controlled through backlog items, pipelines, release gates, module status logs, AI-assisted development logs and security/ethics controls. | 11. Delivery Governance Layer |
