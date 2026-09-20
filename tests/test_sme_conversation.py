"""Generated questions must be grounded, reviewed and tied to the current revision."""

import asyncio
import copy
import json
import uuid

import httpx
import pytest

from services.sme_interviewer.conversation import (
    REVIEW_MODEL,
    checked_generation,
    checked_spoken_question,
    compose_followup,
    context_hash,
)
from services.sme_interviewer.dialogue import DETAILS, LocalPlanner, question_text, source_sentences
from services.sme_interviewer.evidence import FixtureEvidence, digest
from services.sme_interviewer.ledger import Ledger


def session():
    return {"scope": {"region": "unknown", "variant": "unknown", "date": ""},
            "evidence": FixtureEvidence().snapshot(), "questions": [{"key": "sequence", "text": "Is the sequence correct?"}],
            "segments": [{"id": "s1", "revision": 1, "kind": "reported_practice", "state": "confirmed",
                          "text": "The insurance certificate had expired. I kept the supplier on hold."}]}


def candidate(text="What would you need before lifting the hold on this supplier?"):
    return {"already_known": "The supplier was kept on hold.", "missing_detail": "Requirements for lifting the hold.",
            "text": text, "action": "probe", "focus": "required_checks", "sources": ["1"]}


def reviewed(s, raw=None):
    result = checked_generation(raw or candidate(), source_sentences(s["segments"], s), s, DETAILS)
    result.update(content_hash=digest(result), context_hash=context_hash(s),
                  review={"verdict": "pass", "reason": "Useful missing detail.", "model": REVIEW_MODEL})
    return result


def test_question_is_generated_without_automatic_readback():
    s = session()
    generation = reviewed(s)
    plan = {"question": "controls", "generation": generation}
    assert question_text(plan, s) == candidate()["text"]
    assert "you said" not in question_text(plan, s)
    assert generation["basis"][0]["quote"] == "I kept the supplier on hold."


@pytest.mark.parametrize("text", [
    "You said the supplier stayed on hold. What happened?",
    "What happened? Who decided?",
    "Did the buyer provide a certificate, and what happened next?",
    "What is your access token?",
    "Could you open https://example.com?",
    "What did you do with £50,000?",
    "What happened <script>alert(1)</script>?",
    "Tell me what happened next.",
])
def test_bad_spoken_output_rejected(text):
    s = session()
    with pytest.raises(ValueError):
        checked_generation(candidate(text), source_sentences(s["segments"], s), s, DETAILS)


@pytest.mark.parametrize("change", ["wording", "kind", "revision", "provisional", "history", "scope", "tamper", "unreviewed"])
def test_revision_and_review_boundary_rechecked(change):
    s = session()
    generation = reviewed(s)
    if change == "wording":
        s["segments"][0]["text"] = "The record was released."
    elif change == "kind":
        s["segments"][0]["kind"] = "hypothetical"
    elif change == "revision":
        s["segments"][0]["revision"] = 2
    elif change == "provisional":
        s["segments"][0]["state"] = "provisional"
    elif change == "history":
        s["questions"].append({"key": "controls", "text": candidate()["text"]})
    elif change == "scope":
        s["scope"]["region"] = "UK"
    elif change == "tamper":
        generation["text"] = "Who authorised the activation?"
    else:
        generation["review"]["verdict"] = "reject"
    with pytest.raises(ValueError):
        checked_spoken_question(generation, s)


def test_unknown_source_and_exact_repeats_rejected():
    s = session()
    value = candidate()
    value["sources"] = ["invented"]
    with pytest.raises(ValueError):
        checked_generation(value, source_sentences(s["segments"], s), s, DETAILS)
    s["questions"].append({"key": "controls", "text": candidate()["text"].upper()})
    with pytest.raises(ValueError, match="Repeated"):
        checked_generation(candidate(), source_sentences(s["segments"], s), s, DETAILS)


