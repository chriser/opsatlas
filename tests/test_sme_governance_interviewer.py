"""Governance interviews, Tibi side: explain each issue, verify the answer, save only what the Human confirms."""
import asyncio

from services.sme_interviewer import governance_interviewer as module
from services.sme_interviewer.governance_interviewer import CHECKING, GovernanceInterviewer

DUPLICATE = {'key': 'k-dup', 'kind': 'issue', 'check': 'duplicate', 'category': 'consistency', 'severity': 'low',
             'spoken_title': 'DT603 Part A, section 3.1 Implemented solution architecture',
             'spoken_title_b': 'Architecture and technology', 'source_title': 'DT603 Part A · 3.1',
             'headings': ['3.1 Implemented solution architecture', 'Architecture and technology'],
             'relation': {'record_title': 'Architecture and technology', 'cites': 'DT603 Part A · 3.1'},
             'passages': ['I designed OpsAtlas as a local-first web platform.', 'OpsAtlas is a local-first platform.'],
             'detail': "Section '3.1' closely matches 'Architecture' in 'Architecture and technology'.",
             'issues': [{'key': 'k-dup', 'source_id': 's1', 'source_title': 'DT603 Part A · 3.1', 'check': 'duplicate',
                         'detail': 'dup'}], 'answer': None}
OAG = {'key': 'acronym:OAG', 'kind': 'acronym', 'check': 'undefined_acronym', 'category': 'compliance', 'severity': 'low',
       'acronym': 'OAG', 'sources': ['DT603 Part A, section Appendix A'], 'in_source': 'The move from RAG to OAG.',
       'known': [], 'mentions': [{'phrase': 'Ontology-Augmented Generation', 'source_title': 'Appendix A'}],
       'detail': 'OAG', 'issues': [{'key': 'k2', 'source_id': 's2', 'source_title': 'Appendix A',
                                    'check': 'undefined_acronym', 'detail': 'OAG', 'acronyms': ['OAG']}], 'answer': None}
GOV = {**OAG, 'key': 'acronym:GOV', 'acronym': 'GOV', 'mentions': [], 'detail': 'GOV',
       'in_source': 'Selected GOV.UK and legislation.gov.uk material.'}
ANSWERED = {**OAG, 'key': 'acronym:SME', 'acronym': 'SME', 'answer': {'id': 'a', 'status': 'pending', 'answer': 'x'}}


def make(items=(DUPLICATE, OAG, GOV, ANSWERED), verification=None):
    session = {'id': 'session-1', 'evidence': {'governance_interview': {'contributor': 'Chris'}}}
    t = GovernanceInterviewer(session, 'token', 'http://core')
    t.calls = []
    t.verification = verification or {}

    async def call(method, path, body=None, timeout=30):
        t.calls.append((method, path, body))
        if path.endswith('/agenda'):
            return {'items': list(items), 'issues': 27, 'total': len(items)}
        if path.endswith('/verify'):
            return {'verification': t.verification.get(body['issue_key'], [])}
        return {'id': 'saved', 'status': 'pending'}

    t._call = call
    asyncio.run(t.load())
    return t


async def turn(t, text, apply=True):
    running = t.begin(text)
    segments = []
    while (segment := await running.next()) is not None:
        segments.append(segment.text)
    await running.task
    result = running.result
    if apply:
        t.commit(text, result['reply'], result['route'])
        await t.apply(result)
    return segments, result


def test_answered_issues_wait_in_review_and_the_interview_starts_on_request():
    t = make()
    assert [i['key'] for i in t.agenda] == ['k-dup', 'acronym:OAG', 'acronym:GOV']
    segments, result = asyncio.run(turn(t, 'Start'))
    assert segments[:2] == ["Great, let's start.", 'Question 1 of 3.']
    assert 'That looks intended: the record Architecture and technology cites that section as its evidence.' in segments
    assert segments[-1] == 'Shall I record the overlap as intended?' and result['grounding'] == 'governance_question'


def test_a_confirmed_answer_is_verified_read_back_and_saved_only_after_yes():
    t = make(verification={'k-dup': [{'status': 'matches', 'message': 'That fits: the overlap is by design.'}]})
    asyncio.run(turn(t, 'Start'))
    segments, result = asyncio.run(turn(t, "Yes, that's intended."))
    assert segments == ["So I'll record it as intended.", 'That fits: the overlap is by design.',
                        'Shall I save that for your approval?']
    assert result['governance']['save'] is None and not [c for c in t.calls if c[1].endswith('/answers')]
    segments, result = asyncio.run(turn(t, 'Yes please.'))
    saved = [c for c in t.calls if c[1].endswith('/answers')]
    assert segments[0] == 'Saved for your approval.' and segments[1] == 'Next.' and 'OAG is used' in segments[3]
    assert saved[0][2] == {'issue_key': 'k-dup', 'contributor': 'Chris', 'session_id': 'session-1',
                           'answer': "Yes, that's intended.", 'resolution': {'decision': 'accept', 'note': "Yes, that's intended."}}
    assert t.state['saved'] == 1 and t.state['position'] == 1


