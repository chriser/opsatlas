"""Route a question to the most relevant process record (deterministic keyword match)."""

from __future__ import annotations

import re

from .models import ProcessRecord

_MIN_OVERLAP = 2  # require a couple of shared terms to avoid spurious matches


def _normalise_token(token: str) -> str:
    """Keep the router deterministic while tolerating simple singular/plural forms."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def _tokens(text: str) -> set[str]:
    return {_normalise_token(token) for token in re.findall(r"[a-z0-9]+", text.lower())}


def _haystack(record: ProcessRecord) -> str:
    rule_text = " ".join(
        " ".join([rule.topic, rule.role, rule.rule, rule.confidence])
        for rule in record.rules
    )
    return " ".join([
        record.name,
        record.domain,
        record.process,
        " ".join(record.capabilities),
        " ".join(record.roles),
        " ".join(record.systems),
        " ".join(record.controls),
        " ".join(record.dependencies),
        " ".join(record.business_rules),
        rule_text,
    ])


def match_process(query: str, records: list[ProcessRecord]) -> ProcessRecord | None:
    qt = _tokens(query)
    if not qt:
        return None
    best: ProcessRecord | None = None
    best_score = 0
    for r in records:
        score = len(qt & _tokens(_haystack(r)))
        if score > best_score:
            best, best_score = r, score
    return best if best_score >= _MIN_OVERLAP else None
