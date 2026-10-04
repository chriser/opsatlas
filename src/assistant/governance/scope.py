"""Scope and dates of a statement, and when two statements cannot conflict (GOV S8).

Two statements conflict only if they cannot both hold "for the same subject, scope and time" (the governance pair
benchmark's definition). Every error the fast local judges made on the benchmark was a scope or date case, so this
module settles the plain ones without a model. The rules were fixed on 26 September 2026 before being measured:

* dates: statements whose effective periods do not overlap ("From 1 April 2027 ..." against "Until 31 March 2027 ...")
  are set aside, not judged;
* phase: statements in phases that exclude each other are set aside: day one against the end state, and the proof of
  concept against a real deployment ("The PoC uses anonymised data" against "A real deployment uses the organisation's
  own data", which the Human asked to keep apart in evaluation 2);
* applies to (sites, networks, groups): never set aside. A general rule that says "always" can genuinely conflict
  with a site-specific one, so a model or the Human decides.

Two revisions followed the first measurements, both recorded in docs/data-and-governance/statement-level-governance.md:

* telling the judge what each statement applies to was dropped: on the governance pair benchmark it fixed no case and
  turned one (scoped-09, pilot sites) into a false conflict for qwen2.5:14b-instruct. Scope is shown to people instead;
* a statement's words give it a phase or dates only when it opens with them ("For day one, ...", "In the end state,
  ...", "From 1 April 2027, ...", "The proof of concept uses ..."). On the 21 learning packs the first rule, which took
  any mention, set aside six pairs of table rows that discuss the choice between phases ("Decides whether the redesign
  is a day-one change or a later-phase improvement"), one of them a duplicate Claude Opus 5.5 had found.

Scope comes from the statement's own words (kept on the statement as ``scope``) and, where the workspace keeps it,
from its source's metadata (``effective_from``, ``effective_to``, ``phases``, ``applies_to`` on the source record); the
metadata wins where both say something. A source may also name the sources it ``supersedes``: those are no longer in
force, so they are not governed while the source replacing them is (the rule the sales workspace already applied to
a record's earlier versions).
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date

PHASES = {
    'day_one': re.compile(r"\bday[- ]one\b|\binitial (?:rollout|release|go-live)\b|\bfirst phase\b|\bat cut-?over\b", re.I),
    'end_state': re.compile(r"\bend[- ]state\b|\btarget (?:state|model|architecture)\b|\blonger[- ]term\b|\blater phase\b|"
                            r"\bfuture phase\b", re.I),
    'proof_of_concept': re.compile(r"\bproof[- ]of[- ]concept\b|\bPoC\b|\bthe demo\b|\bdemonstration\b"),
    'real_deployment': re.compile(r"\breal (?:deployment|use|organisation's)\b|\bproduction deployment\b|\bin production\b|"
                                  r"\blive deployment\b|\bproduction use\b", re.I),
}
EXCLUSIVE = ({'day_one', 'end_state'}, {'proof_of_concept', 'real_deployment'})
PHASE_WORDS = {'day_one': 'day one', 'end_state': 'the end state', 'proof_of_concept': 'the proof of concept',
               'real_deployment': 'a real deployment'}
MONTHS = {m: n for n, m in enumerate(('january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september',
                                      'october', 'november', 'december'), 1)}
MONTH = r"(?:january|february|march|april|may|june|july|august|september|october|november|december)"
DATE = (rf"(?:\d{{1,2}}(?:st|nd|rd|th)? {MONTH} \d{{4}}|{MONTH} \d{{1,2}},? \d{{4}}|{MONTH} \d{{4}}|\d{{4}}-\d{{2}}-\d{{2}}|"
        rf"q[1-4] \d{{4}}|\d{{4}})")
FROM = re.compile(rf"\b(?:effective from|from|starting|effective|as of|after|beginning)\s+(?:the\s+)?({DATE})", re.I)
UNTIL = re.compile(rf"\b(?:until|till|up to|before|through|to the end of|ending)\s+(?:the\s+)?({DATE})", re.I)
DURING = re.compile(rf"\b(?:in|during|throughout)\s+({MONTH} \d{{4}}|q[1-4] \d{{4}}|\d{{4}})\b", re.I)
APPLIES = re.compile(r"\b(?:for|at|in)\s+(?:the\s+)?((?:[a-z-]+\s+){0,3}(?:sites?|stores?|networks?|regions?|countries|"
                     r"markets?|teams?|suppliers?|customers?))\s+only\b|\bonly\s+(?:for|at|in)\s+(?:the\s+)?((?:[a-z-]+\s+){0,3}"
                     r"(?:sites?|stores?|networks?|regions?|countries|markets?|teams?|suppliers?|customers?))\b|"
                     r"\bfor\s+((?:[a-z-]+\s+){0,3}(?:sites?|stores?|networks?))\b", re.I)


@dataclass
class Scope:
    phases: set = field(default_factory=set)
    start: date | None = None
    end: date | None = None
    applies_to: list = field(default_factory=list)

    def empty(self) -> bool:
        return not (self.phases or self.start or self.end or self.applies_to)

    def as_dict(self) -> dict:
        """The fields a statement keeps, in the same names a source uses."""
        return {'phases': sorted(self.phases), 'effective_from': self.start and self.start.isoformat(),
                'effective_to': self.end and self.end.isoformat(), 'applies_to': list(self.applies_to)}

    def describe(self) -> str:
        """What the statement covers, in words: shown on the Governance page and said by Tibi."""
        day = lambda d: f'{d.day} {d.strftime("%B")} {d.year}'  # noqa: E731
        parts = [PHASE_WORDS[p] for p in sorted(self.phases)]
        if self.start and self.end:
            parts.append(f'{day(self.start)} to {day(self.end)}')
        elif self.start:
            parts.append(f'{day(self.start)} onwards')
        elif self.end:
            parts.append(f'up to {day(self.end)}')
        parts += self.applies_to
        return '; '.join(parts)


def _date(text: str, end: bool = False) -> date | None:
    """A date phrase as a day; a month, quarter or year stands for its first day, or its last with ``end``."""
    value = text.lower().replace(',', '').strip()

    def month_bound(year, month):
        return date(year, month, calendar.monthrange(year, month)[1] if end else 1)
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            return date.fromisoformat(value)
        if match := re.fullmatch(rf'(\d{{1,2}})(?:st|nd|rd|th)? ({MONTH}) (\d{{4}})', value):
            return date(int(match.group(3)), MONTHS[match.group(2)], int(match.group(1)))
        if match := re.fullmatch(rf'({MONTH}) (\d{{1,2}}) (\d{{4}})', value):
            return date(int(match.group(3)), MONTHS[match.group(1)], int(match.group(2)))
        if match := re.fullmatch(rf'({MONTH}) (\d{{4}})', value):
            return month_bound(int(match.group(2)), MONTHS[match.group(1)])
        if match := re.fullmatch(r'q([1-4]) (\d{4})', value):
            quarter = int(match.group(1))
            return month_bound(int(match.group(2)), 3 * quarter if end else 3 * quarter - 2)
        if re.fullmatch(r'\d{4}', value) and 1990 <= int(value) <= 2100:
            return date(int(value), 12, 31) if end else date(int(value), 1, 1)
    except ValueError:
        return None
    return None


LEAD = re.compile(r"(?:(?:for|on|at|in|during|within|under|from|by)\s+)?(?:(?:the|a|an|this)\s+)?", re.I)
# A short label before the statement proper: a workspace's status ("Currently: ", "Planned, not delivered: ").
LABEL = re.compile(r"[A-Z][^:|.]{0,40}:\s+")


def _opens_with(pattern: re.Pattern, text: str) -> bool:
    """Whether the statement opens with the phrase, alone or after a preposition and an article ("In the end state")."""
    return bool(pattern.match(text) or pattern.match(text, LEAD.match(text).end()))


def extract(text: str) -> Scope:
    """The scope a statement opens with. A phase or date mentioned later ("decides whether it is a day-one change or
    a later-phase improvement") is discussed, not the statement's scope."""
    full = text.strip()
    label = LABEL.match(full)
    openings = [full, full[label.end():]] if label else [full]  # "Day one: ..." opens with its phase, too
    scope = Scope({name for name, pattern in PHASES.items() if any(_opens_with(pattern, body) for body in openings)})
    for body in openings:
        if (match := FROM.match(body)) and (start := _date(match.group(1))):
            scope.start = start
            if (match := UNTIL.search(body)) and (end := _date(match.group(1), end=True)):
                scope.end = end  # "From 1 April 2027 ... until 31 March 2028"
        elif (match := UNTIL.match(body)) and (end := _date(match.group(1), end=True)):
            scope.end = end
        elif (match := DURING.match(body)):
            scope.start, scope.end = _date(match.group(1)), _date(match.group(1), end=True)
        if scope.start or scope.end:
            break
    scope.applies_to = [' '.join(g.split()) for m in APPLIES.finditer(text) for g in m.groups() if g][:2]
    return scope


def from_dict(fields: dict | None) -> Scope:
    """A scope kept as fields (a statement's, or a source's metadata)."""
    return merge(Scope(), fields)


def of_source(source) -> dict:
    """A register source's scope fields, or {} when it has none."""
    fields = {k: getattr(source, k, None) for k in ('phases', 'effective_from', 'effective_to', 'applies_to')}
    return {k: v for k, v in fields.items() if v}


def merge(text_scope: Scope, metadata: dict | None) -> Scope:
    """Scope from the statement's words, overridden where its source's metadata says something. Unknown phase names
    are ignored."""
    if not metadata:
        return text_scope
    phases = {p for p in metadata.get('phases') or [] if p in PHASES} or text_scope.phases
    start = date.fromisoformat(metadata['effective_from']) if metadata.get('effective_from') else text_scope.start
    end = date.fromisoformat(metadata['effective_to']) if metadata.get('effective_to') else text_scope.end
    return Scope(phases, start, end, list(metadata.get('applies_to') or []) or text_scope.applies_to)


def separated(a: Scope, b: Scope) -> str | None:
    """Why two statements cannot conflict or duplicate each other, or None if their scopes may overlap."""
    if (a.start or a.end) and (b.start or b.end):
        a_start, a_end = a.start or date.min, a.end or date.max
        b_start, b_end = b.start or date.min, b.end or date.max
        if a_end < b_start or b_end < a_start:
            return 'dates'
    for group in EXCLUSIVE:
        pa, pb = a.phases & group, b.phases & group
        if len(pa) == 1 and len(pb) == 1 and pa != pb:
            return 'phase'
    return None
