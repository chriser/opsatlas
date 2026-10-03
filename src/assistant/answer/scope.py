"""Scope decides which approved source may answer (REF H3), and a multi-part question gets evidence for each part
(REF H4). Both are candidates under test, off unless their settings say otherwise (KP_SCOPE_EVIDENCE, KP_PLAN_PARTS).

Scope. A source can say when it is in force (effective_from, effective_to), which sources it replaces (supersedes) and
which sites it applies to (applies_to). Retrieval used only approval and the space, so an approved policy not yet in
force, a replaced one, or another site's guidance could answer. With scope on, a source answers only when it is in force
on the date the question is about (today, unless the question names a later year or "next year"), is not replaced by
an approved source in force then, and, when the question names a site, applies to that site or to none. When the
question names no site and the sources differ by site, each passage says which site it applies to, so the answer can
label both or ask.

Parts. The core retrieved the top five passages for the whole question; a question asking two things could spend all
five on one. With planning on, a question that asks several things is split into its parts, each part is retrieved
on its own, and a part with nothing approved behind it is said to be missing.
"""
from __future__ import annotations

import re
from datetime import date

YEAR = re.compile(r"\b(20\d\d)\b")
NEXT_YEAR = re.compile(r"\bnext year\b", re.I)
# Words a site name shares with others, which alone do not name a site.
GENERIC = {"centre", "center", "office", "head", "site", "distribution", "store", "branch", "the", "and", "pilot"}


def asked_date(question: str, today: date) -> date:
    """The date the question is about: a later year it names (from its first day), next year, or today."""
    years = [int(y) for y in YEAR.findall(question) if int(y) > today.year]
    if years:
        return date(min(years), 1, 1)
    if NEXT_YEAR.search(question):
        return date(today.year + 1, 1, 1)
    return today


def _names(site: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", site.lower()) if len(w) >= 4 and w not in GENERIC}


def asked_site(question: str, sites: list[str]) -> str | None:
    """The site the question names, by its full name or a word only it has (Leeds, Bristol)."""
    words = set(re.findall(r"[a-z]+", question.lower()))
    named = [s for s in sites if s.lower() in question.lower() or _names(s) & words]
    return named[0] if len(named) == 1 else None


def _iso(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return None


class ScopeFilter:
    """Which approved sources may answer one question (REF H3)."""

    def __init__(self, records, question: str, today: date) -> None:
        approved = [r for r in records if r.approval_status == "approved"]
        self.when = asked_date(question, today)
        # The sites the space knows: named by any of its sources, approved or not. Learning them only from approved ones
        # let another site's guidance answer for a site that had no approved source yet (found by the random scenarios).
        self.sites = sorted({s for r in records for s in (r.applies_to or [])})
        self.site = asked_site(question, self.sites)
        in_force = {r.id for r in approved if self._dated(r)}
        self.superseded = {old for r in approved if r.id in in_force for old in (r.supersedes or []) if old != r.id}

    def _dated(self, record) -> bool:
        start, end = _iso(record.effective_from), _iso(record.effective_to)
        return (start is None or start <= self.when) and (end is None or self.when <= end)

    def allow(self, record) -> bool:
        if not self._dated(record) or record.id in self.superseded:
            return False
        return not record.applies_to or self.site is None or self.site in record.applies_to

    def note(self, record) -> str:
        """What a passage says about its own scope when the question named no site (so the answer can label it)."""
        return f"(Applies to: {', '.join(record.applies_to)}.) " if record.applies_to and self.site is None else ""


PART_BREAK = re.compile(r"\?\s+(?=\S)|[;,]?\s+and\s+(?=(?:what|how|why|which|who|whom|when|where|whether|does|do|is|are|can)\b)",
                        re.I)


def parts(question: str) -> list[str]:
    """The separate things a question asks (REF H4): split at a question mark followed by more, or at "and" before
    a new question word. One part when it asks one thing."""
    pieces = [p.strip(" ,;?") for p in PART_BREAK.split(question.strip())]
    pieces = [p for p in pieces if len(p.split()) >= 3]
    return pieces if len(pieces) > 1 else [question.strip()]
