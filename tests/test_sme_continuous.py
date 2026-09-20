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
        def __init__(self, runtime, interviews, saved, send):
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
