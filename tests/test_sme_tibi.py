"""Tibi turn pipeline: routing, grounding, streaming and speculation (independent review 2)."""
import asyncio
import json
from pathlib import Path

import pytest

from services.sme_interviewer import tibi as tibi_module
from services.sme_interviewer.tibi import CONVERSATION, EVIDENCE, Evidence, EvidenceChanged, Tibi, cited, sentences

RECORDS = {r['id']: {**r, 'eligible': True, 'sha256': r['id'] * 4, 'source_id': 's-' + r['id'], 'references': [],
                     'audience': 'internal_rehearsal'}
           for r in json.loads((Path(__file__).parents[1] / 'services/opsatlas_sales/corpus/product.json').read_text())}


class FakeEvidence(Evidence):
    def __init__(self, ranking=None, variants=(), records=RECORDS):
        super().__init__('fake', 'http://core')
        self.records = dict(records)
        self.variants = list(variants)
        self.digest = 'd1'
        self.live_digest = 'd1'
        self.ranking = ranking or {}
        self.searches = []

    async def search(self, text):
        self.searches.append(text)
        results = self.ranking.get(text, [])
        return {'digest': self.digest, 'mode': 'hybrid', 'results': results}

    async def current(self):
        return self.live_digest

    async def refresh(self, digest=None):
        pass


def hit(record_id, similarity, relevant=True):
    return {'id': record_id, 'similarity': similarity, 'relevant': relevant, 'score': similarity, 'lexical': 1.0}


def make(replies, ranking=None, variants=(), history=None):
    t = Tibi(history or [], 'fake', 'http://core')
    t.evidence = FakeEvidence(ranking, variants)
    calls = []

    async def stream(system, user, history=()):
        calls.append((system, json.loads(user)))
        for piece in replies.get(system, ['OK\n', 'Fine.']):
            await asyncio.sleep(0)
            yield piece

    t._stream = stream
    t.calls = calls
    return t


async def run(t, text):
    turn = t.begin(text)
    segments = []
    while (segment := await turn.next()) is not None:
        segments.append(segment)
    await turn.task
    return segments, turn.result


def test_sentence_splitting_and_citation():
    ready, rest = sentences('Hello there. How are you')
    assert ready == ['Hello there.'] and rest == 'How are you'
    assert sentences('One. Two!', final=True)[0] == ['One.', 'Two!']
    assert [r['id'] for r in cited('It uses approved document retrieval with structured knowledge.',
                                   [RECORDS['process'], RECORDS['overview']])] == ['overview']


def test_small_talk_streams_sentences_without_evidence_and_commits_only_on_request():
    t = make({CONVERSATION: ['OK', '\nI am ready to listen. ', 'How has your day ', 'been?']})
    segments, result = asyncio.run(run(t, 'Hello, how are you?'))
    assert [s.text for s in segments] == ['I am ready to listen.', 'How has your day been?']
    assert result['route'] == 'conversation' and result['evidence'] == [] and not t.history
    t.commit('Hello, how are you?', result['reply'], result['route'])
    assert t.history[-1]['content'] == result['reply']


def test_definition_is_general_knowledge_not_product_evidence():
    t = make({CONVERSATION: ['OK - An ontology names kinds of things and how they relate.']},
             {'What is an ontology?': [hit('retrieval', 0.60)]})
    _, result = asyncio.run(run(t, 'What is an ontology?'))
    assert result['route'] == 'general' and result['grounding'] == 'general_model_knowledge'


@pytest.mark.parametrize('question', ['How much would it cost us per year?', 'Is the platform secure enough for a bank?',
                                      'What is Atlas really?', 'Who are your customers?'])
def test_review_probes_route_to_evidence_without_naming_opsatlas(question):
    t = make({})
    route = asyncio.run(t.route(question))
    assert route.kind == 'product', route.reasons


def test_capability_question_and_uncertain_similarity_default_to_evidence():
    t = make({}, {'Can it draw process diagrams?': [hit('process', 0.635)],
                  'Something vaguely about approved knowledge': [hit('governance', 0.59)],
                  'Tell me a joke.': [hit('tiberius', 0.36)]})
    assert asyncio.run(t.route('Can it draw process diagrams?')).kind == 'product'
    assert asyncio.run(t.route('Something vaguely about approved knowledge')).kind == 'product'
    assert asyncio.run(t.route('Tell me a joke.')).kind == 'conversation'


