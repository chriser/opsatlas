# 2. Architectural intent and design principles

The architecture should be judged against five design principles. These principles are not decorative; they directly shape how the system should be built, tested and governed.

| Principle | Meaning for the build |
| --- | --- |
| Grounded by design | Answers should be based on retrieved source evidence rather than general model memory. This reduces hallucination risk and makes the assistant suitable for process knowledge where accuracy and provenance matter. |
| Inspectable by design | The system should expose citations, retrieved evidence, answer confidence, validation status and diagnostic information. A user or reviewer should be able to see why an answer was produced. |
| Modular by design | Each major capability should have a clear responsibility and interface. Ingestion should not own answer generation; analytics should not own retrieval; model runtime should not own source governance. |
| Governed by design | Data handling, sanitisation, access assumptions, model selection, AI coding-agent use and evaluation results should be documented as part of the architecture, not added later. |
| Iterative by design | The solution should be delivered as thin vertical slices. Each slice should prove an end-to-end user value path before deeper sophistication is added. |
