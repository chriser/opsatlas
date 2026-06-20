# 5. RAG framework and hallucination control

RAG is a central part of the architecture and should be visible as its own layer. The reason is simple: the solution should not ask a language model to answer from general knowledge about the world, the internet or its training data. It should ask the model to interpret a controlled package of evidence retrieved from the assistant’s own knowledge layer.

The RAG orchestration layer should perform five jobs. First, it interprets the user question and decides what retrieval strategy is needed. Second, it searches the vector and lexical indexes. Third, it assembles a small evidence pack with source references and metadata. Fourth, it constructs a prompt that instructs the model to answer only from that evidence. Fifth, it passes the draft answer to validation before it is shown or spoken to the user.

| RAG function | Purpose |
| --- | --- |
| Query routing | Decides whether the question is a process explanation, ownership question, onboarding question, system question, comparison, unsupported request or analytics query. |
| Hybrid retrieval | Combines semantic retrieval from the vector index with deterministic keyword retrieval from the lexical index. |
| Evidence assembly | Selects the best passages, removes duplicates and preserves citations, headings and source metadata. |
| Constrained prompt construction | Builds a prompt that tells the model to answer only from supplied evidence and to state when evidence is insufficient. |
| Validation hand-off | Sends the generated answer to support checks before it is accepted as a final response. |
