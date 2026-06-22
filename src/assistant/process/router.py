"""Route a question to the most relevant process record (deterministic keyword match)."""

from __future__ import annotations

import re

from .models import ProcessRecord

_MIN_OVERLAP = 2  # require a couple of shared terms to avoid spurious matches


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def match_process(query: str, records: list[ProcessRecord]) -> ProcessRecord | None:
    qt = _tokens(query)
    if not qt:
        return None
    best: ProcessRecord | None = None
    best_score = 0
    for r in records:
        haystack = " ".join([r.name, r.domain, r.process, " ".join(r.capabilities), " ".join(r.roles), " ".join(r.systems)])
        score = len(qt & _tokens(haystack))
        if score > best_score:
            best, best_score = r, score
    return best if best_score >= _MIN_OVERLAP else None