class Client:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    async def post(self, path, json):
        self.calls.append(json)
        output = next(self.outputs)
        if isinstance(output, BaseException):
            raise output
        if isinstance(output, dict) and "already_known" in output:
            # Ordinary fixture writers obey the selected-purpose schema. Hostile
            # schema violations are exercised separately in the state tests.
            output = {**output, "focus": json["format"]["properties"]["focus"]["enum"][0]}
        return httpx.Response(200, json={"message": {"content": __import__("json").dumps(output)}},
                              request=httpx.Request("POST", "http://127.0.0.1:11434" + path))


def test_reviewer_rejects_invented_activation_then_repair_is_used():
    s = session()
    bad = candidate("Why did you activate the supplier despite the expired certificate?")
    rejected = {"reason": "The supplier stayed on hold; activation is invented.", "verdict": "reject"}
    accepted = {"reason": "Useful missing detail.", "verdict": "pass"}
    client = Client([bad, rejected, candidate(), accepted])
    result = asyncio.run(compose_followup(client, "local", s, source_sentences(s["segments"], s), [], DETAILS))
    assert result["attempts"] == 2 and result["text"] == candidate()["text"]
    repair = json.loads(client.calls[2]["messages"][1]["content"])["repair"]
    assert "activation is invented" in repair["issue"]


def test_twice_rejected_question_is_never_returned_and_cancel_propagates():
    s = session()
    rejected = {"reason": "Already answered", "verdict": "reject"}
    client = Client([candidate(), rejected, candidate(), rejected])
    with pytest.raises(ValueError, match="No conversational"):
        asyncio.run(compose_followup(client, "local", s, source_sentences(s["segments"], s), [], DETAILS))
    client = Client([asyncio.CancelledError()])
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(compose_followup(client, "local", s, source_sentences(s["segments"], s), [], DETAILS))


def test_generated_question_is_persisted_with_provenance_and_replays_exactly(tmp_path):
    store = Ledger(tmp_path / "ledger.sqlite")
    s = store.create(FixtureEvidence().snapshot(), session()["scope"], str(uuid.uuid4()))
    s = store.mutate(s["id"], s["revision"], str(uuid.uuid4()), "segment_saved",
                     {"text": session()["segments"][0]["text"], "kind": "reported_practice", "state": "confirmed"})
    s = store.mutate(s["id"], s["revision"], str(uuid.uuid4()), "plan_requested", {})
    generation = reviewed(s)
    plan = {"question": "controls", "detail": "required_checks", "mode": "local_model", "generation": generation}
    assert store.apply_plan(s["id"], s["revision"], plan)
    saved = store.get(s["id"])
    assert saved["current_question"]["text"] == generation["text"]
    assert saved["current_question"]["generation"] == generation
    assert store.apply_plan(s["id"], s["revision"], plan) is False


def test_sequence_does_not_quote_the_answer_back():
    s = session()
    s["questions"] = []
    result = asyncio.run(LocalPlanner().plan(copy.deepcopy(s)))
    assert result["question"] == "sequence"
    assert "certificate" not in result["text"] and "you said" not in result["text"]


def test_corrected_number_cannot_reenter_the_next_question():
    s = session()
    s["segments"][0]["text"] = "The limit is £15,000, not £50,000."
    raw = candidate("Who approved the £50,000 limit?")
    raw["sources"] = ["0"]
    with pytest.raises(ValueError, match="corrected number"):
        checked_generation(raw, source_sentences(s["segments"], s), s, DETAILS)


def test_short_answer_is_available_with_its_actual_question():
    s = session()
    s["questions"].append({"id": "q2", "key": "controls", "text": "Was the supplier activated?"})
    s["segments"].append({"id": "s2", "revision": 1, "text": "No", "kind": "reported_practice",
                          "state": "confirmed", "question_id": "q2"})
    source = list(source_sentences(s["segments"], s).values())[-1]
    assert source["quote"] == "No" and source["answer_to_question"] == "Was the supplier activated?"