def test_a_suggested_expansion_can_be_confirmed_and_a_conflicting_one_is_challenged():
    t = make(verification={'acronym:OAG': [{'status': 'conflicts', 'acronym': 'OAG',
                                            'expected': 'Ontology-Augmented Generation',
                                            'message': ('But the sources talk about Ontology-Augmented Generation, '
                                                        'which also spells OAG.')}]})
    asyncio.run(turn(t, 'Start'))
    asyncio.run(turn(t, 'Skip'))
    segments, _ = asyncio.run(turn(t, 'It stands for Open Answer Generation.'))
    assert segments[0] == 'So OAG stands for Open Answer Generation.'
    assert segments[-1] == 'Which should I record: yours, or Ontology-Augmented Generation?'
    segments, _ = asyncio.run(turn(t, "Use the sources' one."))
    saved = [c for c in t.calls if c[1].endswith('/answers')][-1][2]
    assert saved['resolution']['definitions'] == [{'acronym': 'OAG', 'expansion': 'Ontology-Augmented Generation'}]
    assert "chose the sources' wording" in saved['answer'] and segments[0] == 'Saved for your approval.'


def test_yes_to_a_suggestion_defines_it_without_a_model_call(monkeypatch):
    t = make(items=(OAG,))

    async def never(*_):
        raise AssertionError('no model call needed')
    monkeypatch.setattr(t, 'extract', never)
    asyncio.run(turn(t, 'Start'))
    segments, result = asyncio.run(turn(t, "Yes, that's right."))
    assert segments[0] == 'So OAG stands for Ontology-Augmented Generation.' and result['grounding'] == 'governance_verified'


def test_an_unclear_answer_goes_to_the_model_after_an_immediate_acknowledgement(monkeypatch):
    t = make(items=(GOV,))
    asyncio.run(turn(t, 'Start'))

    async def extract(item, text):
        return {'decision': 'accept', 'note': 'It is part of the GOV.UK domain name.'}
    monkeypatch.setattr(t, 'extract', extract)
    segments, _ = asyncio.run(turn(t, 'Well it is really part of the web address for the UK government site.'))
    assert segments[0] in CHECKING and segments[1] == "So I'll record it as fine as it is."


def test_commands_and_no_side_effects_until_applied():
    t = make()
    asyncio.run(turn(t, 'Start'))
    before = dict(t.state)
    asyncio.run(turn(t, 'Yes, intended.', apply=False))  # a speculative turn that was never committed
    assert t.state == before
    segments, _ = asyncio.run(turn(t, 'How many are left?'))
    assert segments[0] == '3 left, including this one, and 0 answered so far.'
    segments, _ = asyncio.run(turn(t, 'Can you repeat that?'))
    assert segments[0] == 'Question 1 of 3.'
    asyncio.run(turn(t, 'Skip this one.'))
    asyncio.run(turn(t, 'Skip.'))
    segments, _ = asyncio.run(turn(t, 'Skip.'))
    assert segments[-1].startswith('That was the last open question.')
    segments, result = asyncio.run(turn(t, "That's all for today."))
    assert segments[0] == 'Thanks, Chris. You answered 0 questions today.' and result['phase'] == 'closed'


def test_a_failed_save_is_announced_once_and_the_count_corrected():
    t = make()
    asyncio.run(turn(t, 'Start'))
    asyncio.run(turn(t, 'Yes, intended.'))
    original = t._call

    async def failing(method, path, body=None, timeout=30):
        if path.endswith('/answers'):
            raise module.httpx.ConnectError('down')
        return await original(method, path, body, timeout)
    t._call = failing
    asyncio.run(turn(t, 'Yes.'))
    assert t.state['saved'] == 0 and t.save_error
    segments, _ = asyncio.run(turn(t, 'How many are left?'))
    assert segments[0].startswith("I couldn't save the last answer") and not t.save_error


def test_the_opening_summarises_the_open_questions():
    t = make()

    async def warm_model(*args, **kwargs):
        return None
    original = module.httpx.AsyncClient

    class Quiet(original):
        async def post(self, *args, **kwargs):
            return None
    module.httpx.AsyncClient = Quiet
    try:
        asyncio.run(t.warm())
    finally:
        module.httpx.AsyncClient = original
    assert t.opening.startswith('Hi Chris. The governance review has 3 open questions for you: 2 compliance and 1 consistency.')


def test_a_bare_expansion_that_spells_the_acronym_is_understood_without_a_model(monkeypatch):
    t = make(items=({**OAG, 'mentions': []},))

    async def never(*_):
        raise AssertionError('no model call needed')
    monkeypatch.setattr(t, 'extract', never)
    asyncio.run(turn(t, 'Start'))
    segments, _ = asyncio.run(turn(t, 'Ontology-Augmented Generation.'))
    assert segments[0] == 'So OAG stands for Ontology-Augmented Generation.'


def test_the_model_echo_of_an_expansion_is_trimmed_to_the_humans_words(monkeypatch):
    t = make(items=(GOV,))
    replies = iter(['{"intent": "answer", "decision": "define", "expansion": "GOV stands for government online.", '
                    '"replacement": "", "url": "", "note": "They defined GOV."}'])

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, path, json=None):
            return module.httpx.Response(200, json={'message': {'content': next(replies)}},
                                         request=module.httpx.Request('POST', 'http://ollama' + path))
    monkeypatch.setattr(module.httpx, 'AsyncClient', Client)
    resolution = asyncio.run(t.extract(GOV, 'well I believe it is government online, really'))
    assert resolution['definitions'] == [{'acronym': 'GOV', 'expansion': 'government online'}]
