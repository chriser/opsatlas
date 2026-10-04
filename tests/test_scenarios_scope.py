"""Random scenarios for scope (REF H3, H3b): which approved source may answer, judged by today, and what its passages
say about their scope.

Promises (the Human's decisions of 3 October 2026, each after the stop rule), checked by an oracle written from the
promise text, not from the filter:
- left out: a source expired today, replaced today by an approved source in force today (itself included), or with a
  date that is there but cannot be read;
- one date reader: a date is read as the details editor reads it (Python's ISO 8601 date reader, or a date object), and
  nothing is read from part of a value;
- labelled, exactly: a source approved for a later date says "In force from <start>"; one in force today with an end
  date says "In force until <end>"; a site-specific source says "Applies to: <its sites>"; nothing else;
- exactly these: every other approved source is allowed (scope never hides a source it should not); no site is left
  out for being another site's;
- documents only when anything is left out or labelled: the facts map and the process registry are closed;
- the same judgement twice and in any order of the register, and no crash, whatever the metadata.
(Scope does not see the question, so no date or site can be guessed from it; tests/test_scenarios_scope_answers.py
checks that through the answer service.)

Scenario kinds: missing and unreadable dates (trailing digits, loosely written, padded, numbers, impossible days),
basic and week-form ISO dates, date and datetime objects; dates on the boundary (today itself, 31 December, 1 January);
a start after its end; supersede chains, cycles and self-reference; site names with punctuation, months, common
words, other cases, padding and non-text entries; pending sources; the register read in another order. The red teams'
findings of 3 October 2026 (REF F10, H3b rounds 1 and 2) are kinds here.
"""
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from scenarios import explore

from assistant.answer.scope import ScopeFilter

SITES = ["Leeds Distribution Centre", "Leeds Head Office", "Bristol Returns Centre", "DC (A)", "March", "Reading", "Bath",
         "leeds distribution centre", " York store "]
BOUNDARIES = [date(2025, 12, 31), date(2026, 1, 1), date(2026, 12, 31), date(2027, 1, 1), date(2026, 10, 3)]
UNREADABLE_FORMS = ["31/12/2026", "2026-13-01", "soon", "2026-02-30", "2026-12-311", "2026-01-015", "2027-1-1",
                    " 2027-01-01", "2027-01-01 ", 20261231, 2027.0]


def _read(value):
    """The oracle's reading, as the promise states it: Python's ISO date reader on text, or a date (or a datetime's
    date); None when absent; False when there but unreadable."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value)
    except ValueError:
        return False


def _a_date(run, today):
    roll = run.rng.random()
    if roll < 0.15:
        return None
    if roll < 0.27:
        return run.rng.choice(UNREADABLE_FORMS)  # unreadable: keeps the source out
    when = today + timedelta(days=run.rng.choice([-1, 0, 1]) if roll < 0.5 else run.rng.randint(-900, 900))
    form = run.rng.random()
    if form < 0.12:
        return when.strftime("%Y%m%d")  # basic ISO, which the details editor accepts
    if form < 0.18:
        year, week, day = when.isocalendar()
        return f"{year}-W{week:02d}-{day}"  # the week form, which it accepts too
    if form < 0.28:
        return when  # a date object, as a loader that parses dates gives
    if form < 0.33:
        return datetime(when.year, when.month, when.day, 9, 30)
    return when.isoformat()


def _long(day: date) -> str:
    return f"{day.day} {day:%B %Y}"


def one_run(run):
    today = run.rng.choice(BOUNDARIES) if run.rng.random() < 0.4 else date(2025, 1, 1) + timedelta(days=run.rng.randint(0, 1095))
    ids = [f"s{i}" for i in range(run.rng.randint(1, 8))]
    sources = []
    for sid in ids:
        sites = run.rng.sample(SITES, run.rng.choice([0, 0, 1, 1, 2]))
        sites = [s.upper() if run.rng.random() < 0.15 else s for s in sites]  # another case
        if run.rng.random() < 0.05:
            sites.append(run.rng.choice([None, 42, "", "   "]))  # not a site name
        sources.append(SimpleNamespace(
            id=sid, approval_status="approved" if run.rng.random() < 0.85 else "pending",
            effective_from=_a_date(run, today), effective_to=_a_date(run, today), applies_to=sites,
            supersedes=run.rng.sample(ids, min(len(ids), run.rng.choice([0, 0, 0, 1, 2])))))
    run.step("sources", f"{len(sources)} on {today}")

    scope = ScopeFilter(sources, today)
    again = ScopeFilter(sources, today)
    shuffled = ScopeFilter(run.rng.sample(sources, len(sources)), today)  # the register read in another order
    approved = [s for s in sources if s.approval_status == "approved"]

    def period(s):
        start, end = _read(s.effective_from), _read(s.effective_to)
        if start is False or end is False or (end is not None and end < today):
            return "out"
        if start is not None and start > today:
            return "later" if end is None or start <= end else "out"
        return "now"

    def label(s):
        parts = []
        start, end = _read(s.effective_from), _read(s.effective_to)
        if period(s) == "later":
            parts.append(f"In force from {_long(start)}")
        elif period(s) == "now" and end is not None:
            parts.append(f"In force until {_long(end)}")
        names = [x.strip() for x in s.applies_to if isinstance(x, str) and x.strip()]
        if names:
            parts.append(f"Applies to: {', '.join(names)}")
        return f"({'; '.join(parts)}.) " if parts else ""

    replaced = {old for s in approved if period(s) == "now" for old in s.supersedes}
    labelled_any = False
    for s in approved:
        should = period(s) != "out" and s.id not in replaced
        allowed, note = scope.allow(s), scope.note(s)
        run.promise("same judgement twice", (allowed, note) == (again.allow(s), again.note(s)), s.id)
        run.promise("same judgement in any order", (allowed, note) == (shuffled.allow(s), shuffled.note(s)), s.id)
        run.promise("exactly these", allowed == should,
                    f"{s.id}: allowed {allowed}, should {should} ({period(s)}; from {s.effective_from!r} to {s.effective_to!r})")
        if allowed:
            run.promise("labelled, exactly", note == label(s), f"{s.id}: {note!r}, should be {label(s)!r}")
        labelled_any |= (not should) or bool(label(s))
    run.promise("documents only when anything is left out or labelled", scope.closes_facts(sources) == labelled_any,
                f"closes_facts {scope.closes_facts(sources)}, should {labelled_any}")


def test_scope_keeps_its_promises_over_random_scenarios():
    assert explore("scope", one_run) >= 1
