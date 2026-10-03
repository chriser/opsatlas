"""Scope decides which approved source may answer (REF H3, H3b), and a multi-part question gets evidence for each part
(REF H4). Both are candidates under test, off unless their settings say otherwise (KP_SCOPE_EVIDENCE, KP_PLAN_PARTS).

Scope. A source can say when it is in force (effective_from, effective_to), which sources it replaces (supersedes) and
which sites it applies to (applies_to). Scope judges by today and never guesses the date a question is about (the
Human's decision of 3 October 2026, after the stop rule: inferring it from free text had faults in two review rounds
running). A source expired or replaced today is left out; so is another site's guidance when the question names one
site the space knows. A source approved for a later date is kept, and its passages say from when it applies, so a
question about next year can be answered and a question about now is not misled; a source in force today with an end
date says until when. With no site named, each site-specific passage says its site. The facts map and the process
registry cannot carry those labels, so they are closed to any answer for which scope leaves a source out or labels one.

Parts. The core retrieved the top five passages for the whole question; a question asking two things could spend all
five on one. With planning on, a question that asks several things is split into its parts, each part is retrieved
on its own, and a part with nothing approved behind it is said to be missing.
"""
from __future__ import annotations

import re
from datetime import date

DATE = re.compile(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})")
# Words a site name shares with others, which alone do not name a site.
GENERIC = {"centre", "center", "office", "head", "site", "distribution", "store", "branch", "the", "and", "pilot"}
UNREADABLE = object()  # a date that is there but cannot be read: the source is left out (it fails closed)


def _long(day: date) -> str:
    return f"{day.day} {day:%B %Y}"


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
    """Which approved sources may answer one question, judged by today (REF H3, H3b)."""

    def __init__(self, records, question: str, today: date) -> None:
        approved = [r for r in records if r.approval_status == "approved"]
        self.today = today
        self.sites = _sites(records)
        self.site = asked_site(question, self.sites)
        in_force = {r.id for r in approved if self._period(r) == "now"}
        # A source that names itself is replaced too: the promise reads literally, and the source cannot be trusted.
        self.superseded = {old for r in approved if r.id in in_force for old in (r.supersedes or [])}

    def _period(self, record) -> str:
        """'now' (in force today), 'later' (approved for a later date), or 'out' (expired, or a date cannot be read)."""
        start, end = _iso(record.effective_from), _iso(record.effective_to)
        if start is UNREADABLE or end is UNREADABLE or (end is not None and end < self.today):
            return "out"
        if start is not None and start > self.today:
            return "later" if end is None or start <= end else "out"
        return "now"

    def _applies(self, record) -> bool:
        names = {s.strip().casefold() for s in (record.applies_to or []) if isinstance(s, str) and s.strip()}
        return not names or self.site is None or self.site.casefold() in names

    def allow(self, record) -> bool:
        return self._period(record) != "out" and record.id not in self.superseded and self._applies(record)

    def note(self, record) -> str:
        """What a passage says about its own scope: from when a later source applies, until when a current one does,
        and which site it applies to when the question named none."""
        parts = []
        start, end = _iso(record.effective_from), _iso(record.effective_to)
        if self._period(record) == "later":
            parts.append(f"In force from {_long(start)}")
        elif isinstance(end, date):
            parts.append(f"In force until {_long(end)}")
        names = [s for s in (record.applies_to or []) if isinstance(s, str) and s.strip()]
        if names and self.site is None:
            parts.append(f"Applies to: {', '.join(names)}")
        return f"({'; '.join(parts)}.) " if parts else ""

    def closes_facts(self, records) -> bool:
        """Whether the facts map and the process registry, built from every approved source and unable to carry
        labels, must stay out of this answer: when scope leaves any approved source out or labels one (REF H3b)."""
        return any(not self.allow(r) or self.note(r) for r in records if r.approval_status == "approved")


PART_BREAK = re.compile(r"\?\s+(?=\S)|[;,]?\s+and\s+(?=(?:what|how|why|which|who|whom|when|where|whether|does|do|is|are|can)\b)",
                        re.I)


def parts(question: str) -> list[str]:
    """The separate things a question asks (REF H4): split at a question mark followed by more, or at "and" before
    a new question word. One part when it asks one thing."""
    pieces = [p.strip(" ,;?") for p in PART_BREAK.split(question.strip())]
    pieces = [p for p in pieces if len(p.split()) >= 3]
    return pieces if len(pieces) > 1 else [question.strip()]
