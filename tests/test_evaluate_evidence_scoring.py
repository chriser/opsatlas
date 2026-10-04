"""The evidence runner's scoring (scripts/evaluate_evidence.py): a forbidden fact is said only as a whole phrase or one
of its aliases (found after the H3b run on scope set v3, 3 October 2026: the shared-word match counted other facts)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from evaluate_evidence import _said  # noqa: E402


def test_a_forbidden_fact_is_said_only_as_a_phrase():
    assert _said("Demonstrations will use **Synthetic Pack E** [2].", ["Synthetic Pack A"]) == []
    assert _said("Onboarding lasts 5 onboarding days, with a night-shift session [3].", ["3 onboarding days"]) == []
    assert _said("Onboarding lasts 5 days. Sessions are in the Bay 3 training room.", ["3 onboarding days"]) == []
    assert _said("Use synthetic pack alpha.", ["Synthetic Pack A"]) == []  # a phrase inside a longer word is not said


def test_a_forbidden_fact_or_its_alias_is_found_however_it_is_written():
    assert _said("Prospects get a 7-day trial.", ["7-day trial"]) == ["7-day trial"]
    assert _said("Every FRIDAY, environments reset.", ["every Friday"]) == ["every Friday"]
    assert _said("It runs in the Harrier sandbox.", [{"text": "Harrier Sandbox", "aliases": ["Harrier"]}]) == ["Harrier Sandbox"]
    assert _said("It runs in Harrier.", [{"text": "Harrier Sandbox", "aliases": ["Harrier"]}]) == ["Harrier Sandbox"]
