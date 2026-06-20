# 9. Model and voice architecture decisions

The architecture should name the model layer but should avoid locking the design to one model too early. The correct pattern is a provider abstraction. This means the assistant can use a local model runtime for fast experimentation, an approved cloud or enterprise model where governance permits, and different embedding providers for semantic search. Ollama is a sensible example of a local model runtime, but it should be described as an option rather than a fixed dependency.

| Decision area | Architecture position |
| --- | --- |
| LLM provider gateway | A small abstraction that allows the assistant to route requests to different models without rewriting the RAG or validation layers. |
| Local model runtime option | Useful for experimentation, cost control and offline-style development. Ollama is an example option, subject to hardware and model-quality constraints. |
| Cloud or enterprise model option | Useful where stronger reasoning, enterprise governance, monitoring or approved platform integration is required. |
| Embedding model or service | Creates vector representations of source sections and user questions so semantically similar content can be retrieved. |
| Model configuration | Stores prompt templates, model names, temperature, context limits and response schema settings so runs are repeatable. |
| Model evaluation | Compares model responses using golden questions, retrieval quality, answer support, refusal quality and stakeholder feedback. |
| Speech-to-text | Converts spoken questions into text before they enter the normal assistant pipeline. |
| Text-to-speech | Reads the final validated answer. It should not be allowed to invent, summarise or paraphrase beyond the canonical response. |
