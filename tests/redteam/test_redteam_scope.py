"""Red team, REF F10: attempts to break the promises of assistant.answer.scope.ScopeFilter (hermetic).

Restated after the second stop rule (the Human's decision of 3 October 2026, REF H3b): scope reads nothing from the
question, so no site is guessed and none is left out for being another site's; every site-specific passage says its
sites. Dates are read one way, as the details editor reads them, so a loosely written date is unreadable and the source
is left out. The breaks below were found against the earlier designs; each now holds the restated promise."""
from datetime import date
from types import SimpleNamespace

import pytest

from assistant.answer.scope import ScopeFilter

TODAY = date(2026, 10, 3)


def R(id, *, status="approved", start=None, end=None, sites=None, supersedes=None):
    return SimpleNamespace(id=id, approval_status=status, effective_from=start, effective_to=end,
                           applies_to=list(sites or []), supersedes=list(supersedes or []))


# --- sites: none left out, each labelled ----------------------------------------------------------------------------

@pytest.mark.parametrize("sites", [
    ["Leeds", "Bath"],                                          # "bathroom" once named Bath
    ["Leeds Distribution Centre", "Leeds Head Office"],         # two sites sharing a word
    ["Leeds", "leeds", "Bristol"],                              # one site in two cases
], ids=["word-inside-another", "shared-word", "two-cases"])
def test_no_site_is_left_out_and_each_site_passage_says_its_sites(sites):
    records = [R(f"guide-{n}", sites=[site]) for n, site in enumerate(sites)]
    f = ScopeFilter(records, TODAY)
    for record, site in zip(records, sites):
        assert f.allow(record)
        assert f.note(record) == f"(Applies to: {site}.) "


def test_a_number_in_the_question_cannot_move_the_date():
    """"2050 units" is not a year; scope no longer sees the question at all. The policy in force today answers, and one
    approved for later is kept with its start stated."""
    current = R("current", start="2025-01-01", end="2030-12-31")
    future = R("future", start="2040-01-01")
    f = ScopeFilter([current, future], TODAY)
    assert f.allow(current)
    assert f.allow(future) and f.note(future).startswith("(In force from 1 January 2040")


# --- in force, malformed metadata -----------------------------------------------------------------------------------

@pytest.mark.parametrize("start,end", [("2027-1-1", None), (" 2027-01-01", None), (None, "2025-6-30")])
def test_a_loosely_written_date_is_unreadable_and_keeps_the_source_out(start, end):
    """Not taken as no bound, and not read either: the details editor refuses these forms, so scope does too."""
    rec = R("p", start=start, end=end)
    assert not ScopeFilter([rec], TODAY).allow(rec)


# --- not replaced ---------------------------------------------------------------------------------------------------

def test_not_replaced_source_naming_itself_in_supersedes():
    """Literal promise: no approved source in force names an allowed source in its supersedes, itself included."""
    a = R("returns-policy", start="2026-01-01", supersedes=["returns-policy"])
    assert not ScopeFilter([a], TODAY).allow(a)


# --- no crash, whatever the metadata --------------------------------------------------------------------------------

@pytest.mark.parametrize("rec", [
    R("date-object", start=date(2027, 1, 1)),        # a YAML/JSON loader that parses dates
    R("none-site", sites=["Leeds", None]),            # a null in applies_to
    R("int-site", sites=["Leeds", 42]),               # a site code
], ids=["date-object", "none-in-applies_to", "int-in-applies_to"])
def test_no_crash_whatever_the_metadata(rec):
    f = ScopeFilter([rec, R("other", sites=["Bristol"])], TODAY)
    f.allow(rec)
    f.note(rec)
