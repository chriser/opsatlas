# 3. Target high-level architecture diagram

Figure 1 shows the proposed architecture as a single-view artefact. The diagram separates business knowledge sources, ingestion and governance, knowledge indexing, interaction channels, assistant API and session handling, RAG orchestration, model runtime, validation and response, analytics and insight, build and test activity, delivery governance, and a dedicated observability, audit and evaluation layer. The most important change from a generic chatbot design is the explicit RAG, validation and evidence-trace path between the user, the knowledge base and the model.

> **Figure 1. Proposed high-level architecture for the AI Knowledge and Analytics Assistant.**

![AI Knowledge Assistant (1).png](/.attachments/AI%20Knowledge%20Assistant%20(1)-2bed5d11-77e3-4653-a16a-fb386bb2c1c3.png)