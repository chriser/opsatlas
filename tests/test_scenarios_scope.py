"""Random scenarios for scope (REF H3, H3b): which approved source may answer a question.

Promises, checked by an oracle written from the promise text, not from the filter:
- in force: an allowed source is in force on the date the question is about (today, or the first day of a later year
  it names, or of next year);
- not replaced: no approved source in force then names an allowed source in its supersedes;
- right site: when the question names exactly one site the space knows (any of its sources names it), an allowed
  source applies to that site or to no site;
- exactly these: every approved source meeting all three is allowed (scope never hides a source it should not);
- the same answer twice, and no crash, whatever the metadata (unreadable dates, supersede cycles, self-reference).

Scenario kinds: unreadable or missing dates; dates on the boundary (the day itself, 31 December, 1 January); supersede
chains, cycles and self-reference; sites by full name, by their own word, both named, none named; past, future and
"next year" questions; pending sources among approved ones.
"""
from datetime import date, timedelta
from types import SimpleNamespace

from scenarios import explore

from assistant.answer.scope import ScopeFilter

SITES = ["Leeds distribution centre", "Bristol head office", "York store"]
OWN_WORD = {"Leeds distribution centre": "Leeds", "Bristol head office": "Bristol", "York store": "York"}
BOUNDARIES = [date(2025, 12, 31), date(2026, 1, 1), date(2026, 12, 31), date(2027, 1, 1), date(2026, 10, 3)]


def _parse(value):
    try:
        return date.fromisoformat(value[:10]) if value else None
    except (TypeError, ValueError):
        return None


def _a_date(run, today):
    roll = run.rng.random()
    if roll < 0.2:
        return None
    if roll < 0.3:
        return run.rng.choice(["31/12/2026", "2026-13-01", "soon", ""])  # unreadable: treated as absent
    if roll < 0.55:
        return (today + timedelta(days=run.rng.choice([-1, 0, 1]))).isoformat()  # on the boundary
    return (today + timedelta(days=run.rng.randint(-900, 900))).isoformat()


def one_run(run):
    today = run.rng.choice(BOUNDARIES) if run.rng.random() < 0.4 else date(2025, 1, 1) + timedelta(days=run.rng.randint(0, 1095))
    ids = [f"s{i}" for i in range(run.rng.randint(1, 8))]
    sources = []
    for sid in ids:
        sources.append(SimpleNamespace(
            id=sid, approval_status="approved" if run.rng.random() < 0.85 else "pending",
            effective_from=_a_date(run, today), effective_to=_a_date(run, today),
            applies_to=run.rng.sample(SITES, run.rng.choice([0, 0, 1, 1, 2])),
            supersedes=run.rng.sample(ids, min(len(ids), run.rng.choice([0, 0, 0, 1, 2])))))
    run.step("sources", f"{len(sources)} on {today}")
    # The question: a date it is about, and the sites it names.
    parts, when = ["What applies"], today
    roll = run.rng.random()
    if roll < 0.2:
        year = today.year + run.rng.randint(1, 2)
        parts.append(f"in {year}")
        when = date(year, 1, 1)
    elif roll < 0.3:
        parts.append("next year")
        when = date(today.year + 1, 1, 1)
    elif roll < 0.4:
        parts.append(f"in {today.year - 1}")  # a past year: the date asked about is still today
    named = run.rng.sample(SITES, run.rng.choice([0, 0, 1, 1, 2]))
    for site in named:
        parts.append(f"at {site if run.rng.random() < 0.5 else OWN_WORD[site]}")
    question = " ".join(parts) + "?"
    run.step("question", question)

    scope = ScopeFilter(sources, question, today)
    again = ScopeFilter(sources, question, today)
    known = {site for s in sources for site in s.applies_to}  # a space can only recognise the sites its sources name
    named_known = [site for site in named if site in known]
    site = named_known[0] if len(named_known) == 1 else None
    approved = [s for s in sources if s.approval_status == "approved"]

    def in_force(s):
        start, end = _parse(s.effective_from), _parse(s.effective_to)
        return (start is None or start <= when) and (end is None or when <= end)
    replaced = {old for s in approved if in_force(s) for old in s.supersedes if old != s.id}
    for s in approved:
        should = in_force(s) and s.id not in replaced and (site is None or not s.applies_to or site in s.applies_to)
        allowed = scope.allow(s)
        run.promise("same answer twice", allowed == again.allow(s), s.id)
        if allowed:
            run.promise("in force", in_force(s), f"{s.id} {s.effective_from}..{s.effective_to} asked about {when}")
            run.promise("not replaced", s.id not in replaced, s.id)
            run.promise("right site", site is None or not s.applies_to or site in s.applies_to, f"{s.id} {s.applies_to} vs {site}")
        run.promise("exactly these", allowed == should, f"{s.id}: allowed {allowed}, should {should}")


def test_scope_keeps_its_promises_over_random_scenarios():
    assert explore("scope", one_run) >= 1
