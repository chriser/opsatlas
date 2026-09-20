"""The unified local turn still enforces provenance and keeps facts provisional."""

import asyncio
import copy
import json

import httpx
import pytest

from services.sme_interviewer.evidence import FixtureEvidence
from services.sme_interviewer.turn_planner import prepare_turn


def session():
    q = {'id': 'opening', 'key': 'story', 'text': 'What happened?'}
    return {'scope': {'region': 'unknown', 'variant': 'unknown', 'date': ''}, 'evidence': FixtureEvidence().snapshot(),
            'segments': [], 'questions': [q], 'current_question': q}


def output(**changes):
    return {'complete': 'finished', 'category': 'responsive', 'kind': 'reported_practice',
            'already_known': 'Finance checked the bank details.', 'missing_detail': 'How they checked.',
            'focus': 'check_evidence', 'sources': ['0'], 'text': 'How did Finance check the bank details?', **changes}


def mock_model(monkeypatch, value):
    calls = []
    def respond(request):
        calls.append(json.loads(request.content))
        v = value.pop(0) if isinstance(value, list) else value
        return httpx.Response(200, json={'message': {'content': json.dumps(v)}})
    client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: client(**kw, transport=httpx.MockTransport(respond)))
    return calls


def test_intent_and_question_use_one_call_and_leave_authoritative_session_untouched(monkeypatch):
    calls = mock_model(monkeypatch, output())
    s = session()
    before = copy.deepcopy(s)
    result = asyncio.run(prepare_turn(s, 'Finance checked the bank details.', 'audio-1'))
    assert len(calls) == 1
    assert s == before
    assert result['context']['segments'][-1]['id'] == 'audio-1'
    assert result['plan']['generation']['review']['verdict'] == 'pending'
    assert result['plan']['generation']['basis'][0]['quote'] == 'Finance checked the bank details.'


@pytest.mark.parametrize('change', [
    {'sources': ['invented']}, {'text': 'How did Acme check the bank details?'},
    {'text': 'How did Finance check the £50,000 bank details?'},
])
def test_invalid_output_cannot_enter_spoken_lane(monkeypatch, change):
    calls = mock_model(monkeypatch, output(**change))
    result = asyncio.run(prepare_turn(session(), 'Finance checked the bank details.', 'audio-1'))
    assert result['plan'] is None
    assert result['question_error']
    assert result['route']['category'] == 'responsive'
    assert len(calls) == 2


def test_unrelated_answer_does_not_generate_a_question(monkeypatch):
    mock_model(monkeypatch, output(category='off_topic', text='', sources=[]))
    result = asyncio.run(prepare_turn(session(), 'An unrelated answer.', 'audio-1'))
    assert result['plan'] is None
    assert result['route']['command'] == 'none'


@pytest.mark.parametrize('text,expected', [('pause', 'pause'), ('Please pause the interview.', 'pause'),
                                         ("Let's review the recap now.", 'recap'), ('Let us review the recap.', 'recap')])
def test_explicit_controls_need_no_inference(monkeypatch, text, expected):
    calls = mock_model(monkeypatch, output())
    result = asyncio.run(prepare_turn(session(), text, 'audio-1'))
    assert not calls
    assert result['route']['command'] == expected


def test_reported_pause_is_not_a_control():
    from services.sme_interviewer.voice_commands import command
    assert command('The manager said to pause the work until the checks were finished.') == 'none'
    assert command('If I say pause, then stop.') == 'none'


def test_hypothetical_must_remain_conditional_at_the_spoken_boundary(monkeypatch):
    mock_model(monkeypatch, output(kind='hypothetical', text='How did Finance check the bank details?'))
    result = asyncio.run(prepare_turn(session(), 'Hypothetically, Finance checked the bank details.', 'audio-1'))
    assert result['plan'] is None
    assert 'hypothetical' in result['question_error']


def test_repair_is_bounded_and_preserves_interpretation(monkeypatch):
    calls = mock_model(monkeypatch, [output(sources=['invented']), output(kind='proposal')])
    result = asyncio.run(prepare_turn(session(), 'Finance checked the bank details.', 'audio-1'))
    assert len(calls) == 2
    assert result['route']['kind'] == 'reported_practice'
    assert result['plan']['generation']['attempts'] == 2


def test_invalid_intent_cannot_be_saved_as_a_checked_answer(monkeypatch):
    mock_model(monkeypatch, output(complete='yes'))
    with pytest.raises(ValueError, match='intent'):
        asyncio.run(prepare_turn(session(), 'Finance checked the bank details.', 'audio-1'))


def test_finished_and_cut_off_are_not_confused_with_answer_completeness(monkeypatch):
    mock_model(monkeypatch, output(complete='cut_off', category='unclear', text='', sources=[]))
    result = asyncio.run(prepare_turn(session(), 'And then the manager was about to', 'audio-1'))
    assert result['route']['complete'] is False
    assert result['plan'] is None