def test_hypothetical_accepts_a_conditional_question_without_turning_it_into_practice():
    s = session()
    s["segments"][0].update(text="We could ask Operations to approve an urgent supplier. This has not happened.", kind="hypothetical")
    raw = candidate("If Operations were to approve an urgent supplier, what criteria would they use?")
    raw["sources"] = ["0"]
    result = checked_generation(raw, source_sentences(s["segments"], s), s, DETAILS)
    assert result["basis"][0]["kind"] == "hypothetical"
    raw["text"] = "What criteria does Operations use to approve suppliers?"
    with pytest.raises(ValueError, match="hypothetical"):
        checked_generation(raw, source_sentences(s["segments"], s), s, DETAILS)


def test_explicit_unknown_uses_source_finding_guide_without_an_echo(monkeypatch):
    s = session()
    s["segments"][0].update(text="I do not know who approves it.", kind="uncertain")
    calls = []

    class CoverageClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, path, json):
            calls.append(path)
            return httpx.Response(200, json={"message": {"content": __import__("json").dumps(dict.fromkeys(DETAILS, []))}},
                                  request=httpx.Request("POST", "http://127.0.0.1:11434" + path))

    monkeypatch.setattr(httpx, "AsyncClient", CoverageClient)
    plan = asyncio.run(LocalPlanner().plan(s))
    assert plan["guide_reason"] == "explicit_unknown" and plan["question"] == "followup"
    assert "Which role or source" in plan["text"] and "you said" not in plan["text"]
    assert calls == []  # This deterministic route no longer waits for any model call.


def test_an_unknown_source_is_not_requested_again():
    s = session()
    s['questions'].append({'id': 'q-source', 'key': 'followup', 'text': 'Which role or source could clarify it?'})
    s['segments'].append({'id': 's2', 'revision': 1, 'text': 'I do not know who could clarify it.',
                          'kind': 'uncertain', 'state': 'confirmed', 'question_id': 'q-source'})
    raw = candidate('What information first arrived with this supplier request?')
    raw['action'] = 'move_on'
    accepted = {'reason': 'A different part of the account remains unexplored.', 'verdict': 'pass'}
    client = Client([raw, accepted])
    result = asyncio.run(compose_followup(client, 'local', s, source_sentences(s['segments'], s), [], DETAILS))
    assert result['action'] == 'move_on'
    assert client.calls[0]['format']['properties']['action']['enum'] == ['move_on']


def test_model_cannot_override_the_unknown_point_control():
    s = session()
    s['segments'][0].update(text='I do not know who approved it.', kind='uncertain')
    client = Client([candidate('Who approved this supplier request?'), candidate('Who released this supplier?')])
    with pytest.raises(ValueError, match='No conversational'):
        asyncio.run(compose_followup(client, 'local', s, source_sentences(s['segments'], s), [], DETAILS))
    assert len(client.calls) == 2  # Both are rejected before semantic review.


def test_skipping_a_source_question_does_not_restart_the_unknown_loop():
    from services.sme_interviewer.dialogue import source_requested

    s = session()
    s['questions'][0]['id'] = 'q-original'
    s['segments'][0].update(text='I do not know who approved it.', kind='uncertain', question_id='q-original')
    assert not source_requested(s, s['segments'][0])
    s['questions'].extend([
        {'id': 'q-source', 'key': 'followup', 'text': 'Which role or source could clarify it?'},
        {'id': 'q-moved', 'key': 'systems', 'text': 'Where did you record the request?'},
    ])
    assert source_requested(s, s['segments'][0])
    # A new uncertain answer on another question is a new open point.
    new = {**s['segments'][0], 'id': 's2', 'question_id': 'q-moved'}
    assert not source_requested(s, new)


