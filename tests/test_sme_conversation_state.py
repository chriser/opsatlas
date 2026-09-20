"""Coverage must survive new answers and restart, but not corrected source history."""
import asyncio
import json
import uuid

import httpx
import pytest

from services.sme_interviewer.dialogue import (
    DETAILS,
    LocalPlanner,
    checked_observations,
    coverage_context,
    merge_coverage,
    retained_coverage,
)
from services.sme_interviewer.evidence import FixtureEvidence
from services.sme_interviewer.ledger import Ledger


def account():
    s = {"scope": {"region": "UK", "variant": "standard", "date": "2026-09-19"},
         "evidence": FixtureEvidence().snapshot(),
         "questions": [{"id": "q0", "key": "story", "text": "What happened?"},
                       {"id": "q1", "key": "sequence", "text": "Is the sequence correct?"}],
         "segments": [{"id": "s1", "revision": 1, "kind": "reported_practice", "state": "confirmed",
                       "text": "The buyer requested a supplier for a repair.", "question_id": "q0"}]}
    obs = checked_observations([{"detail": "request_start", "assessment": "addressed", "segment_id": "s1",
                                 "quote": s["segments"][0]["text"]}], s)
    s["analysis"] = {"valid": False, "observations": obs, "coverage_context": coverage_context(s, {"s1"})}
    return s


def add_no(s):
    s["questions"].append({"id": "q2", "key": "controls", "detail": "required_checks",
                           "text": "Did the buyer provide a renewed certificate?"})
    s["segments"].append({"id": "s2", "revision": 1, "kind": "reported_practice", "state": "confirmed",
                          "text": "No", "question_id": "q2"})


def test_new_short_answer_does_not_erase_previous_coverage():
    s = account()
    add_no(s)
    old, seen = retained_coverage(s)
    assert [o["detail"] for o in merge_coverage(old, [])] == ["request_start"]
    assert seen == {"s1"}
    assert len(s["analysis"]["coverage_context"]["segments"]) == 1


@pytest.mark.parametrize("change", ["text", "revision", "kind", "state", "question", "scope"])
def test_corrections_invalidate_dependent_coverage(change):
    s = account()
    add_no(s)
    if change == "question":
        s["questions"][0]["text"] = "Who approved it?"
    elif change == "scope":
        s["scope"]["region"] = "France"
    else:
        s["segments"][0][change] = {"text": "Correction: no repair was requested.", "revision": 2,
                                    "kind": "hypothetical", "state": "provisional"}[change]
    assert retained_coverage(s) == ([], set())


def test_explicit_unknown_replaces_prior_assessment_but_hypothetical_does_not():
    s = account()
    old, _ = retained_coverage(s)
    uncertain = {**old[0], "assessment": "left_open"}
    assert merge_coverage(old, [uncertain])[0]["assessment"] == "left_open"
    hypothetical = {**old[0], "assessment": "illustrative"}
    assert merge_coverage(old, [hypothetical]) == old


def test_complete_planning_turn_preserves_coverage_when_new_assessment_is_empty(monkeypatch):
    s = account()
    add_no(s)
    calls = []

    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, path, json):
            calls.append(json)
            raw = dict.fromkeys(DETAILS, [])
            return httpx.Response(200, json={"message": {"content": __import__("json").dumps(raw)}},
                                  request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"))

    async def unavailable(*args):
        raise ValueError("Question failed review")

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    monkeypatch.setattr("services.sme_interviewer.conversation.compose_followup", unavailable)
    result = asyncio.run(LocalPlanner().plan(s))
    assert result["reason"] and result["observations"][0]["detail"] == "request_start"
    assert result["coverage_context"]["assessed_ids"] == ["s1", "s2"]
    payload = json.loads(calls[0]["messages"][1]["content"])
    assert payload["sentences"][-1]["answer_to_question"] == "Did the buyer provide a renewed certificate?"
    assert payload["sentences"][-1]["new"] is True
    assert payload["sentences"][0]["new"] is False


def test_failed_extraction_does_not_mark_unassessed_answer_as_seen(monkeypatch):
    s = account()
    add_no(s)

    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs): raise httpx.ReadTimeout("test")

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    plan = asyncio.run(LocalPlanner().plan(s))
    s["analysis"] = plan
    assert retained_coverage(s)[1] == {"s1"}
    assert plan["observations"][0]["detail"] == "request_start"


