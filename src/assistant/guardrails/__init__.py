"""Guardrails — input checks that keep the assistant focused and safe.

Deterministic (regex) classification into manipulation / focus / content-safety
categories, applied before answer generation. This is a v1 heuristic layer; the
grounding prompt is the second line of defence. An LLM-based classifier could
replace the heuristics later.
"""
