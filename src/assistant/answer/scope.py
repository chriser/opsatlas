"""Scope decides which approved source may answer (REF H3, H3b), and a multi-part question gets evidence for each part
(REF H4). Both are candidates under test, off unless their settings say otherwise (KP_SCOPE_EVIDENCE, KP_PLAN_PARTS).

Scope. A source can say when it is in force (effective_from, effective_to), which sources it replaces (supersedes) and
which sites it applies to (applies_to). Scope judges by today and reads nothing from the question: it guesses neither
the date nor the site a question is about (the Human's decisions of 3 October 2026, each after the stop rule found
faults in free-text guessing in consecutive review rounds). A source expired, replaced today, or carrying a date that
cannot be read is left out. A source approved for a later date is kept, and its passages say from when it applies, so
a question about next year can be answered and a question about now is not misled; a source in force today with an
end date says until when; a site-specific source says its sites. The facts map and the process registry cannot carry
those labels, so they are closed to any answer for which scope leaves a source out or labels one.

Dates are read one way, by ``read_date``, which the details editor uses too: whatever the editor accepts, scope reads.

Parts. The core retrieved the top five passages for the whole question; a question asking two things could spend all
five on one. With planning on, a question that asks several things is split into its parts, each part is retrieved
on its own, and a part with nothing approved behind it is said to be missing.
"""
from __future__ import annotations

import re
from datetime import date, datetime

UNREADABLE = object()  # a date that is there but cannot be read: the source is left out (it fails closed)


def read_date(value):
    """The one reader of a scope date (REF H3b), shared with the details editor: an ISO 8601 date as Python reads it
    ("2026-12-31", "20261231", "2026-W53-4"), or a date object; None when absent; UNREADABLE otherwise ("2026-12-311",
    "2027-1-1", " 2027-01-01", a number). Nothing is read from part of a value."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return UNREADABLE
    try:
        return date.fromisoformat(value)
    except ValueError:
        return UNREADABLE


def _long(day: date) -> str:
    return f"{day.day} {day:%B %Y}"


class ScopeFilter:
    """Which approved sources may answer, and what their passages say about their scope, judged by today on one
    reading of the register (REF H3, H3b). The question plays no part."""

    def __init__(self, records, today: date) -> None:
        approved = [r for r in records if r.approval_status == "approved"]
        self.today = today
        in_force = {r.id for r in approved if self._period(r) == "now"}
        # A source that names itself is replaced too: the promise reads literally, and the source cannot be trusted.
        self.superseded = {old for r in approved if r.id in in_force for old in (r.supersedes or [])}

    def _period(self, record) -> str:
        """'now' (in force today), 'later' (approved for a later date), or 'out' (expired, or a date cannot be read)."""
        start, end = read_date(record.effective_from), read_date(record.effective_to)
        if start is UNREADABLE or end is UNREADABLE or (end is not None and end < self.today):
            return "out"
        if start is not None and start > self.today:
            return "later" if end is None or start <= end else "out"
        return "now"

    def allow(self, record) -> bool:
        return self._period(record) != "out" and record.id not in self.superseded

    def note(self, record) -> str:
        """What a passage says about its own scope: from when a later source applies, or until when a current one
        does, and which sites it applies to."""
        parts = []
        start, end = read_date(record.effective_from), read_date(record.effective_to)
        if self._period(record) == "later":
            parts.append(f"In force from {_long(start)}")
        elif isinstance(end, date):
            parts.append(f"In force until {_long(end)}")
        names = [s.strip() for s in (record.applies_to or []) if isinstance(s, str) and s.strip()]
        if names:
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