def test_short_answer_draft_retains_the_exact_question_without_expanding_its_meaning(tmp_path):
    from services.sme_interviewer.review import markdown

    store = Ledger(tmp_path / 'ledger.sqlite')
    s = store.create(FixtureEvidence().snapshot(), session()['scope'], str(uuid.uuid4()))
    s = store.mutate(s['id'], s['revision'], str(uuid.uuid4()), 'segment_saved',
                     {'text': session()['segments'][0]['text'], 'kind': 'reported_practice', 'state': 'confirmed'})
    s = store.mutate(s['id'], s['revision'], str(uuid.uuid4()), 'plan_requested', {})
    generation = reviewed(s, candidate('Did you later activate this supplier?'))
    store.apply_plan(s['id'], s['revision'], {'question': 'controls', 'mode': 'local_model', 'generation': generation})
    s = store.get(s['id'])
    question = s['current_question']
    s = store.mutate(s['id'], s['revision'], str(uuid.uuid4()), 'segment_saved',
                     {'text': 'No', 'kind': 'reported_practice', 'state': 'confirmed'})
    draft = store.finish(s['id'], s['revision'], True)['review']
    claim = draft['claims'][-1]
    assert claim['wording'] == 'No'
    assert claim['question_id'] == question['id']
    assert claim['question'] == 'Did you later activate this supplier?'
    assert 'Question: Did you later activate this supplier?\n\n> No' in markdown(draft)
    assert claim['approval'] == 'not_requested'


@pytest.mark.parametrize('wording', [
    'I do not know who approves emergency requests.',
    "We don't know who approves emergency requests.",
    'I cannot remember who approves emergency requests.',
])
def test_explicit_unknown_repeat_is_rejected_without_depending_on_a_model(wording):
    from services.sme_interviewer.conversation import review_question

    client = Client([])
    result = asyncio.run(review_question(client, wording, [], 'Who approves emergency requests?'))
    assert result['verdict'] == 'reject' and result['method'] == 'exact_unknown_repeat'
    assert client.calls == []


def test_unknown_repeat_guard_still_allows_a_source_finding_question():
    from services.sme_interviewer.conversation import review_question

    client = Client([{'verdict': 'pass', 'reason': 'Seeks a possible source, not the unknown answer.'}])
    result = asyncio.run(review_question(client, 'I do not know who approves emergency requests.', [], 'Who could help us find out?'))
    assert result['verdict'] == 'pass' and len(client.calls) == 1


@pytest.mark.parametrize('account,question', [
    ('I waited for Finance approval.', 'What happened after Finance approval was granted?'),
    ('I waited for Finance approval.', 'Did you receive Finance approval before proceeding?'),
    ('Finance confirmed that the bank details matched; this was not permission to activate.', 'Who approved supplier activation?'),
    ('I asked the buyer for a renewed certificate.', 'Did the order proceed once the buyer provided the certificate?'),
    ('Finance had not approved the supplier.', 'Who approved the supplier?'),
    ('The supplier stays on hold until Finance has approved it.', 'What happened after Finance approved it?'),
])
def test_completed_event_cannot_be_inferred_from_waiting_conditions_or_matching(account, question):
    from services.sme_interviewer.conversation import unconfirmed_past_event

    assert unconfirmed_past_event(question, [account])


def test_completion_guard_allows_checking_occurrence_and_following_an_explicit_event():
    from services.sme_interviewer.conversation import unconfirmed_past_event

    assert unconfirmed_past_event('Did Finance approve the supplier?', ['I waited for approval.']) is None
    assert unconfirmed_past_event('What happened after Finance approved it?', ['Finance approved it before activation.']) is None
    assert unconfirmed_past_event('What would happen after Operations approved it?', ['We could ask Operations.']) is None


def test_neutral_supplier_outcome_check_does_not_wait_for_review_inference():
    from services.sme_interviewer.conversation import review_question

    client = Client([])
    result = asyncio.run(review_question(
        client,
        "Finance confirmed the payment details matched; that was not permission to activate the supplier.",
        [],
        "Did the supplier activation actually happen?",
    ))
    assert result["verdict"] == "pass" and result["method"] == "neutral_outcome_occurrence"
    assert client.calls == []
