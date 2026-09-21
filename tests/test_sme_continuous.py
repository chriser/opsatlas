"""State/ledger invariants for continuous listening and recap confirmation."""

import asyncio
import base64
import copy
import uuid

import pytest

from services.sme_interviewer.continuous import Conversation
from services.sme_interviewer.conversation_store import ConversationStore, hearing_context
from services.sme_interviewer.evidence import FixtureEvidence
from services.sme_interviewer.interview import Interviews
from services.sme_interviewer.ledger import Conflict


class Engine:
    def __init__(self, probability=0, text="The buyer requested a supplier."):
        self.probability = probability
        self.text = text
        self.closed = False
        self.calls = 0

    async def start(self):
        pass

    async def infer(self, pcm):
        self.calls += 1
        return {"probability": self.probability, "text": self.text, "no_speech": 0.01}

    async def stream(self, text):
        yield {"rate": 24000, "pcm": base64.b64encode(bytes(480)).decode()}

    async def close(self):
        self.closed = True


class Planner:
    async def plan(self, context):
        return {"question": "story", "observations": [], "mode": "guided"}


async def router(*args):
    return {"category": "responsive", "kind": "reported_practice", "command": "none", "clarification": None}


def setup(tmp_path):
    interviews = Interviews(tmp_path)
    session = interviews.store.create(
        FixtureEvidence().snapshot(), {"region": "unknown", "variant": "unknown", "date": ""}, str(uuid.uuid4())
    )
    events = []

    async def send(event):
        events.append(copy.deepcopy(event))
        if event["type"] == "audio_chunk" and getattr(c, "auto_ack", True):
            c.audio_ack({"generation_id": event["generation_id"], "index": event["index"]})

    asr, vad, speaker = Engine(), Engine(), Engine()
    c = Conversation(tmp_path, interviews, session, send, asr, vad, speaker, router)
    c.planner = Planner()
    return c, events


def test_provisional_hearing_never_becomes_confirmed_until_atomic_recap(tmp_path):
    c, events = setup(tmp_path)
    store = ConversationStore(c.interviews.store)
    s = store.begin(c.session)
    s = store.heard(s, "The limit was £50,000.", "reported_practice", "turn-1")
    context = hearing_context(s)
    assert context["segments"][0]["state"] == "confirmed"
    assert c.interviews.store.get(s["id"])["segments"][0]["state"] == "provisional"
    with pytest.raises(Conflict):
        c.interviews.store.finish(s["id"], s["revision"], True)
    rows = [{"id": "turn-1", "revision": 1, "text": "The limit was £15,000, not £50,000.", "kind": "reported_practice"}]
    confirmed = store.confirm_recap(s, rows)
    assert confirmed["segments"][0]["revision"] == 2
    assert confirmed["segments"][0]["state"] == "confirmed"
    assert confirmed["analysis"] is None and confirmed["review"] is None
    history = c.interviews.store.events(s["id"])[-1]["payload"]
    assert history["previous"][0]["text"] == "The limit was £50,000."
    finished = c.interviews.store.finish(s["id"], confirmed["revision"], True)
    assert "£15,000" in str(finished["review"])


def test_recap_rejects_stale_or_partial_confirmation(tmp_path):
    c, _ = setup(tmp_path)
    store = ConversationStore(c.interviews.store)
    s = store.heard(store.begin(c.session), "An answer.", "uncertain", "turn-1")
    with pytest.raises(ValueError):
        store.confirm_recap(s, [])
    rows = [{"id": "turn-1", "revision": 0, "text": "Changed", "kind": "uncertain"}]
    with pytest.raises(Conflict):
        store.confirm_recap(s, rows)
    assert c.interviews.store.get(s["id"]) == s


def test_silence_short_noise_and_missing_frames_cannot_advance_turns(tmp_path):
    async def run():
        c, events = setup(tmp_path)
        await c.start()
        for i in range(10):
            await c.feed({"sequence": i, "pcm": base64.b64encode(bytes(1024)).decode()})
        c.vad.probability = 0.9
        for i in range(10, 14):
            await c.feed({"sequence": i, "pcm": base64.b64encode(bytes(1024)).decode()})
        assert not any(e["type"] == "speech_start" for e in events)
        await c.feed({"sequence": 20, "pcm": base64.b64encode(bytes(1024)).decode()})
        assert c.paused and c.session["segments"] == []
        await c.close()

    asyncio.run(run())