def test_persisted_coverage_survives_ledger_reload_and_is_invalidated_by_correction(tmp_path):
    store = Ledger(tmp_path/'sessions.sqlite')
    s = store.create(FixtureEvidence().snapshot(), account()["scope"], uuid.uuid4().hex)
    s = store.mutate(s['id'], s['revision'], uuid.uuid4().hex, 'segment_saved',
                     {'text': 'The buyer requested a supplier for a repair.', 'kind': 'reported_practice', 'state': 'confirmed'})
    s = store.mutate(s['id'], s['revision'], uuid.uuid4().hex, 'plan_requested', {})
    seg = s['segments'][0]
    obs = checked_observations([{'detail':'request_start', 'assessment':'addressed',
                                'segment_id':seg['id'], 'quote':seg['text']}], s)
    plan={'question':'sequence','mode':'guided','observations':obs,
          'coverage_context':coverage_context(s,{seg['id']})}
    store.apply_plan(s['id'], s['revision'], plan)
    s = Ledger(tmp_path/'sessions.sqlite').get(s['id'])
    s = store.mutate(s['id'], s['revision'], uuid.uuid4().hex, 'segment_saved',
                     {'text':'Yes', 'kind':'reported_practice', 'state':'confirmed'})
    assert retained_coverage(s)[0] == obs
    s = store.mutate(s['id'], s['revision'], uuid.uuid4().hex, 'segment_saved',
                     {'segment_id':seg['id'],'segment_revision':1,'text':'Correction: the request was cancelled.',
                      'kind':'reported_practice','state':'confirmed'})
    assert retained_coverage(s) == ([], set())


def test_hypothetical_coverage_can_be_retained_without_becoming_reported_practice():
    s = account()
    s["segments"][0]["kind"] = "hypothetical"
    s["analysis"]["observations"][0].update(kind="hypothetical", assessment="illustrative")
    s["analysis"]["coverage_context"] = coverage_context(s, {"s1"})
    assert retained_coverage(s)[0][0]["assessment"] == "illustrative"


def test_writer_cannot_reopen_an_addressed_focus_even_if_review_would_pass():
    from services.sme_interviewer.conversation import compose_followup
    from services.sme_interviewer.dialogue import source_sentences

    s = account()
    responses = []

    class Client:
        async def post(self, path, json):
            responses.append(json)
            raw = {"already_known": "The buyer requested a supplier for a repair.",
                   "missing_detail": "The trigger", "text": "What triggered the request for this supplier?",
                   "action": "probe", "focus": "request_start", "sources": ["0"]}
            return httpx.Response(200, json={"message": {"content": __import__("json").dumps(raw)}},
                                  request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"))

    with pytest.raises(ValueError, match="No conversational"):
        asyncio.run(compose_followup(Client(), 'local', s, source_sentences(s['segments'], s),
                                     s['analysis']['observations'], DETAILS))
    assert len(responses) == 2  # Rejected without relying on the fallible reviewer.
    assert 'request_start' not in responses[0]['format']['properties']['focus']['enum']


def test_timeline_clause_is_not_allowed_to_smuggle_in_an_unconfirmed_event():
    from services.sme_interviewer.conversation import validate_question

    s = account()
    basis = [{"segment_id": "s1", "segment_revision": 1, "kind": "reported_practice",
              "quote": s["segments"][0]["text"]}]
    with pytest.raises(ValueError, match="recorded"):
        validate_question('Did the supplier get released after Finance recorded approval?', basis, s)


@pytest.mark.parametrize('question', [
    {'id':'q-unknown','key':'followup','text':'Who could find that date?'},
    {'id':'q-unknown','key':'scope','detail':'process_date','text':'When did you record the hold?'},
])
def test_unknown_answer_cannot_erase_an_unrelated_known_detail(monkeypatch, question):
    s = account()
    s['questions'].append(question)
    s['segments'].append({'id':'s2','revision':1,'text':'I do not know.', 'kind':'uncertain',
                          'state':'confirmed','question_id':'q-unknown'})

    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, path, json):
            raw = dict.fromkeys(DETAILS, [])
            raw['request_start'] = ['1']  # Deliberately misclassified by the model.
            return httpx.Response(200,json={'message':{'content':__import__('json').dumps(raw)}},
                                  request=httpx.Request('POST','http://127.0.0.1:11434/api/chat'))

    async def unavailable(*args): raise ValueError('test')
    monkeypatch.setattr(httpx,'AsyncClient',Client)
    monkeypatch.setattr('services.sme_interviewer.conversation.compose_followup',unavailable)
    plan = asyncio.run(LocalPlanner().plan(s))
    known = next(o for o in plan['observations'] if o['detail']=='request_start')
    assert known['assessment']=='addressed' and known['segment_id']=='s1'


