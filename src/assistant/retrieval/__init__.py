"""Knowledge retrieval module.

Hybrid retrieval over ingested sections: lexical (BM25) always, plus semantic
(local embeddings via Ollama) when available, fused by reciprocal rank fusion.
Degrades gracefully to lexical-only when no embedder is configured or reachable.
"""
