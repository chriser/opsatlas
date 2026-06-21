"""Grounded answer module (RAG orchestration + answer generation).

Assembles an evidence pack (full-context for small knowledge bases, else
retrieved passages), builds a constrained, grounding-only prompt, and calls the
model to produce a cited answer that refuses when the evidence is insufficient.
"""
