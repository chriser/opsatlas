"""Red team, REF F10: attempts to break the promises of assistant.answer.scope.ScopeFilter (hermetic)."""
from datetime import date
from types import SimpleNamespace

import pytest

from assistant.answer.scope import ScopeFilter

TODAY = date(2026, 10, 3)


def R(id, *, status="approved", start=None, end=None, sites=None, supersedes=None):
    return SimpleNamespace(id=id, approval_status=status, effective_from=start, effective_to=end,
                           applies_to=list(sites or []), supersedes=list(supersedes or []))


# --- right site -------------------------------------------------------------------------------------------------

def test_right_site_substring_inside_another_word_hides_the_named_site():
    """The question names exactly one known site (Leeds); "bathroom" contains the site name "Bath", so asked_site
    counts two sites, gives up, and Bath's guidance answers a Leeds question."""
    leeds, bath = R("leeds-guide", sites=["Leeds"]), R("bath-guide", sites=["Bath"])
    f = ScopeFilter([leeds, bath], "Where is the bathroom key kept at Leeds?", TODAY)
    assert f.allow(leeds)
    assert not f.allow(bath)


def test_right_site_full_name_of_one_site_shares_a_word_with_another():
    """The question names one site by its full name; the other site shares the word "leeds", which _names treats as
    distinctive although both sites have it, so no site is chosen and the Head Office guidance answers."""
    dc = R("dc-guide", sites=["Leeds Distribution Centre"])
    ho = R("ho-guide", sites=["Leeds Head Office"])
    f = ScopeFilter([dc, ho], "What is the fire drill at Leeds Distribution Centre?", TODAY)
    assert f.allow(dc)
    assert not f.allow(ho)


def test_right_site_same_site_spelt_in_two_cases_by_two_sources():
    """Duplicate/inconsistent metadata: one source says "Leeds", another "leeds". The question names Leeds; both
    strings match, asked_site returns None, and Bristol-only guidance answers a Leeds question."""
    a, b = R("a", sites=["Leeds"]), R("b", sites=["leeds"])
    bristol = R("bristol-guide", sites=["Bristol"])
    f = ScopeFilter([a, b, bristol], "What are the Leeds opening hours?", TODAY)
    assert not f.allow(bristol)


# --- exactly these ----------------------------------------------------------------------------------------------

def test_exactly_these_no_site_named_but_a_word_contains_a_site_name():
    """The question names no site, so "right site" holds for every source; "bathroom" makes asked_site pick Bath and
    the Leeds-only source, approved and in force, is wrongly withheld."""
    leeds, bath = R("leeds-guide", sites=["Leeds"]), R("bath-guide", sites=["Bath"])
    f = ScopeFilter([leeds, bath], "Who cleans the bathroom?", TODAY)
    assert f.allow(leeds)


def test_in_force_a_number_that_is_not_a_year_moves_the_asked_date():
    """"2050 units" is not a year. Restated after the stop rule (today, future rules labelled): no word of the question
    moves the date; the policy in force today answers, and one approved for later is kept with its start stated."""
    current = R("current", start="2025-01-01", end="2030-12-31")
    future = R("future", start="2040-01-01")
    f = ScopeFilter([current, future], "What is the discount on orders of 2050 units?", TODAY)
    assert f.allow(current)
    assert f.allow(future) and f.note(future).startswith("(In force from 1 January 2040")


# --- in force, malformed metadata -------------------------------------------------------------------------------

@pytest.mark.parametrize("start,end", [("2027-1-1", None), (" 2027-01-01", None), (None, "2025-6-30")])
def test_in_force_unparseable_date_is_taken_as_no_bound(start, end):
    """A loosely written date is read, not taken as no bound. Restated after the stop rule: a policy starting in 2027 is
    kept with its start stated; one that ended in 2025 is left out."""
    rec = R("p", start=start, end=end)
    f = ScopeFilter([rec], "What is the returns policy?", TODAY)
    if end:
        assert not f.allow(rec)
    else:
        assert f.allow(rec) and f.note(rec).startswith("(In force from 1 January 2027")


# --- not replaced -----------------------------------------------------------------------------------------------

def test_not_replaced_source_naming_itself_in_supersedes():
    """Literal promise: no approved source in force names an allowed source in its supersedes. A source that names
    its own id (e.g. a re-issue keeping the id) is skipped by `old != r.id` and stays allowed."""
    a = R("returns-policy", start="2026-01-01", supersedes=["returns-policy"])
    f = ScopeFilter([a], "What is the returns policy?", TODAY)
    assert not f.allow(a)


# --- no crash, whatever the metadata ----------------------------------------------------------------------------

@pytest.mark.parametrize("rec", [
    R("date-object", start=date(2027, 1, 1)),        # a YAML/JSON loader that parses dates
    R("none-site", sites=["Leeds", None]),            # a null in applies_to
    R("int-site", sites=["Leeds", 42]),               # a site code
], ids=["date-object", "none-in-applies_to", "int-in-applies_to"])
def test_no_crash_whatever_the_metadata(rec):
    f = ScopeFilter([rec, R("other", sites=["Bristol"])], "What applies at Leeds?", TODAY)
    f.allow(rec)
