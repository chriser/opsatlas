"""Random scenarios for scope (REF H3, H3b): which approved source may answer a question, judged by today.

Promises (the Human's decision of 3 October 2026 after the stop rule), checked by an oracle written from the promise
text, not from the filter:
- left out: a source expired today, replaced today by an approved source in force today (itself included), with a date
  that is there but cannot be read, or for another site when the question names exactly one site the space knows;
- kept and labelled: a source approved for a later date answers only with "In force from <start>" in its passages; one
  in force today with an end date says "In force until <end>"; with no site named, a site-specific passage says its site;
- exactly these: every other approved source is allowed (scope never hides a source it should not);
- no date guessing: adding a date or year to the question changes nothing;
- documents only when anything is left out or labelled (REF H3b): the facts map and the process registry are closed;
- the same answer twice, and no crash, whatever the metadata.

Scenario kinds: missing, unreadable and loosely written dates, date objects; dates on the boundary (today itself, 31
December, 1 January); a start after its end; supersede chains, cycles and self-reference; sites by full name, by their
own word, both named, none named, in another case, a site name inside another word, two sites sharing a word; years,
months, quarters, ISO dates and numbers in the question; pending sources; non-text in applies_to. The red teams'
findings of 3 October 2026 (REF F10, H3b) are kinds here.
"""
import re
from datetime import date, timedelta
from types import SimpleNamespace

from scenarios import explore

from assistant.answer.scope import ScopeFilter

SITES = ["Leeds Distribution Centre", "Leeds Head Office", "Bristol head office", "York store", "Bath"]
BOUNDARIES = [date(2025, 12, 31), date(2026, 1, 1), date(2026, 12, 31), date(2027, 1, 1), date(2026, 10, 3)]
GENERIC = {"centre", "center", "office", "head", "site", "distribution", "store", "branch", "the", "and", "pilot"}


def _parse(value):
    """The oracle's reading: None when absent, False when there but unreadable, else the date."""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    match = re.fullmatch(r"\s*(\d{4})-(\d{1,2})-(\d{1,2})\s*", str(value))
    if not match:
        return False
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return False


def _a_date(run, today):
    roll = run.rng.random()
    if roll < 0.15:
        return None
    if roll < 0.25:
        return run.rng.choice(["31/12/2026", "2026-13-01", "soon", "2026-02-30"])  # unreadable: keeps the source out
    when = today + timedelta(days=run.rng.choice([-1, 0, 1]) if roll < 0.5 else run.rng.randint(-900, 900))
    form = run.rng.random()
    if form < 0.15:
        return f"{when.year}-{when.month}-{when.day}"  # loosely written
    if form < 0.25:
        return " " + when.isoformat()
    if form < 0.35:
        return when  # a date object, as a loader that parses dates gives
    return when.isoformat()


def _own_words(site, known):
    words = {w for w in site.casefold().split() if len(w) >= 4 and w not in GENERIC}
    others = {w for s in known if s.casefold() != site.casefold() for w in s.casefold().split()}
    return sorted(words - others)