def test_endpoint_and_barge_in_cancel_pending_reply(tmp_path):
    async def run():
        c, events = setup(tmp_path)
        await c.start()
        await asyncio.sleep(0)
        blocked = asyncio.Event()

        async def slow(*args):
            await blocked.wait()
            return await router()

        c.interpret = slow
        c.vad.probability = 0.9
        pcm = base64.b64encode(bytes(1024)).decode()
        for i in range(8):
            await c.feed({"sequence": i, "pcm": pcm})
        c.vad.probability = 0
        for i in range(8, 44):
            await c.feed({"sequence": i, "pcm": pcm})
        await asyncio.sleep(0)
        old = c.reply
        assert any(e["type"] == "endpoint" for e in events)
        c.vad.probability = 0.9
        for i in range(44, 50):
            await c.feed({"sequence": i, "pcm": pcm})
        await asyncio.sleep(0)
        await asyncio.gather(old, return_exceptions=True)
        assert old.cancelled()
        assert c.session["segments"] == []
        blocked.set()
        await c.close()
        assert c.asr.closed and c.vad.closed and c.speaker.closed

    asyncio.run(run())


def test_relevant_turn_saved_as_provisional_without_a_confirmation_form(tmp_path):
    async def run():
        c, events = setup(tmp_path)
        await c.start()
        await asyncio.sleep(0)
        c.interrupt()
        c.turn = "live-turn"
        await c.complete(bytes(4000), c.generation)
        assert c.session["segments"][0]["state"] == "provisional"
        assert any(e["type"] == "audio_chunk" for e in events)
        await c.show_recap()
        assert c.paused and c.recap
        s = c.session["segments"][0]
        await c.confirm(
            {"expected_revision": c.session["revision"], "rows": [{"id": s["id"], "revision": 1, "text": s["text"], "kind": s["kind"]}]}
        )
        assert c.session["status"] == "finished"
        await c.close()

    asyncio.run(run())


def test_unrelated_answer_is_not_saved_as_process_evidence(tmp_path):
    async def run():
        c, events = setup(tmp_path)

        async def unrelated(*args):
            return {"kind": "reported_practice", "command": "none", "clarification": "How does that relate to the question?"}

        c.interpret = unrelated
        await c.start()
        await asyncio.sleep(0)
        c.interrupt()
        c.turn = "unrelated"
        await c.complete(bytes(4000), c.generation)
        assert c.session["segments"] == []
        assert any(e["type"] == "clarification" for e in events)
        await c.close()

    asyncio.run(run())


def test_high_impact_confirmation_keeps_the_original_audio_provenance(tmp_path):
    async def run():
        c, events = setup(tmp_path)
        await c.start()
        await asyncio.sleep(0)
        c.interrupt()
        c.turn = "original-recording"
        c.asr.text = "The limit was £15,000, not £50,000."
        await c.complete(bytes(4000), c.generation)
        assert c.pending_check and not c.session["segments"]
        c.interrupt()
        c.turn = "confirmation-recording"
        c.asr.text = "Yes."
        await c.complete(bytes(4000), c.generation)
        segment = c.session["segments"][0]
        assert segment["audio_sequence"] == "original-recording"
        assert segment["text"] == "The limit was £15,000, not £50,000."
        assert segment["state"] == "provisional"
        await c.close()

    asyncio.run(run())


def test_playback_backpressure_and_duplicate_acknowledgement(tmp_path):
    async def run():
        c, events = setup(tmp_path)
        c.paused = False
        c.auto_ack = False
        task = asyncio.create_task(c.speak("First sentence. Second sentence. Third sentence."))
        await asyncio.sleep(0)
        chunks = [e for e in events if e["type"] == "audio_chunk"]
        assert len(chunks) == 2 and not task.done()
        ack = {"generation_id": str(c.generation), "index": chunks[0]["index"]}
        c.audio_ack(ack)
        c.audio_ack(ack)
        await task
        assert len([e for e in events if e["type"] == "audio_chunk"]) == 3
        assert len(c.audio_pending) == 2
        await c.close()

    asyncio.run(run())


def test_incomplete_thought_receives_more_silence_before_endpoint(tmp_path):
    async def run():
        c, events = setup(tmp_path)
        c.paused = False
        c.vad.probability = 0.9
        pcm = base64.b64encode(bytes(1024)).decode()
        for i in range(8):
            await c.feed({"sequence": i, "pcm": pcm})
        c.preview = {"text": "And then we", "complete": False, "result": None}
        c.vad.probability = 0
        for i in range(8, 44):
            await c.feed({"sequence": i, "pcm": pcm})
        assert not any(e["type"] == "endpoint" for e in events)
        await c.close()

    asyncio.run(run())


