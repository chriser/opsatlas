"""Bounded single-headset conversation: PCM -> VAD -> resident ASR -> speculative questions -> PCM."""

import array
import asyncio
import base64
import binascii
import json
import re
import secrets
import time
import uuid
from collections import deque
from contextlib import suppress

import anyio
from fastapi import WebSocket, WebSocketDisconnect

from .conversation_store import ConversationStore, hearing_context
from .dialogue import LocalPlanner
from .ledger import Conflict
from .resident import Resident
from .speech import SpeechWorker
from .turn_interpreter import interpret

OPENING = (
    "I'm your process interviewer. This is a fictional practice conversation, saved only on this Mac. "
    "You can interrupt me, say pause, or ask for the recap. We'll check the wording together at the end. "
    "Think of a supplier activation. What happened from the request to the outcome?"
)


def normal(text):
    return " ".join(text.split()).strip()


class Conversation:
    def __init__(self, runtime, interviews, session, send, recognizer=None, detector=None, speaker=None, interpreter=interpret):
        self.interviews, self.session, self.send = interviews, session, send
        self.store = ConversationStore(interviews.store)
        self.asr = recognizer or Resident(runtime, "asr", "ggml-small.en.bin")
        self.vad = detector or Resident(runtime, "vad")
        self.speaker = speaker or SpeechWorker("kokoro", runtime)
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
        self.pending_check = None
        self.inflight_text = None
        self.continuation = []
        self.started_at = time.monotonic()
        self.markers = {}
        self.audio_slots = asyncio.Semaphore(2)
        self.audio_pending = set()
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
        self.session = self.store.begin(self.session)
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

    def interrupt(self, continue_answer=False):
        if continue_answer and self.inflight_text:
            self.continuation = [self.inflight_text]
        elif not continue_answer:
            self.continuation = []
        self.inflight_text = None
        self.generation += 1
        self.preview = None
        self.audio_slots = asyncio.Semaphore(2)
        self.audio_pending.clear()
        for task in (self.reply, self.speculation):
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
            self.frames = list(self.ring)
            self.utterance_start = self.samples - len(self.frames) * 512
            self.partial_at = self.samples
            self.markers = {"speech_start_sample": self.samples - 5 * 512}
            await self.emit("speech_start", sample=self.samples - 5 * 512)
        else:
            self.frames.append(floats)
        if probability >= 0.35:
            self.last_voice = self.samples
        if self.samples - self.partial_at >= 16000 and (not self.partial or self.partial.done()):
            self.partial_at = self.samples
            self.partial = self.task(self.transcribe_partial(b"".join(self.frames), self.generation))
        completion = self.preview.get("complete") if self.preview else None
        silence = 25600 if completion is False else (11200 if completion is True else 17600)
        if self.samples - self.last_voice >= silence or len(self.frames) * 512 >= 16000 * 180:
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

    async def transcribe_partial(self, pcm, generation):
        try:
            result = await self.asr.infer(pcm)
            if generation != self.generation or self.paused:
                return
            text = normal(" ".join([*self.continuation, result.get("text", "")]))
            if not text or result.get("no_speech", 1) > 0.5:
                return
            await self.emit("partial", text=text)
            if self.preview and self.preview["text"] == text:
                return
            if self.speculation:
                self.speculation.cancel()
            self.preview = {"text": text, "result": None}
            self.speculation = self.task(self.prepare(text, generation))
        except asyncio.CancelledError:
            raise
        except Exception:
            # Final recognition gets one fresh attempt; partial failures cannot create observations.
            if generation == self.generation:
                self.preview = None

    async def prepare(self, text, generation, source_turn=None):
        question = (self.session.get("current_question") or {}).get("text", "Describe the process.")
        history = "\n".join(f"[{s['kind']}] {s['text']}" for s in self.session["segments"])
        routed = await self.interpret(question, text, history)
        if generation == self.generation and self.preview and self.preview["text"] == text:
            self.preview["complete"] = routed.get("complete", True)
        context = hearing_context(self.session, text, routed["kind"], source_turn or self.turn)
        plan = None
        if not routed["clarification"] and routed["command"] == "none":
            plan = await asyncio.wait_for(self.planner.plan(context), 20)
        result = {"route": routed, "context": context, "plan": plan}
        if generation == self.generation and self.preview and self.preview["text"] == text:
            self.preview["result"] = result
        return result

    async def complete(self, pcm, generation, limit=False):
        try:
            result = await self.asr.infer(pcm)
            if generation != self.generation or self.paused:
                return
            text = normal(" ".join([*self.continuation, result.get("text", "")]))
            await self.emit("final_transcript", text=text)
            if not text or result.get("no_speech", 1) > 0.5:
                await self.speak("I couldn't get clear speech that time. Please check your microphone and say that again.")
                return
            if len(text) > 6000:
                await self.pause("That answer exceeded the transcript limit. Please use the fallback to review it.")
                return
            self.inflight_text = text
            self.continuation = []
            self.session = self.store.observe(self.session, text, self.turn)
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
            elif re.search(r"\d|£|\b(?:not|never)\b", text, re.I) and len(text) <= 380:
                self.pending_check = (text, self.turn)
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
            if route["clarification"]:
                self.inflight_text = None
                await self.emit("clarification", text=route["clarification"], answer=text)
                await self.speak(route["clarification"])
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
            question = self.session["current_question"]["text"]
            await self.emit("question", text=question, question=self.session["current_question"])
            if len(self.session["segments"]) >= 20 or time.monotonic() - self.started_at > 600:
                await self.show_recap()
                return
            await self.speak(question)
        except asyncio.CancelledError:
            raise
        except Exception:
            if generation == self.generation:
                await self.emit(
                    "error", message="I could not complete that turn. Your saved words are safe. Please retry or open the recap."
                )
                await self.speak("I lost that turn. Please say it again, or ask for the recap.")

    async def speak(self, text, allow_paused=False):
        generation = self.generation
        await self.emit("speech", text=text)
        index = 0
        # The existing speech grammar/grounding check has already checked generated questions.
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            if not sentence.strip():
                continue
            async for chunk in self.speaker.stream(sentence.strip()):
                if (self.paused and not allow_paused) or generation != self.generation:
                    return
                await self.audio_slots.acquire()
                if generation != self.generation:
                    return
                self.audio_index += 1
                self.audio_pending.add(self.audio_index)
                await self.emit("audio_chunk", index=self.audio_index, rate=chunk["rate"], pcm=chunk["pcm"])
                index += 1
        if generation == self.generation:
            await self.emit("speech_done", chunks=index)

    def audio_ack(self, data):
        if data.get("generation_id") == str(self.generation) and data.get("index") in self.audio_pending:
            self.audio_pending.remove(data["index"])
            self.audio_slots.release()

    async def show_recap(self):
        self.interrupt()
        self.recap = True
        self.paused = True
        self.speech = False
        self.frames.clear()
        await self.emit(
            "recap",
            session=self.session,
            message="Review the wording and contribution kinds below. Correct anything I misheard, then confirm the recap once.",
        )

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