def test_greeting_by_name_is_conversation_and_generic_definition_stays_general():
    t = make({}, {'Good morning Tibi!': [hit('tiberius', 0.557)], 'What is an ontology?': [hit('retrieval', 0.642)],
                  'Tell me about Tibi.': [hit('tiberius', 0.572)], 'What does it do?': [hit('overview', 0.5)]})
    assert asyncio.run(t.route('Good morning Tibi!')).kind == 'conversation'
    assert asyncio.run(t.route('What is an ontology?')).kind == 'general'
    assert asyncio.run(t.route('Tell me about Tibi.')).kind == 'product'
    assert asyncio.run(t.route('What does it do?')).kind == 'product'


def test_follow_up_to_a_product_answer_stays_on_evidence():
    t = make({}, {'Why is that?': [hit('limitations', 0.40)]})
    t.last_route = 'product'
    assert asyncio.run(t.route('Why is that?')).kind == 'product'
    t.last_route = 'conversation'
    assert asyncio.run(t.route('Why is that?')).kind == 'conversation'


def test_conversational_product_claim_is_never_spoken_and_reroutes_to_evidence():
    t = make({CONVERSATION: ['OK\n', 'OpsAtlas costs about £40k a year. ', 'Anything else?'],
              EVIDENCE: ["The records don't establish pricing yet, so I can't give a figure."]},
             {'What do you reckon?': [hit('commercial', 0.40, relevant=False)]})
    segments, result = asyncio.run(run(t, 'What do you reckon?'))
    spoken = ' '.join(s.text for s in segments)
    assert '40k' not in spoken and result['route'] == 'product'
    assert 'reply made a product claim' in result['route_reasons']


def test_conversation_model_product_tag_reroutes():
    t = make({CONVERSATION: ['PRODUCT'], EVIDENCE: ['OpsAtlas combines approved document retrieval with structured knowledge.']},
             {'Go on then': [hit('overview', 0.40, relevant=False)]})
    _, result = asyncio.run(run(t, 'Go on then'))
    assert result['route'] == 'product' and result['grounding'] == 'grounded_synthesis'


def test_invented_price_is_blocked_and_approved_record_wording_is_spoken_instead():
    q = 'How much would it cost us per year?'
    t = make({EVIDENCE: ["It's normally 500 pounds per seat per month."]}, {q: [hit('commercial', 0.42)]})
    segments, result = asyncio.run(run(t, q))
    spoken = ' '.join(s.text for s in segments)
    assert '500' not in spoken and RECORDS['commercial']['text'] in spoken
    assert result['grounding'] == 'approved_fallback' and result['blocked'][0]['reasons']


def test_negated_capability_is_blocked_even_when_a_record_is_cited():
    q = 'Does it support single sign-on?'
    t = make({EVIDENCE: ['OpsAtlas supports enterprise multi-user roles today. ', 'It is simple to set up.']},
             {q: [hit('limitations', 0.54)]})
    segments, result = asyncio.run(run(t, q))
    assert 'multi-user roles today' not in ' '.join(s.text for s in segments)
    assert result['grounding'] == 'approved_fallback'


def test_supported_answer_streams_per_sentence_with_citations():
    q = 'What is OpsAtlas used for?'
    t = make({EVIDENCE: ['OpsAtlas combines approved document retrieval with structured knowledge. ',
                         'It gives cited answers, process intelligence and governance workflows.']},
             {q: [hit('overview', 0.86), hit('process', 0.76)]})
    segments, result = asyncio.run(run(t, q))
    assert [s.kind for s in segments] == ['answer', 'answer']
    # Citations follow the wording: both sentences draw on overview; "process intelligence" also on process.
    assert result['grounding'] == 'grounded_synthesis' and [e['id'] for e in result['evidence']][0] == 'overview'
    assert result['background_check'] and 'first_segment' in result['marks']


def test_experimental_record_qualification_is_spoken_when_the_answer_drops_it():
    q = 'Tell me about Tibi.'
    t = make({EVIDENCE: ['Tibi is the local voice companion that supports explicit conversation with product evidence.']},
             {q: [hit('tiberius', 0.70)]})
    segments, _ = asyncio.run(run(t, q))
    assert segments[0].kind == 'qualifier' and segments[0].text == 'That part is still experimental.'