def test_interrupting_the_thinking_phase_retains_the_first_part(tmp_path):
    c, _ = setup(tmp_path)
    c.inflight_text = "The buyer sent a form."
    c.interrupt(continue_answer=True)
    assert c.continuation == ["The buyer sent a form."]
    c.interrupt()
    assert c.continuation == []


def test_recap_correction_invalidates_previous_draft_and_rejects_duplicates(tmp_path):
    c, _ = setup(tmp_path)
    store = ConversationStore(c.interviews.store)
    s = store.heard(store.begin(c.session), "A request arrived.", "reported_practice", "turn-1")
    s = store.heard(s, "Finance checked it.", "reported_practice", "turn-2")
    rows = [{"id": "turn-1", "revision": 1, "text": "Corrected", "kind": "reported_practice"}] * 2
    with pytest.raises(ValueError):
        store.confirm_recap(s, rows)
    assert all(x["state"] == "provisional" for x in c.interviews.store.get(s["id"])["segments"])


def test_interrupted_final_text_is_durable_but_cannot_become_a_claim(tmp_path):
    async def run():
        c, events = setup(tmp_path)
        blocked = asyncio.Event()

        async def slow(*args):
            await blocked.wait()
            return await router()

        await c.start()
        await asyncio.sleep(0)
        c.interrupt()
        c.turn = "durable"
        c.interpret = slow
        task = asyncio.create_task(c.complete(bytes(4000), c.generation))
        await asyncio.sleep(0)
        await c.pause("Paused by participant")
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        saved = c.interviews.store.get(c.session["id"])
        assert saved["hearing_attempts"][0]["text"] == c.asr.text
        assert saved["segments"] == []
        await c.close()

    asyncio.run(run())


def test_audio_turn_cannot_be_added_twice(tmp_path):
    c, _ = setup(tmp_path)
    store = ConversationStore(c.interviews.store)
    s = store.heard(store.begin(c.session), 'An answer.', 'uncertain', 'same-turn')
    with pytest.raises(Conflict):
        store.heard(s, 'An answer.', 'uncertain', 'same-turn')
    assert len(c.interviews.store.get(s['id'])['segments']) == 1