def test_draft_open_point_uses_actual_question_instead_of_generic_topic():
    from services.sme_interviewer.review import packet

    s = account()
    s.update(id='fictional',revision=4,title='Synthetic',gaps=[])
    s['questions'].append({'id':'q-date','key':'systems','detail':'record_changes',
                           'text':'When did you record the hold in the ERP?'})
    s['segments'].append({'id':'s2','revision':1,'text':'I do not remember the date.',
                          'kind':'uncertain','state':'confirmed','question_id':'q-date'})
    s['analysis']={'valid':True,'observations':checked_observations([
        {'detail':'record_changes','assessment':'left_open','segment_id':'s2','quote':'I do not remember the date.'}],s)}
    result = packet(s,True)
    assert 'Left open: When did you record the hold in the ERP?' in result['open_points']


def test_service_failure_preserves_valid_prior_coverage(tmp_path):
    from services.sme_interviewer.interview import Interviews

    class Broken:
        async def plan(self, *args): raise TimeoutError('test deadline')

    async def run():
        interviews = Interviews(tmp_path, planner=Broken())
        store = interviews.store
        s = store.create(FixtureEvidence().snapshot(), account()['scope'], uuid.uuid4().hex)
        s = store.mutate(s['id'],s['revision'],uuid.uuid4().hex,'segment_saved',
                         {'text':account()['segments'][0]['text'],'kind':'reported_practice','state':'confirmed'})
        s = store.mutate(s['id'],s['revision'],uuid.uuid4().hex,'plan_requested',{})
        seg = s['segments'][0]
        obs = checked_observations([{'detail':'request_start','assessment':'addressed',
                                    'segment_id':seg['id'],'quote':seg['text']}],s)
        store.apply_plan(s['id'],s['revision'],{'question':'sequence','mode':'guided','observations':obs,
                                              'coverage_context':coverage_context(s,{seg['id']})})
        s = store.get(s['id'])
        s = store.mutate(s['id'],s['revision'],uuid.uuid4().hex,'segment_saved',
                         {'text':'Yes','kind':'reported_practice','state':'confirmed'})
        await interviews.plan(s['id'],{'expected_revision':s['revision'],'request_id':uuid.uuid4().hex})
        await interviews.tasks[s['id']]
        result = store.get(s['id'])
        assert result['analysis']['reason'] and result['analysis']['observations'] == obs
        assert retained_coverage(result)[1] == {seg['id']}
        await interviews.close()

    asyncio.run(run())


def test_an_approval_role_cannot_be_invented_for_certificate_renewal():
    from services.sme_interviewer.conversation import validate_question

    s = account()
    s['segments'][0]['text'] = 'I asked the buyer for a renewed certificate.'
    basis = [{'segment_id':'s1','segment_revision':1,'kind':'reported_practice',
              'quote':s['segments'][0]['text']}]
    with pytest.raises(ValueError,match='No approval step'):
        validate_question('Who is responsible for approving the renewal of the insurance certificate?',basis,s)
    assert validate_question('Does renewing the certificate require an approval?',basis,s)


@pytest.mark.parametrize('wording', [
    'I did not write this in any system or document.',
    "We didn't record anything in any document.",
])
def test_explicit_absence_of_recording_covers_location_and_changes(wording):
    from services.sme_interviewer.dialogue import explicit_absence_of_recording, source_sentences

    s = account()
    s['segments'][0]['text'] = wording
    observations = explicit_absence_of_recording(source_sentences(s['segments'],s),s)
    assert {o['detail'] for o in observations} == {'record_location','record_changes'}
    assert all(o['quote']==wording and o['status']=='unverified' for o in observations)


def test_narrow_recording_negative_does_not_swallow_a_contrast_or_condition():
    from services.sme_interviewer.dialogue import explicit_absence_of_recording, source_sentences

    s = account()
    s['segments'][0]['text'] = 'I did not write this in any system, but I recorded it in a paper ledger.'
    assert explicit_absence_of_recording(source_sentences(s['segments'],s),s) == []


def test_first_person_hold_is_not_asked_as_an_unknown_actor():
    from services.sme_interviewer.conversation import review_question

    class NoInference:
        async def post(self, *args, **kwargs): raise AssertionError('Unneeded inference')

    result = asyncio.run(review_question(NoInference(),
        'I noticed the certificate had expired, so I kept the supplier on hold.',[],
        'Who decided to place the supplier on hold?'))
    assert result['verdict']=='reject' and result['method']=='explicit_first_person_hold'


