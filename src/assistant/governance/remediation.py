"""Auto-remediation suggestions for a near-duplicate document pair.

Deterministic (no LLM): recommends which document should keep the overlapping
content and proposes a trimmed version of the other. The heuristic favours the
document with more *unique* (non-shared) material as the better single home —
it is the more complete/authoritative source — and suggests the thinner one drop
the shared passages. The result is advisory: the operator reviews and edits before
saving.
"""

from __future__ import annotations

import re

_MIN_LINE = 25  # ignore short lines so trivial matches don't count as overlap


def _norm(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().lower())


def _shared_lines(a_text: str, b_text: str) -> set[str]:
    b_set = {n for n in (_norm(line) for line in b_text.split("\n")) if len(n) >= _MIN_LINE}
    return {n for n in (_norm(line) for line in a_text.split("\n")) if len(n) >= _MIN_LINE and n in b_set}


def _unique_chars(text: str, shared: set[str]) -> int:
    return sum(len(line) for line in text.split("\n") if _norm(line) not in shared)


def _strip_shared(text: str, shared: set[str]) -> str:
    kept = [line for line in text.split("\n") if _norm(line) not in shared]
    collapsed = re.sub(r"\n{3,}", "\n\n", "\n".join(kept))  # tidy gaps left by removed lines
    return collapsed.strip() + "\n"


def suggest_remediation(a: dict, b: dict) -> dict:
    """a, b: dicts with id/title/text. Returns a keep/trim recommendation."""
    shared = _shared_lines(a["text"], b["text"])
    ua, ub = _unique_chars(a["text"], shared), _unique_chars(b["text"], shared)
    keep, trim, keep_u, trim_u = (a, b, ua, ub) if ua >= ub else (b, a, ub, ua)
    return {
        "shared_lines": len(shared),
        "keep_id": keep["id"],
        "keep_title": keep["title"],
        "trim_id": trim["id"],
        "trim_title": trim["title"],
        "reason": (
            f"'{keep['title']}' has more unique content ({keep_u:,} vs {trim_u:,} characters not shared), "
            f"so it is the better single home for the overlap. '{trim['title']}' can drop the "
            f"{len(shared)} shared line(s) below."
        ),
        "trim_suggested_text": _strip_shared(trim["text"], shared),
    }
