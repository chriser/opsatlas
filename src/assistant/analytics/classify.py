"""Lightweight, deterministic query classification (topic)."""

from __future__ import annotations

# Ordered (topic, keywords); first match wins. Heuristic v1 — an LLM or trained
# classifier could replace this, and more dimensions (role, system) can be added.
_TOPICS: list[tuple[str, list[str]]] = [
    ("checks", ["due diligence", "credit check", "credit", "gate", "approv", "reject", "fail"]),
    ("finance_mapping", ["mapping", "finance", "supplier id", "identifier", "reconcil", "invoic", "payment"]),
    ("validation", ["validat", "complete", "handover", "downstream"]),
    ("open_decisions", ["open decision", "undecided", "decided", "master system", "sequenc", "parallel"]),
    ("roles", ["who ", "role", "responsib", "requester", "support lead", "analyst", "master data lead", "supply chain"]),
    ("onboarding", ["onboard", "setup", "set up", "initiat", "start", "supplier form", "request"]),
]


def classify_topic(question: str) -> str:
    q = question.lower()
    for topic, keywords in _TOPICS:
        if any(k in q for k in keywords):
            return topic
    return "general"
