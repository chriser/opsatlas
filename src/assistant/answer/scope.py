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

# A year the question is about: with a cue ("in 2027", "from 1 January 2027", "2027 onwards"), not any 20xx number
# ("orders of 2050 units" is about today; red team, REF F10).
MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
YEAR = re.compile(r"\b(?:in|from|for|during|by|until|after|before|since|starting|effective|year)\s+"
                  r"(?:(?:\d{1,2}(?:st|nd|rd|th)?\s+)?" + MONTH + r"\s+)?(20\d\d)\b|\b(20\d\d)\s+onwards?\b", re.I)
NEXT_YEAR = re.compile(r"\bnext year\b", re.I)
DATE = re.compile(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})")
# Words a site name shares with others, which alone do not name a site.
GENERIC = {"centre", "center", "office", "head", "site", "distribution", "store", "branch", "the", "and", "pilot"}
UNREADABLE = object()  # a date that is there but cannot be read: the source is not in force (it fails closed)


def asked_date(question: str, today: date) -> date:
    """The date the question is about: a later year it names (from its first day), next year, or today."""
    years = [int(a or b) for a, b in YEAR.findall(question) if int(a or b) > today.year]
    if years:
        return date(min(years), 1, 1)
    if NEXT_YEAR.search(question):
        return date(today.year + 1, 1, 1)
    return today


def _sites(records) -> list[str]:
    """The sites the space knows, named by any of its sources (approved or not; red team and random scenarios, REF
    F10), one per spelling regardless of case; anything that is not text is not a site name."""
    seen: dict[str, str] = {}
    for record in records:
        for site in record.applies_to or []:
            if isinstance(site, str) and site.strip():
                seen.setdefault(site.strip().casefold(), site.strip())
    return sorted(seen.values())


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.casefold()))


def asked_site(question: str, sites: list[str]) -> str | None:
    """The one site the question names, by its full name as whole words or by a word only that site has (Leeds,
    Bristol); None when it names none or more than one. "bathroom" does not name Bath; a word two sites share names
    neither; a full name inside a longer one named too ("Leeds" in "Leeds Head Office") gives way to the longer."""
    text = question.casefold()
    by_name = [s for s in sites if re.search(r"\b" + re.escape(s.casefold()) + r"\b", text)]
    by_name = [s for s in by_name if not any(s != o and s.casefold() in o.casefold() for o in by_name)]
    owners: dict[str, set[str]] = {}
    for site in sites:
        for word in _words(site):
            if len(word) >= 4 and word not in GENERIC:
                owners.setdefault(word, set()).add(site)
    by_word = {next(iter(owners[w])) for w in _words(question) if w in owners and len(owners[w]) == 1}
    named = set(by_name) | by_word
    return named.pop() if len(named) == 1 else None


def _iso(value):
    """A date from metadata: an ISO date, written loosely or not ("2027-1-1", " 2027-01-01"), or a date object; None
    when absent; UNREADABLE when present but unreadable, which keeps the source out (red team, REF F10)."""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    match = DATE.match(str(value))
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return UNREADABLE
    return UNREADABLE


class ScopeFilter:
    """Which approved sources may answer one question (REF H3)."""

    def __init__(self, records, question: str, today: date) -> None:
        approved = [r for r in records if r.approval_status == "approved"]
        self.when = asked_date(question, today)
        self.sites = _sites(records)
        self.site = asked_site(question, self.sites)
        in_force = {r.id for r in approved if self._dated(r)}
        # A source that names itself is replaced too: the promise reads literally, and the source cannot be trusted.
        self.superseded = {old for r in approved if r.id in in_force for old in (r.supersedes or [])}

    def _dated(self, record) -> bool:
        start, end = _iso(record.effective_from), _iso(record.effective_to)
        if start is UNREADABLE or end is UNREADABLE:
            return False
        return (start is None or start <= self.when) and (end is None or self.when <= end)

    def _applies(self, record) -> bool:
        names = {s.strip().casefold() for s in (record.applies_to or []) if isinstance(s, str) and s.strip()}
        return not names or self.site is None or self.site.casefold() in names

    def allow(self, record) -> bool:
        return self._dated(record) and record.id not in self.superseded and self._applies(record)

    def excludes_any(self, records) -> bool:
        """Whether scope keeps any of these approved sources out of this answer: then the facts map and the process
        registry, built from every approved source, are not used for it (REF H3b)."""
        return any(not self.allow(r) for r in records if r.approval_status == "approved")

    def note(self, record) -> str:
        """What a passage says about its own scope when the question named no site (so the answer can label it)."""
        names = [s for s in (record.applies_to or []) if isinstance(s, str) and s.strip()]
        return f"(Applies to: {', '.join(names)}.) " if names and self.site is None else ""


PART_BREAK = re.compile(r"\?\s+(?=\S)|[;,]?\s+and\s+(?=(?:what|how|why|which|who|whom|when|where|whether|does|do|is|are|can)\b)",
                        re.I)


def parts(question: str) -> list[str]:
    """The separate things a question asks (REF H4): split at a question mark followed by more, or at "and" before
    a new question word. One part when it asks one thing."""
    pieces = [p.strip(" ,;?") for p in PART_BREAK.split(question.strip())]
    pieces = [p for p in pieces if len(p.split()) >= 3]
    return pieces if len(pieces) > 1 else [question.strip()]