def one_run(run):
    today = run.rng.choice(BOUNDARIES) if run.rng.random() < 0.4 else date(2025, 1, 1) + timedelta(days=run.rng.randint(0, 1095))
    ids = [f"s{i}" for i in range(run.rng.randint(1, 8))]
    sources = []
    for sid in ids:
        sites = run.rng.sample(SITES, run.rng.choice([0, 0, 1, 1, 2]))
        sites = [s.upper() if run.rng.random() < 0.15 else s for s in sites]  # another case
        if run.rng.random() < 0.05:
            sites.append(run.rng.choice([None, 42, ""]))  # not a site name
        sources.append(SimpleNamespace(
            id=sid, approval_status="approved" if run.rng.random() < 0.85 else "pending",
            effective_from=_a_date(run, today), effective_to=_a_date(run, today), applies_to=sites,
            supersedes=run.rng.sample(ids, min(len(ids), run.rng.choice([0, 0, 0, 1, 2])))))
    run.step("sources", f"{len(sources)} on {today}")
    known = {s.casefold(): s for src in sources for s in src.applies_to if isinstance(s, str) and s}
    parts = ["What applies"]
    mentions = []
    for site in run.rng.sample(SITES, run.rng.choice([0, 0, 1, 1, 2])):
        if run.rng.random() < 0.5 or site.casefold() not in known:
            mention = site if run.rng.random() < 0.7 else site.lower()
        else:
            words = _own_words(site, known.values())
            mention = words[0].title() if words else site.split()[0]  # a shared word names neither
        parts.append(f"at {mention}")
        mentions.append(mention)
    if run.rng.random() < 0.2:
        parts.append("near the bathroom")  # "Bath" inside another word names no site
    question = " ".join(parts) + "?"
    dated = question[:-1] + " " + run.rng.choice([
        f"in {today.year + 1}", f"from 1 January {today.year + 1}", f"as of March {today.year + 1}", f"in Q1 {today.year + 1}",
        f"on {today.year + 1}-01-01", f"in {today.year - 1}", "next year", f"for orders of {today.year + 7} units"]) + "?"
    run.step("question", question)

    scope = ScopeFilter(sources, question, today)
    again = ScopeFilter(sources, question, today)
    with_date = ScopeFilter(sources, dated, today)
    # Which known site each mention names, by the stated rule: a known site's full name, else a word only one known
    # site has (even inside a longer name the space does not know); a word two known sites share names neither.
    unique = {}
    for name in known.values():
        for word in {w for w in name.casefold().split() if len(w) >= 4 and w not in GENERIC}:
            unique.setdefault(word, set()).add(name.casefold())
    named = set()
    for mention in mentions:
        if mention.casefold() in known:
            named.add(mention.casefold())
        else:
            owners = {o for w in mention.casefold().split() if len(unique.get(w, ())) == 1 for o in unique[w]}
            named |= owners
    if len(named) > 1:  # a full name inside a longer named one gives way to it
        named = {n for n in named if not any(n != o and n in o for o in named)}
    site = next(iter(named)) if len(named) == 1 else None
    approved = [s for s in sources if s.approval_status == "approved"]

    def period(s):
        start, end = _parse(s.effective_from), _parse(s.effective_to)
        if start is False or end is False or (end is not None and end < today):
            return "out"
        if start is not None and start > today:
            return "later" if end is None or start <= end else "out"
        return "now"

    def right_site(s):
        names = {x.casefold() for x in s.applies_to if isinstance(x, str) and x}
        return not names or site is None or site in names

    replaced = {old for s in approved if period(s) == "now" for old in s.supersedes}
    labelled_any = False
    for s in approved:
        should = period(s) != "out" and s.id not in replaced and right_site(s)
        allowed, note = scope.allow(s), scope.note(s)
        run.promise("same answer twice", allowed == again.allow(s), s.id)
        run.promise("no date guessing", allowed == with_date.allow(s) and note == with_date.note(s), f"{s.id} with {dated!r}")
        run.promise("exactly these", allowed == should, f"{s.id}: allowed {allowed}, should {should} ({period(s)}, site {site})")
        if allowed and period(s) == "later":
            run.promise("a later source says from when", "In force from" in note, f"{s.id}: {note!r}")
        end = _parse(s.effective_to)
        if allowed and period(s) == "now" and isinstance(end, date):
            run.promise("a current source with an end says until when", "In force until" in note, f"{s.id}: {note!r}")
        names = [x for x in s.applies_to if isinstance(x, str) and x]
        if allowed and names and site is None:
            run.promise("with no site named, a site passage says its site", "Applies to" in note, f"{s.id}: {note!r}")
        labelled_any |= (not should) or bool(note)
    run.promise("documents only when anything is left out or labelled", scope.closes_facts(sources) == labelled_any,
                f"closes_facts {scope.closes_facts(sources)}, should {labelled_any}")


def test_scope_keeps_its_promises_over_random_scenarios():
    assert explore("scope", one_run) >= 1
