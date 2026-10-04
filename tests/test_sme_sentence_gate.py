"""The evidence layer's sentence gate on labelled sentences (audit F03, F07).

Two sets in evaluation/sets/tibi/: the adversarial set (the audit's three cases, and cases
written with the fix, which shaped it) and a held-out set written before the fixed gate was run and not tuned
against. Faithful restatements must all be allowed (over-blocking is measured, not assumed away); the block rates
are floors at the first measured result, so a regression shows. The misses are known limits of lexical checks:
subject changes, scope, and modality on words outside the claim vocabulary.
"""
import json
from pathlib import Path

import pytest

from services.sme_interviewer.tibi import sentence_gate

EVALUATION = Path(__file__).resolve().parents[1] / 'evaluation/sets/tibi'
FLOORS = {'adversarial': 14, 'heldout': 6}  # unsupported sentences blocked when first measured


def outcomes(name):
    data = json.loads((EVALUATION / f'sentence-gate-{name}.json').read_text())
    for case in data['cases']:
        records = [{'id': r, **data['records'][r]} for r in case['records']]
        text = ' '.join(r['title'] + '. ' + r['text'] for r in records)
        yield case, 'block' if sentence_gate(case['sentence'], records, text, case['question']) else 'allow'


@pytest.mark.parametrize('name', sorted(FLOORS))
def test_faithful_sentences_pass_and_unsupported_ones_are_blocked_at_least_as_often_as_measured(name):
    results = list(outcomes(name))
    assert [c['id'] for c, got in results if c['expect'] == 'allow' and got == 'block'] == []  # no over-blocking
    blocked = sum(1 for c, got in results if c['expect'] == 'block' and got == 'block')
    assert blocked >= FLOORS[name]


def test_every_case_the_audit_supplied_is_blocked():
    audit = [(c, got) for c, got in outcomes('adversarial') if c['origin'] == 'audit']
    assert len(audit) == 3 and all(got == 'block' for _, got in audit)
