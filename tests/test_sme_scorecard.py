"""The engine scorecard measures what it says (audit F07)."""
from types import SimpleNamespace

from services.sme_interviewer.evaluate_engine import check, precision, score

RECORD = {'id': 'r', 'title': 'Deployment', 'text': 'OpsAtlas runs locally. Deployment to 10 teams takes 2 weeks.'}
PRODUCT = {'grounding': 'grounded_synthesis', 'evidence': [RECORD]}


def test_the_audits_answers_fail_the_support_check_though_they_share_the_records_words():
    turn = {'say': 'Can OpsAtlas deploy to 500 teams?'}
    assert check('supported', 'Deployment to 10 teams takes 2 weeks.', PRODUCT, turn, {})
    for reply in ('OpsAtlas deploys to 500 teams in 2 weeks.', 'Deployment to 2 teams takes 10 weeks.', 'We automate payroll.'):
        assert not check('supported', reply, PRODUCT, turn, {}), reply
    # Citation coverage is lexical, and is named so: the swapped figures still share the record's words.
    assert precision('Deployment to 2 teams takes 10 weeks.', PRODUCT) == 1.0


def test_an_abstention_is_not_scored_as_supported_or_unsupported():
    abstained = {'grounding': 'no_approved_evidence'}
    assert check('supported', "I don't yet have approved evidence for that.", abstained, {'say': 'x'}, {}) is None


def test_length_limits_apply_to_approved_wording_too():
    long = 'Approved wording. ' * 30
    assert not check('brief', long, {'grounding': 'approved_fallback'}, {}, {})
    assert not check('short', long, {'grounding': 'approved_spoken'}, {}, {})


def test_rehearsal_and_conversation_are_measured_apart_with_their_sample_sizes():
    def row(mode, route, grounding, ok=True):
        return {'mode': mode, 'scenario': 's', 'turn': 0, 'route': route, 'route_ok': True, 'checks': {'x': ok},
                'grounding': grounding, 'blocked': 1 if grounding == 'approved_fallback' else 0, 'precision': None,
                'first_segment_ms': 500.0}
    turns = [row('chat', 'conversation', 'conversation'), row('chat', 'product', 'grounded_synthesis'),
             row('chat', 'product', 'no_approved_evidence'), row('rehearsal', 'rehearsal', 'approved_fallback', ok=False)]
    card = score(turns, SimpleNamespace(runs=1, judge=False, replay=None), 'digest')
    m = card['measures']
    assert m['appropriateness'] == 1.0 and m['rehearsal_appropriateness'] == 0.0
    assert m['abstention_rate'] == round(1 / 3, 3) and m['fallback_rate'] == round(1 / 3, 3) and m['blocked_sentences'] == 1
    assert card['sample_sizes']['rehearsal'] == 1 and card['sample_sizes']['evidence_replies'] == 3 and card['scenarios_sha256']