def test_changed_extraction_version_invalidates_retained_assessments():
    s = account()
    s["analysis"]["coverage_context"]["version"] = "earlier-extractor"
    assert retained_coverage(s) == ([], set())


def test_explicit_activation_and_approver_are_not_left_for_the_model_to_rediscover():
    from services.sme_interviewer.dialogue import explicit_process_facts, source_sentences

    s = account()
    s["segments"][0]["text"] = (
        "The supplier was activated after the manager responsible for activation approved it, "
        "and the company could access the information."
    )
    observations = explicit_process_facts(source_sentences(s["segments"], s), s)
    assert {item["detail"] for item in observations} == {"outcome", "decision_owner"}
    assert all(item["quote"] == s["segments"][0]["text"] for item in observations)


@pytest.mark.parametrize("wording,kind", [
    ("I asked whether the supplier was activated.", "reported_practice"),
    ("If the supplier was activated, the company could access the information.", "reported_practice"),
    ("The supplier would be activated after approval.", "hypothetical"),
])
def test_contingent_or_imagined_activation_is_not_treated_as_an_actual_outcome(wording, kind):
    from services.sme_interviewer.dialogue import explicit_process_facts, source_sentences

    s = account()
    s["segments"][0].update(text=wording, kind=kind)
    assert explicit_process_facts(source_sentences(s["segments"], s), s) == []


def test_explicit_completed_outcome_survives_an_empty_model_assessment(monkeypatch):
    s = account()
    s["segments"][0]["text"] = "The supplier was activated after the manager approved it."

    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, path, json):
            raw = dict.fromkeys(DETAILS, [])
            return httpx.Response(200, json={"message": {"content": __import__("json").dumps(raw)}},
                                  request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"))

    async def unavailable(*args):
        raise ValueError("Question failed review")

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    monkeypatch.setattr("services.sme_interviewer.conversation.compose_followup", unavailable)
    result = asyncio.run(LocalPlanner().plan(s))
    assert {item["detail"] for item in result["observations"]} == {"outcome", "decision_owner"}


def test_an_explicit_activation_cannot_be_reasked_as_a_yes_no_outcome():
    from services.sme_interviewer.conversation import validate_question

    s = account()
    s["segments"][0]["text"] = "The supplier was activated after the manager approved it."
    basis = [{"segment_id": "s1", "segment_revision": 1, "kind": "reported_practice",
              "quote": s["segments"][0]["text"]}]
    with pytest.raises(ValueError, match="already stated the supplier outcome"):
        validate_question("Was the supplier activated?", basis, s)
    assert validate_question("What additional checks were required before the supplier was activated?", basis, s)


def test_unstated_recording_location_is_reworded_as_a_neutral_question():
    from services.sme_interviewer.conversation import safe_question_wording

    raw = {"focus": "record_location", "text": "Where was the supplier hold action recorded?",
           "sources": ["0"], "missing_detail": "Where the hold was recorded."}
    sentences = {"0": {"quote": "I kept the supplier on hold."}}
    repaired = safe_question_wording(raw, sentences, DETAILS)
    assert repaired["text"] == "Was the decision recorded, and if so where?"
    assert repaired["focus"] == "record_location"


def test_compound_low_reasoning_question_uses_the_single_safe_detail_prompt():
    from services.sme_interviewer.conversation import safe_question_wording

    raw = {"focus": "check_evidence",
           "text": "Did the buyer provide the renewed certificate, and how was it verified?",
           "sources": ["0"], "missing_detail": "Whether it arrived and how it was checked."}
    repaired = safe_question_wording(raw, {"0": {"quote": "I requested a renewed certificate."}}, DETAILS)
    assert repaired["text"] == "What evidence shows the results of the checks?"


def test_unstated_handover_is_not_assumed():
    from services.sme_interviewer.conversation import validate_question
    s = account()
    s['segments'][0]['text'] = 'The shift lead released the supplier because the order was urgent.'
    basis = [{'segment_id': 's1', 'segment_revision': 1, 'kind': 'reported_practice',
              'quote': s['segments'][0]['text']}]
    with pytest.raises(ValueError, match='No handover'):
        validate_question('What responsibility did the shift lead hand off to the supplier?', basis, s)
    assert validate_question('Did responsibility pass to anyone else after that?', basis, s)