def test_websocket_auth_origin_single_owner_and_cleanup(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    from services.sme_interviewer import continuous

    c, _ = setup(tmp_path)
    closed = []

    class Stub:
        def __init__(self, runtime, interviews, saved, send, listener_only=False):
            self.send = send
        async def start(self):
            await self.send({'type': 'ready'})
        async def close(self):
            closed.append(True)

    monkeypatch.setattr(continuous, 'Conversation', Stub)
    app = FastAPI()
    continuous.attach_conversation(app, tmp_path, 'test-secret', c.interviews)
    path = '/api/conversation/' + c.session['id']
    headers = {'host': '127.0.0.1:8767', 'origin': 'http://127.0.0.1:8767'}
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(path, headers={**headers, 'origin': 'https://outside.example'}):
                pass
        with client.websocket_connect(path, headers=headers) as bad:
            bad.send_json({'token': 'wrong'})
            with pytest.raises(WebSocketDisconnect):
                bad.receive_json()
        with client.websocket_connect(path, headers=headers) as first:
            first.send_json({'token': 'test-secret'})
            assert first.receive_json()['type'] == 'ready'
            with client.websocket_connect(path, headers=headers) as second:
                second.send_json({'token': 'test-secret'})
                with pytest.raises(WebSocketDisconnect):
                    second.receive_json()
        with client.websocket_connect(path, headers=headers) as reopened:
            reopened.send_json({'token': 'test-secret'})
            assert reopened.receive_json()['type'] == 'ready'
    assert len(closed) == 2


def test_prepared_audio_is_silent_until_authorised_and_bounded():
    from services.sme_interviewer.speech import PreparedSpeech

    async def run():
        worker = Engine()
        voice = PreparedSpeech(worker, 'A checked question?')
        await voice.task
        assert voice.done and len(voice.chunks) == 1
        assert [c async for c in voice.stream()] == voice.chunks

        class TooLarge(Engine):
            async def stream(self, text):
                yield {'pcm': 'x' * 4_000_001, 'rate': 24000}

        bad = PreparedSpeech(TooLarge(), 'A question?')
        await bad.task
        with pytest.raises(ValueError):
            _ = [c async for c in bad.stream()]
        assert bad.chunks == []
    asyncio.run(run())


def test_preparation_is_cancelled_on_new_speech(tmp_path):
    from services.sme_interviewer.speech import PreparedSpeech

    async def run():
        c, events = setup(tmp_path)
        blocked = asyncio.Event()
        class Slow(Engine):
            async def stream(self, text):
                await blocked.wait()
                yield {'pcm': 'AAA=', 'rate': 24000}
        voice = PreparedSpeech(Slow(), 'Old question?')
        c.prepared_voice = voice
        await asyncio.sleep(0)
        c.interrupt()
        await voice.task
        assert isinstance(voice.error, asyncio.CancelledError)
        assert c.prepared_voice is None
        assert not events
    asyncio.run(run())


def test_stable_numeric_hearing_does_not_force_per_turn_confirmation(tmp_path):
    async def run():
        c, events = setup(tmp_path)
        await c.start()
        await asyncio.sleep(0)
        c.interrupt()
        c.turn = 'stable-number'
        c.asr.text = 'The limit is £15,000, not £50,000.'
        c.last_heard_partial = c.asr.text
        await c.complete(bytes(4000), c.generation)
        assert len(c.session['segments']) == 1
        assert c.session['segments'][0]['state'] == 'provisional'
        assert not any(e['type'] == 'wording_check' for e in events)
        await c.close()
    asyncio.run(run())


def test_final_recognition_reuses_only_complete_matching_audio(tmp_path):
    async def run():
        c, _ = setup(tmp_path)
        await c.start()
        await asyncio.sleep(0)
        c.interrupt()
        c.turn = 'recognition-reuse'
        c.last_voice = 10000
        c.last_recognition = {'generation': c.generation, 'voice': 10000, 'end': 14000,
                              'result': {'text': 'The buyer sent the request.', 'no_speech': 0.01}}
        await c.complete(bytes(4000), c.generation)
        assert c.asr.calls == 0
        assert c.session['segments'][0]['text'] == 'The buyer sent the request.'
        await c.close()
    asyncio.run(run())


def test_new_audio_after_partial_requires_fresh_final_recognition(tmp_path):
    async def run():
        c, _ = setup(tmp_path)
        await c.start()
        await asyncio.sleep(0)
        c.interrupt()
        c.turn = 'recognition-fresh'
        c.last_voice = 15000
        c.last_recognition = {'generation': c.generation, 'voice': 10000, 'end': 14000,
                              'result': {'text': 'An incomplete earlier sentence.', 'no_speech': 0.01}}
        await c.complete(bytes(4000), c.generation)
        assert c.asr.calls == 1
        assert c.session['segments'][0]['text'] == c.asr.text
        await c.close()
    asyncio.run(run())


def test_background_question_review_is_recorded_without_confirming_words(tmp_path):
    c, _ = setup(tmp_path)
    store = ConversationStore(c.interviews.store)
    s = store.heard(store.begin(c.session), 'The request arrived.', 'reported_practice', 'a')
    context = hearing_context(s)
    s = store.question(s, {'question': 'story'}, context)
    q = s['current_question']['id']
    s = store.audit_question(s, q, {'verdict': 'reject', 'reason': 'Premise needs checking.'})
    assert s['current_question']['semantic_review']['verdict'] == 'reject'
    assert s['segments'][0]['state'] == 'provisional'
    assert c.interviews.store.events(s['id'])[-1]['type'] == 'conversation_question_reviewed'


def test_speech_cancellation_drains_reply_and_preserves_warm_worker(tmp_path):
    from types import SimpleNamespace

    from services.sme_interviewer.speech import SpeechWorker

    async def run():
        worker = SpeechWorker('kokoro', tmp_path)
        replies = asyncio.Queue()
        writes = []
        closed = []
        async def nothing():
            pass
        async def close():
            closed.append(True)
        worker.start = nothing
        worker.close = close
        worker._read = replies.get
        worker.process = SimpleNamespace(stdin=SimpleNamespace(write=writes.append, drain=nothing))
        async def consume():
            return [c async for c in worker.stream('A checked question?')]
        pending = asyncio.create_task(consume())
        await asyncio.sleep(0)
        pending.cancel()
        await replies.put({'done': True})
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert not closed
        await replies.put({'chunk': 0, 'pcm': 'AAA=', 'rate': 24000})
        await replies.put({'done': True})
        result = await consume()
        assert len(result) == 1
        assert len(writes) == 2
    asyncio.run(run())


def test_live_partial_does_not_queue_planning_until_a_speech_pause(tmp_path):
    async def run():
        c, _ = setup(tmp_path)
        c.paused = False
        calls = []
        async def prepare(*args):
            calls.append(args)
        c.prepare = prepare
        await c.transcribe_partial(b'', 0, end_sample=16000, voiced_sample=15500)
        assert c.last_heard_partial == c.asr.text
        assert c.speculation is None
        await c.transcribe_partial(b'', 0, end_sample=20000, voiced_sample=16000)
        await c.speculation
        assert len(calls) == 1
    asyncio.run(run())


def test_rejected_question_keeps_valid_answer_without_continuing_it_next_turn(tmp_path):
    async def run():
        c, events = setup(tmp_path)
        await c.start()
        async def prepare(text, *args):
            return {'route': await router(), 'context': hearing_context(c.session, text, 'reported_practice', c.turn),
                    'plan': None, 'question_error': 'Rejected after bounded repair'}
        c.prepare = prepare
        await c.complete(b'', c.generation)
        assert c.session['segments'][-1]['text'] == c.asr.text
        assert c.inflight_text is None
        assert any("kept your wording" in e.get('text', '') for e in events)
        await c.close()
    asyncio.run(run())


def test_explicit_recap_is_not_joined_to_an_unfinished_answer(tmp_path):
    async def run():
        c, events = setup(tmp_path)
        await c.start()
        c.continuation = ['An unfinished answer']
        c.asr.text = 'Let us review the recap.'
        async def prepare(text, *args):
            assert text == c.asr.text
            return {'route': {**await router(), 'command': 'recap'}, 'context': {}, 'plan': None}
        c.prepare = prepare
        await c.complete(b'', c.generation)
        assert any(e['type'] == 'recap' for e in events)
        await c.close()
    asyncio.run(run())


def test_recap_waits_for_cancelled_reply_to_register_its_review(tmp_path):
    async def run():
        c, events = setup(tmp_path)
        speaking = asyncio.Event()
        release_review = asyncio.Event()

        async def review():
            await release_review.wait()

        async def reply():
            try:
                speaking.set()
                await asyncio.Event().wait()
            finally:
                task = c.task(review())
                c.reviews.add(task)
                task.add_done_callback(c.reviews.discard)

        c.reply = c.task(reply())
        await speaking.wait()
        await c.show_recap()
        assert len(c.reviews) == 1
        assert events[-1]['type'] == 'recap'
        release_review.set()
        await asyncio.gather(*c.reviews)
        await c.close()

    asyncio.run(run())


def test_committed_social_reply_finishes_before_question_and_interruption_cancels_it(tmp_path):
    async def run():
        c, events = setup(tmp_path)
        c.paused = False
        c.auto_ack = False
        import time
        wording = "Of course. Take your time."
        c.social_audio[wording] = [{"rate": 24000, "pcm": base64.b64encode(bytes(480)).decode()}]
        action = c.listener.decide("Let me think", c.generation, time.monotonic())
        cue = asyncio.create_task(c.social_response(action))
        await asyncio.sleep(0)
        question = asyncio.create_task(c.speak('What happened next?'))
        await asyncio.sleep(0)
        assert [e['text'] for e in events if e['type'] == 'speech'] == [wording]
        chunk = next(e for e in events if e['type'] == 'audio_chunk')
        c.audio_ack({'generation_id': chunk['generation_id'], 'index': chunk['index']})
        await cue
        await question
        assert [e['text'] for e in events if e['type'] == 'speech'][-1] == 'What happened next?'
        c.reply = asyncio.create_task(c.social_response(action))
        await asyncio.sleep(0)
        reply = c.reply
        c.interrupt()
        await asyncio.gather(reply, return_exceptions=True)
        assert reply.cancelled()
        await c.close()
    asyncio.run(run())


def test_manual_finish_does_not_turn_silence_into_an_answer(tmp_path):
    async def run():
        c, events = setup(tmp_path)
        c.paused = False
        await c.finish_answer()
        assert not events and c.reply is None
        await c.close()
    asyncio.run(run())


def test_deferred_review_uses_no_model_during_listening_then_drains_at_recap(tmp_path):
    async def run():
        c, events = setup(tmp_path)
        c.defer_reviews = True
        calls = []

        async def review(*args):
            calls.append(args)

        c.review_in_background = review
        c.queue_review({'id': 'q', 'text': 'Which record?'}, {'segments': []})
        await asyncio.sleep(0)
        assert not calls and not c.reviews
        c.start_review_drain()
        await c.review_drain
        assert len(calls) == 1 and not c.deferred_reviews
        assert [e['type'] for e in events] == ['review_pending', 'review_complete']
        await c.close()
    asyncio.run(run())


@pytest.mark.parametrize('text', ['Can I get a recap please?', 'Could you give me a recap?', 'Recap please.'])
def test_natural_recap_bypasses_failed_model_and_pending_wording_check(tmp_path, text):
    async def run():
        c, events = setup(tmp_path)
        await c.start()
        c.continuation = ['An unfinished account']
        c.pending_check = ('A number to confirm', 'earlier-turn')
        c.asr.text = text
        async def fail(*args):
            raise AssertionError('A recap must never call the planner')
        c.prepare = fail
        await c.complete(b'', c.generation)
        assert c.recap and c.paused and c.pending_check is None
        assert any(e['type'] == 'recap' for e in events)
        assert not any(e['type'] == 'error' for e in events)
        assert not c.session['segments']
        await c.close()
    asyncio.run(run())


@pytest.mark.parametrize("failure", ["timeout", "malformed_model_output"])
def test_reasoning_failure_is_not_reported_as_unclear_participant_speech(tmp_path, failure):
    import httpx
    async def run():
        c, events = setup(tmp_path)
        await c.start()
        async def failed(*args):
            if failure == 'timeout':
                raise httpx.ReadTimeout('local model unavailable')
            raise ValueError('Invalid model output')
        c.prepare = failed
        await c.complete(b'', c.generation)
        assert c.session['hearing_attempts'][-1]['text'] == c.asr.text
        speech = [e['text'] for e in events if e['type'] == 'speech'][-1]
        assert 'reasoning engine' in speech and 'clarify' not in speech and 'say it again' not in speech
        await c.close()
    asyncio.run(run())


def test_social_requests_bypass_failed_reasoner_and_preserve_unfinished_answer(tmp_path):
    async def run():
        c, events = setup(tmp_path)
        await c.start()
        await c.reply
        events.clear()
        async def unavailable(*args):
            raise AssertionError('Social request must not call the planner')
        c.interpret = unavailable
        c.continuation = ['The buyer sent the request.']
        c.pending_check = ('The amount was £15,000.', 'earlier')
        c.asr.text = 'Give me a second please.'
        await c.complete(b'', c.generation)
        assert not c.session['segments']
        assert not c.session.get('hearing_attempts')
        assert c.continuation == ['The buyer sent the request.']
        assert c.pending_check == ('The amount was £15,000.', 'earlier')
        assert any(e['type'] == 'audio_chunk' for e in events)
        assert any(e['type'] == 'speech' and e['cue'] for e in events)
        c.asr.text = 'Please let me think in silence.'
        await c.complete(b'', c.generation)
        assert c.session['listener']['quiet']
        restored = Conversation(tmp_path, c.interviews, c.session, c.send, Engine(), Engine(), Engine(), router)
        assert restored.listener.quiet
        await c.close()
    asyncio.run(run())


def test_expired_social_action_waiting_for_audio_floor_is_dropped(tmp_path):
    async def run():
        import time
        c, events = setup(tmp_path)
        await c.start()
        await c.reply
        events.clear()
        action = c.listener.decide('Let me think', c.generation, time.monotonic() - 3)
        await c.social_response(action)
        assert not events
        action = c.listener.decide('Let me think', c.generation, time.monotonic())
        c.interrupt()
        await c.social_response(action)
        assert not events
        await c.close()
    asyncio.run(run())


def test_listener_practice_never_loads_or_calls_content_model(tmp_path):
    async def run():
        c, events = setup(tmp_path)
        c.listener_only = c.defer_reviews = True
        async def forbidden(*args):
            raise AssertionError('No content model in listener practice')
        c.warm_planner = c.planner.plan = c.interpret = forbidden
        await c.start()
        await c.reply
        assert c.session['listener_practice']
        c.asr.text = 'The supplier was activated.'
        await c.complete(b'', c.generation)
        assert any(e['type'] == 'listener_handoff' for e in events)
        assert not c.session['segments'] and not c.session.get('hearing_attempts')
        await c.pause('Pause')
        await c.resume()
        await c.close()
    asyncio.run(run())