def test_open_question_uses_approved_spoken_wording_with_its_audio_key():
    variant = {'id': 'v1', 'record_id': 'overview', 'text': 'OpsAtlas brings approved company knowledge together.',
               'text_sha256': 'a' * 64, 'usable': True}
    q = 'What is OpsAtlas?'
    t = make({}, {q: [hit('overview', 0.86), hit('process', 0.76)]}, [variant])
    segments, result = asyncio.run(run(t, q))
    assert [(s.kind, s.audio_key) for s in segments] == [('approved', 'a' * 64)]
    assert result['grounding'] == 'approved_spoken' and not t.calls


def test_evidence_change_before_speech_fails_closed():
    q = 'What is OpsAtlas used for?'
    t = make({EVIDENCE: ['OpsAtlas combines approved document retrieval with structured knowledge.']},
             {q: [hit('overview', 0.86)]})
    t.evidence.live_digest = 'changed'
    with pytest.raises(EvidenceChanged):
        asyncio.run(run(t, q))


def test_unanchored_conflict_is_not_spoken_and_anchored_conflict_is():
    t = make({CONVERSATION: ['CONFLICT | you said it was blue | now it is red\n', 'Which colour is it?']},
             history=[{'role': 'user', 'content': 'The van is blue.'}, {'role': 'assistant', 'content': 'Noted.'}])
    segments, result = asyncio.run(run(t, 'Actually the van is red.'))
    assert result['conversation_issue'] == 'unanchored' and 'misunderstood' in segments[0].text
    t = make({CONVERSATION: ['CONFLICT | The van is blue. | the van is red\n', 'Which colour is it now?']},
             history=[{'role': 'user', 'content': 'The van is blue.'}, {'role': 'assistant', 'content': 'Noted.'}])
    segments, result = asyncio.run(run(t, 'Actually the van is red.'))
    assert result['conversation_issue'] == 'possible_conflict' and segments[0].text == 'Which colour is it now?'


def test_workspace_help_and_missing_evidence_are_fixed_replies():
    t = make({})
    segments, result = asyncio.run(run(t, 'How would I add a pricing quote to the records so it is guaranteed?'))
    assert result['grounding'] == 'workspace_guidance' and 'customer guarantee' in segments[0].text
    t = make({}, {'Is it secure?': []})
    t.evidence.records = {}
    segments, result = asyncio.run(run(t, 'Is it secure?'))
    assert result['grounding'] == 'no_approved_evidence'


def test_speculative_turn_has_no_side_effects_and_can_be_cancelled():
    t = make({})
    release = asyncio.Event()

    async def slow(system, user, history=()):
        yield 'OK\n'
        await release.wait()
        yield 'Never spoken.'

    t._stream = slow

    async def go():
        turn = t.begin('I was thinking about', speculative=True)
        await asyncio.sleep(0.01)
        turn.cancel()
        await asyncio.gather(turn.task, return_exceptions=True)
        return turn
    turn = asyncio.run(go())
    assert turn.task.cancelled() and not turn.spoken and not t.history and not t.archive


def test_model_uses_the_measured_fast_default(monkeypatch):
    assert tibi_module.MODEL == 'qwen2.5:7b-instruct' and tibi_module.KEEP_ALIVE == '30m'
    assert tibi_module.REVIEW_MODEL != tibi_module.MODEL  # a background check never queues ahead of a reply


def test_prewarm_caches_the_evidence_prompt_for_product_partials_only(monkeypatch):
    import httpx

    sent = []
    original = httpx.AsyncClient

    def client(**kwargs):
        def handle(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200, json={'message': {'content': ''}, 'done': True})
        return original(**{**kwargs, 'transport': httpx.MockTransport(handle)})

    monkeypatch.setattr(httpx, 'AsyncClient', client)
    t = make({}, {'Does it support single sign': [hit('limitations', 0.53)], 'I was just saying': [hit('tiberius', 0.3)]})
    assert asyncio.run(t.prewarm('Does it support single sign')) == ['limitations']
    assert asyncio.run(t.prewarm('I was just saying')) is None
    assert len(sent) == 1 and sent[0]['options']['num_predict'] == 1
    body = json.loads(sent[0]['messages'][-1]['content'])
    assert list(body) == ['approved_records', 'question']  # records first: the cached prefix excludes the question
