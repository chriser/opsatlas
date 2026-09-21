"""Bounded single-headset conversation: PCM -> VAD -> resident ASR -> speculative questions -> PCM."""

import array
import asyncio
import base64
import binascii
import json
import logging
import os
import re
import secrets
import time
import uuid
from collections import deque
from contextlib import suppress

import anyio
import httpx
from fastapi import WebSocket, WebSocketDisconnect

from .conversation import review_question
from .conversation_store import ConversationStore, hearing_context
from .dialogue import LocalPlanner
from .endpointing import TurnBoundary
from .ledger import Conflict
from .resident import Resident
from .speech import PreparedSpeech, SpeechWorker
from .turn_interpreter import interpret
from .turn_planner import prepare_turn
from .voice_commands import command

OPENING = (
    "I'm your process interviewer. This is a fictional practice conversation, saved only on this Mac. "
    "You can interrupt me, say pause, or ask for the recap. We'll check the wording together at the end. "
    "Think of a supplier activation. What happened from the request to the outcome?"
)


def normal(text):
    return " ".join(text.split()).strip()


class Conversation:
    def __init__(self, runtime, interviews, session, send, recognizer=None, detector=None, speaker=None,
                 interpreter=interpret, endpoint=None):
        self.interviews, self.session, self.send = interviews, session, send
        self.store = ConversationStore(interviews.store)
        self.asr = recognizer or Resident(runtime, "asr", "ggml-small.en.bin")
        self.vad = detector or Resident(runtime, "vad")
        self.speaker = speaker or SpeechWorker(os.environ.get("SME_VOICE_BACKEND", "kokoro"), runtime)
        self.endpoint = endpoint
        self.smart_endpoint = endpoint is not None or os.environ.get("SME_SMART_ENDPOINT") == "1"
        self.boundary = TurnBoundary()
        self.endpoint_task = None
        self.speech_lock = asyncio.Lock()
        self.cue_task = None
        self.cue_used = False
        self.cue_pending = False
        self.patience_chunks = []
        self.interpret = interpreter
        self.planner = LocalPlanner()
        self.generation = 0
        self.turn = "opening"
        self.sequence = -1
        self.samples = 0
        self.ring = deque(maxlen=16)
        self.frames = []
        self.voiced = 0
        self.last_voice = 0
        self.utterance_start = 0
        self.partial_at = 0
        self.speech = False
        self.paused = True
        self.recap = False
        self.closed = False
        self.work = set()
        self.partial = self.speculation = self.reply = None
        self.preview = None
        self.last_heard_partial = None
        self.last_recognition = None
        self.prepared_voice = None
        self.reviews = set()
        self.deferred_reviews = []
        self.review_drain = None
        self.defer_reviews = os.environ.get("SME_DEFER_REVIEWS") == "1"
        self.pending_check = None
        self.inflight_text = None
        self.continuation = []
        self.started_at = time.monotonic()
        self.markers = {}
        self.playback_window = 8 if getattr(self.speaker, "engine", "") == "pocket" else 2
        self.audio_slots = asyncio.Semaphore(self.playback_window)
        self.audio_pending = set()
        self.audio_empty = asyncio.Event()
        self.audio_empty.set()
        self.audio_index = 0
        self.last_frame_at = time.monotonic()

    def task(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.work.add(task)

        def done(t):
            self.work.discard(t)
            if not t.cancelled():
                t.exception()  # All model errors are handled at their boundary; consume transport shutdown errors.

        task.add_done_callback(done)
        return task

    async def emit(self, event, **data):
        if not self.closed:
            await self.send(
                {
                    "type": event,
                    "session_id": self.session["id"],
                    "revision": self.session["revision"],
                    "turn_id": self.turn,
                    "generation_id": str(self.generation),
                    **data,
                }
            )

    async def start(self):
        await self.emit("state", state="warming", message="Preparing local listening and voice…")
        await asyncio.wait_for(asyncio.gather(self.asr.start(), self.vad.start(), self.speaker.start()), 45)
        if self.smart_endpoint and self.endpoint is None:
            from .experience.listener import Endpoint
            self.endpoint = await asyncio.to_thread(Endpoint)
        if self.smart_endpoint:
            async for chunk in self.speaker.stream("Take your time. There is no rush."):
                self.patience_chunks.append(chunk)
        if self.defer_reviews:
            await self.warm_planner()
        voice = "Pocket TTS · Charles" if getattr(self.speaker, "engine", "") == "pocket" else "Kokoro · Isabella"
        self.session = self.store.begin(self.session, voice=voice)
        self.paused = False
        self.last_frame_at = time.monotonic()
        await self.emit("snapshot", session=self.session)
        self.task(self.watchdog())
        if self.session["segments"]:
            await self.show_recap()
            return
        else:
            context = hearing_context(self.session)
            plan = await self.planner.plan(context)
            self.session = self.store.question(self.session, plan, context)
            self.reply = self.task(self.speak(OPENING))
        await self.emit("ready")

    async def warm_planner(self):
        from .planner_runtime import CONTEXT_TOKENS, KEEP_ALIVE, MODEL, scheduling_options

        await self.emit("state", state="warming", message="Warming the local conversation model before listening…")
        async with httpx.AsyncClient(base_url="http://127.0.0.1:11434", timeout=120, trust_env=False) as client:
            response = await client.post("/api/generate", json={"model": MODEL, "keep_alive": KEEP_ALIVE,
                                                               "prompt": "Say ready.", "think": False, "stream": False,
                                                               "options": {"num_ctx": CONTEXT_TOKENS, "num_predict": 1,
                                                                           **scheduling_options()}})
            response.raise_for_status()

    def queue_review(self, question, context):
        if self.defer_reviews:
            self.deferred_reviews.append((question["id"], question["text"], context))
        else:
            task = self.task(self.review_in_background(question["id"], question["text"], context))
            self.reviews.add(task)
            task.add_done_callback(self.reviews.discard)

    def start_review_drain(self):
        if not self.deferred_reviews or (self.review_drain and not self.review_drain.done()):
            return

        async def drain():
            await self.emit("review_pending", count=len(self.deferred_reviews))
            while self.deferred_reviews:
                await self.review_in_background(*self.deferred_reviews[0])
                self.deferred_reviews.pop(0)
            unavailable = sum((q.get("semantic_review") or {}).get("verdict") == "unavailable"
                              for q in self.session["questions"])
            await self.emit("review_complete", unavailable=unavailable)

        self.review_drain = self.task(drain())
        self.reviews.add(self.review_drain)
        self.review_drain.add_done_callback(self.reviews.discard)

    def interrupt(self, continue_answer=False):
        if continue_answer and self.inflight_text:
            self.continuation = [self.inflight_text]
        elif not continue_answer:
            self.continuation = []
        self.inflight_text = None
        self.cue_pending = False
        self.generation += 1
        if self.prepared_voice:
            self.prepared_voice.cancel()
            self.prepared_voice = None
        self.preview = None
        self.last_heard_partial = None
        self.last_recognition = None
        self.audio_slots = asyncio.Semaphore(self.playback_window)
        self.audio_pending.clear()
        self.audio_empty.set()
        for task in (self.reply, self.speculation, self.cue_task, self.endpoint_task):
            if task and task is not asyncio.current_task():
                task.cancel()
        self.reply = self.speculation = None

    async def watchdog(self):
        while not self.closed:
            await asyncio.sleep(1)
            if not self.paused and time.monotonic() - self.last_frame_at > 3:
                await self.pause("Audio stopped arriving. Your saved wording is safe. Check the microphone, then resume.")

    async def feed(self, data):
        if self.closed or self.paused:
            return
        seq = data.get("sequence")
        if type(seq) is not int or seq != self.sequence + 1:
            await self.pause("An audio gap was detected. Please resume and repeat the interrupted answer.")
            return
        try:
            raw = base64.b64decode(data["pcm"], validate=True)
            if len(raw) != 1024:
                raise ValueError("Wrong frame size")
            shorts = array.array("h", raw)
            floats = array.array("f", (v / 32768 for v in shorts)).tobytes()
        except (KeyError, ValueError, binascii.Error, TypeError):
            await self.pause("The microphone sent an invalid audio frame. Use the fallback interview or reconnect.")
            return
        self.sequence = seq
        self.last_frame_at = time.monotonic()
        self.samples += 512
        probability = (await self.vad.infer(floats))["probability"]
        self.ring.append(floats)
        if not self.speech:
            self.voiced = self.voiced + 1 if probability >= 0.6 else 0
            if self.voiced < 5:
                return
            self.interrupt(continue_answer=True)
            self.turn = uuid.uuid4().hex
            self.speech = True
            self.boundary.reset()
            self.cue_used = False
            self.frames = list(self.ring)
            self.utterance_start = self.samples - len(self.frames) * 512
            self.partial_at = self.samples
            self.markers = {"speech_start_sample": self.samples - 5 * 512}
            await self.emit("speech_start", sample=self.samples - 5 * 512)
        else:
            self.frames.append(floats)
        if probability >= 0.35:
            self.last_voice = self.samples
            self.boundary.voiced(self.samples)
            if self.cue_pending:
                self.cue_pending = False
                if self.cue_task and not self.cue_task.done():
                    self.cue_task.cancel()
                # Resuming within one answer also interrupts patience audio.
                self.audio_pending.clear()
                self.audio_slots = asyncio.Semaphore(self.playback_window)
                await self.emit("listener_resumed")
        settled_speech = self.samples - self.last_voice >= 3200 and self.partial_at < self.last_voice + 3200
        if (self.samples - self.partial_at >= 16000 or settled_speech) and (not self.partial or self.partial.done()):
            self.partial_at = self.samples
            self.partial = self.task(self.transcribe_partial(b"".join(self.frames), self.generation, self.samples, self.last_voice))
        completion = self.preview.get("complete") if self.preview else None
        silence = 25600 if completion is False else (11200 if completion is True else 17600)
        if self.smart_endpoint:
            if self.boundary.due(self.samples) and (not self.endpoint_task or self.endpoint_task.done()):
                self.boundary.checked_at = self.samples
                self.endpoint_task = self.task(self.check_endpoint(b"".join(self.frames[-250:]), self.last_voice, self.generation))
            ended = self.boundary.complete(self.samples)
            if self.samples - self.last_voice >= 80000 and not self.cue_used and not ended:
                self.cue_used = True
                self.cue_task = self.task(self.patience())
        else:
            ended = self.samples - self.last_voice >= silence
        if ended or len(self.frames) * 512 >= 16000 * 180:
            limit = len(self.frames) * 512 >= 16000 * 180
            self.speech = False
            self.voiced = 0
            self.ring.clear()
            self.markers.update(
                speech_end_sample=self.last_voice, endpoint_sample=self.samples, endpoint_kind="capture_limit" if limit else "detected"
            )
            pcm = b"".join(self.frames)
            self.frames = []
            await self.emit("endpoint", **self.markers)
            self.reply = self.task(self.complete(pcm, self.generation, limit))

    async def check_endpoint(self, pcm, voice_sample, generation):
        import numpy as np

        try:
            result = await asyncio.to_thread(self.endpoint.predict, np.frombuffer(pcm, dtype="<f4"))
            if generation == self.generation and self.speech and not self.paused:
                self.boundary.result(result["probability"], voice_sample)
        except asyncio.CancelledError:
            raise
        except Exception:
            if not self.boundary.failed:
                self.boundary.failed = True
                await self.emit("quality_notice", message="Pause detection is unavailable. Use ‘I've finished’ when ready.")

    async def patience(self):
        self.cue_pending = True
        await self.speak("Take your time. There is no rush.", cue=True)

    async def finish_answer(self):
        if self.paused or not self.speech:
            return
        self.speech = False
        self.voiced = 0
        self.ring.clear()
        self.markers.update(speech_end_sample=self.last_voice, endpoint_sample=self.samples, endpoint_kind="manual")
        pcm = b"".join(self.frames)
        self.frames = []
        await self.emit("endpoint", **self.markers)
        self.reply = self.task(self.complete(pcm, self.generation))

    async def transcribe_partial(self, pcm, generation, end_sample=None, voiced_sample=None):
        try:
            result = await self.asr.infer(pcm)
            if generation != self.generation or self.paused:
                return
            recognised = normal(result.get("text", ""))
            text = recognised if command(recognised) != "none" else normal(" ".join([*self.continuation, recognised]))
            if not text or result.get("no_speech", 1) > 0.5:
                return
            self.last_heard_partial = text
            if end_sample is not None:
                self.last_recognition = {"result": result, "end": end_sample, "voice": voiced_sample, "generation": generation}
            await self.emit("partial", text=text)
            # Rapid partials are useful on screen, but launching an inference for
            # every changing fragment queues obsolete work on the local GPU.
            # Prepare only once the capture contains a short speech pause.
            if end_sample is not None and (voiced_sample is None or end_sample - voiced_sample < 3200):
                return
            if self.preview and self.preview["text"] == text:
                return
            if self.speculation:
                self.speculation.cancel()
            if self.prepared_voice:
                self.prepared_voice.cancel()
                self.prepared_voice = None
            self.preview = {"text": text, "result": None}
            self.speculation = self.task(self.prepare(text, generation))
        except asyncio.CancelledError:
            raise
        except Exception:
            # Final recognition gets one fresh attempt; partial failures cannot create observations.
            if generation == self.generation:
                self.preview = None

    async def prepare(self, text, generation, source_turn=None):
        if self.interpret is interpret:
            result = await prepare_turn(self.session, text, source_turn or self.turn)
            routed, plan = result["route"], result["plan"]
        else:
            # Injectable legacy boundary for deterministic controller tests.
            question = (self.session.get("current_question") or {}).get("text", "Describe the process.")
            history = "\n".join(f"[{s['kind']}] {s['text']}" for s in self.session["segments"])
            routed = await self.interpret(question, text, history)
            context = hearing_context(self.session, text, routed["kind"], source_turn or self.turn)
            plan = None
            if not routed["clarification"] and routed["command"] == "none":
                plan = await asyncio.wait_for(self.planner.plan(context), 20)
            result = {"route": routed, "context": context, "plan": plan}
        if generation == self.generation and self.preview and self.preview["text"] == text:
            self.preview["complete"] = routed.get("complete", True)
        if generation == self.generation and not self.paused:
            spoken = routed["clarification"] or (plan or {}).get("text")
            if spoken and (not plan or not plan.get("reason")) and routed["command"] == "none":
                if self.prepared_voice:
                    self.prepared_voice.cancel()
                self.prepared_voice = PreparedSpeech(self.speaker, spoken)
                self.work.add(self.prepared_voice.task)
                self.prepared_voice.task.add_done_callback(self.work.discard)
                result["speech"] = self.prepared_voice
        if generation == self.generation and self.preview and self.preview["text"] == text:
            self.preview["result"] = result
        return result

    async def complete(self, pcm, generation, limit=False):
        captured = False
        try:
            if self.partial and not self.partial.done():
                with suppress(Exception):
                    await self.partial
            prior = self.last_recognition
            if (prior and prior["generation"] == generation and prior["voice"] == self.last_voice
                    and prior["end"] - self.last_voice >= 3200):
                result = prior["result"]
            else:
                result = await self.asr.infer(pcm)
            if generation != self.generation or self.paused:
                return
            recognised = normal(result.get("text", ""))
            text = recognised if command(recognised) != "none" else normal(" ".join([*self.continuation, recognised]))
            await self.emit("final_transcript", text=text)
            if not text or result.get("no_speech", 1) > 0.5:
                await self.speak("I couldn't get clear speech that time. Please check your microphone and say that again.")
                return
            if len(text) > 6000:
                await self.pause("That answer exceeded the transcript limit. Please use the fallback to review it.")
                return
            # Controls are application actions. They must not depend on a planner,
            # a wording check, or an unfinished earlier answer's speculative work.
            direct = command(recognised)
            if direct != "none":
                self.pending_check = None
                if direct == "recap":
                    await self.show_recap()
                else:
                    await self.pause("Paused. Your provisional wording is saved. Resume when ready.")
                return
            self.inflight_text = text
            self.continuation = []
            self.session = self.store.observe(self.session, text, self.turn)
            captured = True
            await self.emit("snapshot", session=self.session)
            source_turn = self.turn
            if self.pending_check:
                original, original_turn = self.pending_check
                if text.lower().strip(" .!") in ("yes", "yes that is correct", "yes that's correct", "correct", "that is correct"):
                    text = original
                    source_turn = original_turn
                    self.pending_check = None
                    self.preview = None
                    # Rebuild with the participant's explicit high-impact wording check.
                else:
                    self.pending_check = None
            elif (re.search(r"\d|£|\b(?:not|never)\b", text, re.I) and len(text) <= 380
                  and normal(self.last_heard_partial or "").casefold() != text.casefold()):
                self.pending_check = (text, self.turn)
                if self.prepared_voice:
                    self.prepared_voice.cancel()
                    self.prepared_voice = None
                if self.speculation:
                    self.speculation.cancel()
                self.inflight_text = None
                await self.emit("wording_check", text=text)
                await self.speak("I heard: " + text + " Is that wording right? Say yes, or say the corrected answer.")
                return
            await self.emit("state", state="thinking", message="Considering your answer…")
            cached = self.preview and self.preview["text"] == text
            if cached and self.speculation:
                with suppress(Exception):
                    await self.speculation
            if generation != self.generation or self.paused:
                return
            prepared = self.preview["result"] if cached and self.preview and self.preview["result"] else None
            if not prepared:
                if self.speculation:
                    self.speculation.cancel()
                prepared = await self.prepare(text, generation, source_turn)
            if generation != self.generation or self.paused:
                return
            route, plan, context = prepared["route"], prepared["plan"], prepared["context"]
            if route["command"] == "pause":
                await self.pause("Paused. Your provisional wording is saved. Resume when ready.")
                return
            if route["command"] == "recap":
                await self.show_recap()
                return
            if route.get("complete") is False and route["category"] in ("responsive", "unclear"):
                await self.speak("Go on, I'm listening.")
                return
            if route["clarification"]:
                self.inflight_text = None
                await self.emit("clarification", text=route["clarification"], answer=text)
                await self.speak(route["clarification"], prepared=prepared.get("speech"))
                return
            self.session = self.store.heard(self.session, text, route["kind"], source_turn)
            self.inflight_text = None
            await self.emit("snapshot", session=self.session)
            if limit:
                await self.speak("I have captured this part. That was a long answer; please continue when you are ready.")
                return
            if not plan or plan.get("reason"):
                await self.speak("I've kept your wording, but couldn't prepare the follow-up. You can add more, or ask for the recap.")
                return
            self.session = self.store.question(self.session, plan, context)
            q = self.session["current_question"]
            question = q["text"]
            await self.emit("question", text=question, question=self.session["current_question"])
            if len(self.session["segments"]) >= 20 or time.monotonic() - self.started_at > 600:
                await self.show_recap()
                return
            try:
                await self.speak(question, prepared=prepared.get("speech"))
            finally:
                # Let the first voice batch reach playback before competing for
                # unified memory with background semantic inference.
                if not self.closed and (q.get("generation") or {}).get("lane") == "spoken":
                    self.queue_review(q, context)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logging.getLogger(__name__).warning("Conversation turn failed: %s; captured=%s", type(exc).__name__, captured)
            if generation == self.generation:
                if captured:
                    self.inflight_text = None
                    await self.emit("error", message="Your answer is saved. Local reasoning is unavailable; you can open the recap.")
                    await self.speak("I've saved your answer. The local reasoning engine is having trouble. We can open the recap.")
                    return
                await self.emit(
                    "error", message="I could not complete that turn. Your saved words are safe. Please retry or open the recap."
                )
                self.inflight_text = None
                await self.speak("I could not capture that turn. Please say it again, or ask for the recap.")

    async def review_in_background(self, question_id, text, context):
        try:
            account = "\n".join(f"[{s['kind']}] {s['text']}" for s in context["segments"])
            async with httpx.AsyncClient(base_url="http://127.0.0.1:11434", timeout=15, trust_env=False) as client:
                review = await review_question(client, account, [q["text"] for q in context["questions"]], text)
        except asyncio.CancelledError:
            raise
        except Exception:
            review = {"verdict": "unavailable", "reason": "Background question review did not complete."}
        if not self.closed and self.session["status"] == "active":
            self.session = self.store.audit_question(self.session, question_id, review)
            await self.emit("snapshot", session=self.session)
            if review["verdict"] != "pass" and (self.session.get("current_question") or {}).get("id") == question_id:
                await self.emit("quality_notice", message="That question needs review. You can correct its premise or leave it open.")

    async def speak(self, text, allow_paused=False, prepared=None, cue=False):
        generation = self.generation
        async with self.speech_lock:
            if generation != self.generation or (self.paused and not allow_paused):
                return
            await self._speak(text, allow_paused, prepared, cue)

    async def _speak(self, text, allow_paused=False, prepared=None, cue=False):
        generation = self.generation
        await self.emit("speech", text=text, cue=cue)
        index = 0
        # The existing speech grammar/grounding check has already checked generated questions.
        planned_delivery = cue or getattr(self.speaker, "engine", "") == "pocket" or (prepared and prepared.text == text)
        sentences = [text] if planned_delivery else re.split(r"(?<=[.!?])\s+", text)
        for sentence in sentences:
            if not sentence.strip():
                continue
            async def cached_cue():
                for chunk in self.patience_chunks:
                    yield chunk
            chunks = (cached_cue() if cue else
                      prepared.stream() if prepared and prepared.text == text else self.speaker.stream(sentence.strip()))
            async for chunk in chunks:
                if (self.paused and not allow_paused) or generation != self.generation:
                    return
                await self.audio_slots.acquire()
                if generation != self.generation:
                    return
                self.audio_index += 1
                self.audio_pending.add(self.audio_index)
                self.audio_empty.clear()
                await self.emit("audio_chunk", index=self.audio_index, rate=chunk["rate"], pcm=chunk["pcm"], cue=cue)
                index += 1
        if generation == self.generation:
            await self.emit("audio_end")
        if cue:
            await asyncio.wait_for(self.audio_empty.wait(), 15)
        if generation == self.generation:
            await self.emit("speech_done", chunks=index, cue=cue)

    def audio_ack(self, data):
        if data.get("generation_id") == str(self.generation) and data.get("index") in self.audio_pending:
            self.audio_pending.remove(data["index"])
            self.audio_slots.release()
            if not self.audio_pending:
                self.audio_empty.set()

    async def show_recap(self):
        reply = self.reply
        self.interrupt()
        if reply and reply is not asyncio.current_task():
            # Cancellation may register the spoken question's pending review.
            await asyncio.gather(reply, return_exceptions=True)
        self.recap = True
        self.paused = True
        self.speech = False
        self.frames.clear()
        await self.emit(
            "recap",
            session=self.session,
            message="Review the wording and contribution kinds below. Correct anything I misheard, then confirm the recap once.",
        )

        self.start_review_drain()

    async def read_recap(self):
        if not self.recap:
            raise Conflict("Open the recap first.")
        self.interrupt()

        async def reading():
            await self.speak("Here is the wording we captured. It is still yours to correct.", allow_paused=True)
            for segment in self.session["segments"]:
                # Verbatim participant wording, bounded at word boundaries for the speech engine.
                words = segment["text"].split()
                while words:
                    part = []
                    while words and sum(map(len, part)) + len(part) + len(words[0]) <= 550:
                        part.append(words.pop(0))
                    if not part:
                        raise ValueError("A recap word exceeds the speech limit; review it as text.")
                    await self.speak(" ".join(part), allow_paused=True)
            await self.speak("Correct anything I misheard, then confirm the recap when you are ready.", allow_paused=True)

        self.reply = self.task(reading())

    async def confirm(self, data):
        if not self.recap or data.get("expected_revision") != self.session["revision"]:
            raise Conflict("Open the current recap before confirming.")
        self.interrupt()
        self.start_review_drain()
        # Review is off the spoken path, but its outcome must be present in the draft provenance.
        if self.reviews:
            await asyncio.gather(*tuple(self.reviews))
        self.session = self.store.confirm_recap(self.session, data.get("rows"))
        self.session = self.interviews.store.finish(
            self.session["id"], self.session["revision"], self.interviews.evidence.current(self.session["evidence"])
        )
        await self.emit("finished", session=self.session)

    async def pause(self, message):
        self.interrupt()
        self.paused = True
        self.speech = False
        self.frames.clear()
        self.ring.clear()
        await self.emit("paused", message=message)

    async def resume(self):
        if self.session["status"] != "active":
            raise Conflict("This draft has finished. Open it in the review page.")
        self.interrupt()
        if self.review_drain and not self.review_drain.done():
            self.review_drain.cancel()
            await asyncio.gather(self.review_drain, return_exceptions=True)
        if self.defer_reviews:
            await self.warm_planner()
        self.sequence = -1
        self.samples = 0
        self.last_voice = 0
        self.voiced = 0
        self.recap = self.paused = False
        self.last_frame_at = time.monotonic()
        await self.vad.infer(b"")
        await self.emit("ready")

    async def close(self):
        self.closed = True
        self.interrupt()
        for task in tuple(self.work):
            task.cancel()
        await asyncio.gather(*self.work, return_exceptions=True)
        await asyncio.gather(self.asr.close(), self.vad.close(), self.speaker.close())
        for question_id, _, _ in self.deferred_reviews:
            if self.session["status"] == "active":
                self.session = self.store.audit_question(self.session, question_id, {
                    "verdict": "unavailable", "reason": "Session closed before queued question review completed."})
        self.deferred_reviews.clear()
        self.interviews.store.pause(self.session["id"], "disconnect")


def attach_conversation(app, runtime, token, interviews):
    owner = set()

    @app.websocket("/api/conversation/{identifier}")
    async def continuous(socket: WebSocket, identifier: str):
        host = socket.headers.get("host", "")
        if host.split(":")[0] not in ("localhost", "127.0.0.1") or socket.headers.get("origin") != "http://" + host:
            await socket.close(code=1008)
            return
        await socket.accept()
        session = None
        lock = asyncio.Lock()

        async def send(value):
            async with lock:
                await socket.send_json(value)

        try:
            hello = await asyncio.wait_for(socket.receive_json(), 5)
            if (
                not isinstance(hello, dict)
                or not isinstance(hello.get("token"), str)
                or not secrets.compare_digest(hello["token"], token)
                or owner
            ):
                await socket.close(code=1008)
                return
            saved = interviews.store.get(identifier)
            if saved["status"] != "active":
                raise Conflict("Reopen and resume the saved session first.")
            owner.add(identifier)
            session = Conversation(runtime, interviews, saved, send)
            await session.start()
            while True:
                raw = await socket.receive_text()
                if len(raw) > 500_000:
                    raise ValueError("Oversized conversation message")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("Invalid message")
                kind = data.get("type")
                if kind == "frame":
                    await session.feed(data)
                elif kind == "audio_ack":
                    session.audio_ack(data)
                elif kind == "finish_answer":
                    await session.finish_answer()
                elif kind == "pause":
                    await session.pause("Paused. Microphone capture and playback are stopped.")
                elif kind == "resume":
                    await session.resume()
                elif kind == "recap":
                    await session.show_recap()
                elif kind == "read_recap":
                    await session.read_recap()
                elif kind == "confirm_recap":
                    try:
                        await session.confirm(data)
                    except (ValueError, Conflict) as exc:
                        await session.emit("error", message=str(exc))
                else:
                    raise ValueError("Unknown conversation message")
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception:
            with suppress(RuntimeError, WebSocketDisconnect):
                await send(
                    {"type": "error", "message": "Continuous voice is unavailable. Your saved text is safe; use the fallback interview."}
                )
        finally:
            with anyio.CancelScope(shield=True):
                if session:
                    try:
                        await session.close()
                    finally:
                        owner.discard(identifier)
                with suppress(RuntimeError):
                    await socket.close()
