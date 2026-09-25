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

from .companion import Companion
from .conversation import review_question
from .conversation_store import ConversationStore, hearing_context
from .dialogue import LocalPlanner
from .endpointing import TurnBoundary
from .ledger import Conflict
from .resident import Resident
from .social import PHRASES, Listener
from .social import intent as social_intent
from .speech import PreparedSpeech, SpeechWorker
from .spoken_audio import SpokenAudio
from .tibi import EvidenceChanged
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


# Whisper captions non-speech sound instead of transcribing it: "(gentle music)", "[BLANK_AUDIO]", "♪".
ANNOTATION = re.compile(r"[\(\[][^\)\]]{0,40}[\)\]]|[♪♫*]+")


def spoken(text):
    """Recognised words with non-speech captions removed; empty when only sound was heard."""
    return normal(ANNOTATION.sub(" ", text))


class CachedSpeech:
    """Pre-rendered approved audio with the PreparedSpeech interface."""

    done = True

    def __init__(self, text, chunks):
        self.text, self.chunks = text, chunks

    async def stream(self):
        for chunk in self.chunks:
            yield chunk

    def cancel(self):
        pass


class PreparationError(RuntimeError):
    """A safe, actionable startup failure, without exposing internal exception text."""


class Conversation:
    def __init__(self, runtime, interviews, session, send, recognizer=None, detector=None, speaker=None,
                 interpreter=interpret, endpoint=None, listener_only=False, text_only=False):
        self.interviews, self.session, self.send = interviews, session, send
        self.text_only = text_only
        self.store = ConversationStore(interviews.store)
        self.asr = recognizer or Resident(runtime, "asr", "ggml-small.en.bin", os.environ.get("SME_ASR_VOCABULARY") or None)
        self.vad = detector or Resident(runtime, "vad")
        self.speaker = speaker or SpeechWorker(os.environ.get("SME_VOICE_BACKEND", "kokoro"), runtime)
        self.endpoint = endpoint
        self.smart_endpoint = endpoint is not None or os.environ.get("SME_SMART_ENDPOINT") == "1"
        self.boundary = TurnBoundary()
        self.endpoint_task = None
        self.tibi_preview = None
        self.prewarm = None
        self.render_task = None
        self.pending_checks = []
        self.speech_lock = asyncio.Lock()
        self.companion = Companion(session.get("social_dialogue")) if os.environ.get("SME_SOCIAL_CHAT") == "1" else None
        if getattr(interviews, "companion_factory", None):
            self.companion = interviews.companion_factory(session.get("social_dialogue"))
        if getattr(interviews, "product_companion_factory", None) and session['evidence'].get('product_interview'):
            self.companion = interviews.product_companion_factory(session)
        if self.companion:
            self.companion.archive = list(session.get('social_transcript', session.get('social_dialogue', [])))
            self.companion.review_findings = [c for c in session.get("knowledge_checks", [])
                                             if c['status'] == 'possible_conflict'][-2:]
        # Tibi streams segments; the product interviewer and legacy small talk reply whole.
        self.tibi = self.companion if hasattr(self.companion, "begin") else None
        if self.tibi:
            # A companion conversation treats a 1.6 s pause as the end of a turn: the turn model often
            # reads a flat statement ("I have been in meetings all day.") as unfinished. Carrying on
            # talking interrupts the reply and continues the same turn.
            self.boundary = TurnBoundary(fallback=25600)
        self.spoken_audio = SpokenAudio(runtime)
        self.listener_only = bool(session.get("listener_practice") or listener_only or self.companion)
        self.listener = Listener(session.get("listener"))
        self.social_audio = {}
        self.practice_help_given = False
        self.wait_notice_sent = False
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
        self.playback_window = 8 if getattr(self.speaker, "engine", "") in (
            "pocket", "chatterbox", "qwen_custom", "higgs", "higgs_female") else 2
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
        async def prepare(worker, label):
            started = time.monotonic()
            try:
                await worker.start()
            except Exception as exc:
                raise PreparationError(f'{label} could not start. Reopen the saved conversation and retry.') from exc
            logging.getLogger(__name__).info('%s ready in %.2fs', label, time.monotonic() - started)

        try:
            await asyncio.wait_for(asyncio.gather(prepare(self.speaker, 'Local voice'), *([] if self.text_only else [
                prepare(self.asr, 'Speech recognition'), prepare(self.vad, 'Speech detection')])), 45)
        except TimeoutError as exc:
            raise PreparationError('Local voice preparation timed out. Reopen the saved conversation and retry.') from exc
        if self.smart_endpoint and self.endpoint is None and not self.text_only:
            from .experience.listener import Endpoint
            self.endpoint = await asyncio.to_thread(Endpoint)
        # Small same-voice bank, prepared before listening; no GPU inference or
        # speech synthesis on the social response path. Bound the memory budget.
        cached_bytes = 0
        for wording in ([] if self.companion else dict.fromkeys(text for options in PHRASES.values() for text in options)):
            chunks = []
            async for chunk in self.speaker.stream(wording):
                cached_bytes += len(chunk["pcm"])
                if cached_bytes > 8_000_000:
                    raise ValueError("Listener audio cache exceeded its budget")
                chunks.append(chunk)
            self.social_audio[wording] = chunks
        if self.companion:
            await self.emit("state", state="warming", message="Preparing the local conversation model…")
            await self.companion.warm()
        elif self.defer_reviews and not self.listener_only:
            await self.warm_planner()
        voice = "Pocket TTS · Charles" if getattr(self.speaker, "engine", "") == "pocket" else "Kokoro · Isabella"
        if getattr(self.speaker, "engine", "") == "chatterbox":
            voice = "Chatterbox Turbo · British male reference"
        if getattr(self.speaker, "engine", "") == "qwen_custom":
            voice = "Qwen CustomVoice · Aiden (British-English instruction)"
        if getattr(self.speaker, "engine", "") in ("higgs", "higgs_female"):
            voice = "Higgs · British " + ("female" if self.speaker.engine == "higgs_female" else "male") + " reference"
        self.session = self.store.begin(self.session, voice=voice)
        if self.listener_only and not self.session.get("listener_practice"):
            def mark_practice(saved):
                saved["listener_practice"] = True
                saved["social_practice"] = self.companion is not None
                if self.companion:
                    saved["social_engine"] = getattr(self.speaker, "engine", "chatterbox")
                return {"mode": "listener_practice"}
            self.session = self.store.update(self.session["id"], self.session["revision"], "listener_practice", mark_practice)
        self.paused = False
        self.last_frame_at = time.monotonic()
        await self.emit("snapshot", session=self.session)
        self.task(self.watchdog())
        if self.tibi:
            self.task(self.prerender_loop())
        if self.companion:
            self.reply = self.task(self.speak("Welcome back. Would you like to pick up where we left off?"
                                              if self.companion.history else
                                              getattr(self.companion, "opening", "Hello, good to hear from you. How is your day going?")))
        elif self.listener_only:
            self.reply = self.task(self.speak(
                "This is listening practice. You can ask for time, correct me, or ask me to leave you space to think. "
                "I am not interpreting process details in this practice."))
        elif self.session["segments"]:
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
        self.generation += 1
        if not self.tibi:
            self.pause_checks()
        if self.render_task and not self.render_task.done():
            self.render_task.cancel()
        self.cancel_tibi_preview()
        if self.prepared_voice:
            self.prepared_voice.cancel()
            self.prepared_voice = None
        self.preview = None
        self.last_heard_partial = None
        self.last_recognition = None
        self.audio_slots = asyncio.Semaphore(self.playback_window)
        self.audio_pending.clear()
        self.audio_empty.set()
        for task in (self.reply, self.speculation, self.endpoint_task):
            if task and task is not asyncio.current_task():
                task.cancel()
        self.reply = self.speculation = None

    async def watchdog(self):
        while not self.closed:
            await asyncio.sleep(1)
            if not self.text_only and not self.paused and time.monotonic() - self.last_frame_at > 3:
                await self.pause("Audio stopped arriving. Your saved wording is safe. Check the microphone, then resume.")

    async def feed(self, data):
        if self.closed or self.paused or self.text_only:
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
            self.wait_notice_sent = False
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
            if not ended and self.samples - self.last_voice >= 48000 and not self.wait_notice_sent:
                self.wait_notice_sent = True
                await self.emit("endpoint_wait", message="I am still listening. If you have finished, "
                                "press ‘I've finished this answer’ so I can respond.")
            # Silence alone is not a request for reassurance. Explicit social
            # requests are handled after recognition, without the planner.
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

    async def social_chat(self, text, generation):
        if not self.companion or self.paused or generation != self.generation:
            return
        if self.session['evidence'].get('product_interview') and len(self.session.get('product_turns', [])) >= 60:
            await self.emit('error', message='This interview has reached 60 contributions. Pause and review before starting another.')
            return
        await self.emit("state", state="thinking", message="Considering what you said…")
        prepared = None
        try:
            async with asyncio.timeout(9):
                result = await self.companion.respond(text)
            if self.paused or generation != self.generation:
                return
            if getattr(self.speaker, "engine", "") in ("higgs", "higgs_female"):
                await self.emit("reply_preparing", reasoning_ms=result["reasoning_ms"])
                await self.emit("state", state="thinking", message="Preparing Tibi’s voice…")
                prepared = PreparedSpeech(self.speaker, result["reply"])
                self.prepared_voice = prepared
                self.work.add(prepared.task)
                prepared.task.add_done_callback(self.work.discard)
                async with asyncio.timeout(30):
                    await prepared.wait_ready()
                if self.paused or generation != self.generation:
                    prepared.cancel()
                    return
            self.companion.commit(text, result["reply"])

            def change(saved):
                # Durable transcript is independent of the rolling model context.
                transcript = saved.setdefault("social_transcript", list(saved.get("social_dialogue", [])))
                transcript.extend([{"role": "user", "content": text},
                                   {"role": "assistant", "content": result["reply"]}])
                saved["social_dialogue"] = self.companion.history
                if "product_turn" in result:
                    saved.setdefault('product_turns', []).append({**result['product_turn'], 'id': uuid.uuid4().hex})
                if "evidence" in result:
                    saved["answer_evidence"] = result["evidence"]
                return {"phase": result["phase"], "style": result["style"], "reasoning_ms": result["reasoning_ms"],
                        "user": text, "assistant": result["reply"]}

            self.session = self.store.update(self.session["id"], self.session["revision"], "social_exchange", change)
            if "product_turn" in result:
                self.companion.accept_turn(result['product_turn'])
            await self.emit("snapshot", session=self.session)
            await self.emit("social_reply", **result)
            # An acoustic chuckle is allowed only when the semantic layer chooses
            # amused; it is never added as a latency filler or to sympathetic speech.
            spoken = result["reply"]
            if result["style"] == "amused" and getattr(self.speaker, "engine", "") == "chatterbox":
                spoken = "[chuckle] " + spoken
            await self.speak(spoken, prepared=prepared, style=result["style"])
            if result.get("background_check") and not self.paused and generation == self.generation:
                self.queue_check(text, result["reply"], generation)
            if result["phase"] in ("ready", "closed"):
                await self.emit("social_boundary", phase=result["phase"], message=(
                    "Small-talk practice complete. The full process interview is a separate session."
                    if result["phase"] == "ready" else "Thank you. You can pause or start another exchange."))
        except asyncio.CancelledError:
            raise
        except Exception:
            if generation == self.generation and not self.paused:
                await self.emit("error", message=("Tibi could not prepare the voice. Please retry, or pause." if prepared else
                                                  "The local conversation model could not reply. Please retry, or pause."))

        finally:
            if prepared and not prepared.done:
                prepared.cancel()

    # ---- Tibi: streamed, speculative turns -------------------------------------------

    def cancel_tibi_preview(self):
        preview, self.tibi_preview = self.tibi_preview, None
        if preview:
            preview["turn"].cancel()
            if feeder := preview.get("feeder"):
                feeder.cancel()
            if audio := preview.get("first_audio"):
                audio.cancel()

    async def prepare_preview(self, preview):
        # Sole consumer of a speculative turn's first segment; starts its audio during the pause.
        try:
            first = await preview["turn"].next()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            preview["error"] = exc
            return
        preview["first"] = first
        if first is not None and self.tibi_preview is preview:
            preview["first_audio"] = self.prepare_audio(first)

    def prepare_audio(self, segment):
        """Pre-rendered approved audio when available; otherwise start streamed synthesis now."""
        engine = getattr(self.speaker, "engine", "")
        if segment.audio_key and (chunks := self.spoken_audio.get(engine, segment.audio_key)):
            return CachedSpeech(segment.text, chunks)
        prepared = PreparedSpeech(self.speaker, segment.text)
        self.work.add(prepared.task)
        prepared.task.add_done_callback(self.work.discard)
        if segment.audio_key:
            def store(_):
                if prepared.chunks and not prepared.error:
                    with suppress(Exception):
                        self.spoken_audio.put(engine, segment.audio_key, prepared.chunks)
            prepared.task.add_done_callback(store)
        return prepared

    async def tibi_chat(self, text, generation):
        if not self.tibi or self.paused or generation != self.generation:
            return
        await self.emit("state", state="thinking", message="Considering what you said…")
        self.pause_checks()
        preview, self.tibi_preview = self.tibi_preview, None
        first = audio = None
        if preview and preview["text"].casefold() == text.casefold() and preview["generation"] == generation:
            turn = preview["turn"]
            turn.speculative = False
            with suppress(Exception):
                async with asyncio.timeout(12):
                    await preview["feeder"]
            if "error" in preview:
                first = preview["error"]
            else:
                first, audio = preview.get("first"), preview.get("first_audio")
        else:
            if preview:
                self.tibi_preview = preview
                self.cancel_tibi_preview()
            turn = self.tibi.begin(text)
        try:
            if isinstance(first, BaseException):
                raise first
            if first is None:
                async with asyncio.timeout(12):
                    first = await turn.next()
            if first is None:
                raise ValueError("Tibi produced no reply")
            if audio is None:
                audio = self.prepare_audio(first)
            await self.emit("reply_preparing", reasoning_ms=turn.marks.get("first_segment"), speculative=preview is not None
                            and turn is preview["turn"])
            spoken = await self.speak_segments(turn, first, audio, generation)
            if not spoken or generation != self.generation:
                return
            async with asyncio.timeout(5):
                await turn.task
            result = turn.result
            self.tibi.commit(text, result["reply"], result["route"])

            def change(saved):
                transcript = saved.setdefault("social_transcript", list(saved.get("social_dialogue", [])))
                transcript.extend([{"role": "user", "content": text}, {"role": "assistant", "content": result["reply"]}])
                saved["social_dialogue"] = self.tibi.history
                saved["answer_evidence"] = result["evidence"]
                saved.setdefault("turn_marks", []).append({"route": result["route"], "grounding": result["grounding"],
                                                           **result["marks"]})
                return {"phase": result["phase"], "style": result["style"], "reasoning_ms": result["reasoning_ms"],
                        "user": text, "assistant": result["reply"]}

            self.session = self.store.update(self.session["id"], self.session["revision"], "social_exchange", change)
            await self.emit("snapshot", session=self.session)
            await self.emit("social_reply", **result)
            if result.get("background_check") and not self.paused:
                self.queue_check(text, result["reply"], generation)
            else:
                self.kick_checks()
            if result["phase"] == "closed":
                await self.emit("social_boundary", phase="closed", message="Thank you. You can pause or start another exchange.")
        except asyncio.CancelledError:
            raise
        except EvidenceChanged:
            if generation == self.generation and not self.paused:
                await self.speak("The evidence changed while I checked. Please ask again so I can use the current version.")
        except Exception as exc:
            logging.getLogger(__name__).warning("Tibi turn failed: %s", type(exc).__name__)
            if generation == self.generation and not self.paused:
                await self.emit("error", message="The local conversation model could not reply. Please retry, or pause.")
                await self.speak("Sorry, I couldn't prepare a reply just then. Could you say that again?")
        finally:
            if not turn.task.done():
                turn.cancel()
            if audio is not None and not getattr(audio, "done", True):
                audio.cancel()

    async def speak_segments(self, turn, first, audio, generation):
        """Speak segments in order while later ones are synthesised; returns False if interrupted."""
        async with self.speech_lock:
            if generation != self.generation or self.paused:
                return False
            await self.emit("speech", text=first.text, cue=False)
            pending = asyncio.Queue()
            pending.put_nowait((first, audio))

            async def feed():
                try:
                    while (segment := await turn.next()) is not None:
                        pending.put_nowait((segment, self.prepare_audio(segment)))
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    pending.put_nowait(exc)
                    return
                pending.put_nowait(None)

            feeder = self.task(feed())
            count, opened = 0, False
            try:
                while (item := await pending.get()) is not None:
                    if isinstance(item, BaseException):
                        if count:
                            break  # keep what was already said; stop before anything unchecked
                        raise item
                    segment, prepared = item
                    if opened:
                        await self.emit("speech_append", text=segment.text)
                    opened = True
                    emitted = await self._emit_audio(prepared.stream(), generation)
                    if emitted is None:
                        return False
                    count += emitted
            finally:
                feeder.cancel()
                while not pending.empty():
                    item = pending.get_nowait()
                    if isinstance(item, tuple):
                        item[1].cancel()
            if generation != self.generation:
                return False
            await self.emit("audio_end")
            await self.emit("speech_done", chunks=count, cue=False)
            return True

    async def _emit_audio(self, chunks, generation, allow_paused=False, cue=False):
        """Flow-controlled chunk emission; None when interrupted."""
        count = 0
        async for chunk in chunks:
            if (self.paused and not allow_paused) or generation != self.generation:
                return None
            await self.audio_slots.acquire()
            if generation != self.generation:
                return None
            self.audio_index += 1
            self.audio_pending.add(self.audio_index)
            self.audio_empty.clear()
            await self.emit("audio_chunk", index=self.audio_index, rate=chunk["rate"], pcm=chunk["pcm"], cue=cue)
            count += 1
        return count

    async def prerender_loop(self):
        """Render approved spoken answers in the live voice while idle; yields to the participant."""
        engine = getattr(self.speaker, "engine", "")
        refreshed = 0
        while not self.closed:
            await asyncio.sleep(2)
            if self.paused or self.speech or (self.reply and not self.reply.done()) or self.tibi_preview:
                continue
            if time.monotonic() - refreshed > 20:
                refreshed = time.monotonic()
                with suppress(Exception):
                    await self.tibi.evidence.refresh()
            todo = [v for v in self.tibi.evidence.variants if not self.spoken_audio.get(engine, v["text_sha256"])]
            if not todo:
                continue
            variant = todo[0]

            async def render(text=variant["text"]):
                return [chunk async for chunk in self.speaker.stream(text)]

            self.render_task = self.task(render())
            try:
                chunks = await self.render_task
            except asyncio.CancelledError:
                if asyncio.current_task().cancelling():
                    raise
                continue  # the participant started speaking; retry when idle
            except Exception:
                await asyncio.sleep(30)
                continue
            with suppress(Exception):
                self.spoken_audio.put(engine, variant["text_sha256"], chunks)

    def pause_checks(self):
        # Foreground work has priority on the local GPU. A paused check stays queued and resumes
        # after the next reply; it is never silently dropped. Tibi's checks use their own model, so
        # they keep running while the participant speaks and pause only when a reply is prepared.
        product_check = getattr(self, "product_check", None)
        if product_check and not product_check.done():
            product_check.cancel()

    def queue_check(self, text, reply, generation):
        self.pending_checks.append((text, reply, generation))
        self.kick_checks()

    def kick_checks(self):
        running = getattr(self, "product_check", None)
        if self.pending_checks and not self.closed and not (running and not running.done()):
            self.product_check = self.task(self.run_checks())

    async def run_checks(self):
        # After speech, and only while the participant is not speaking. An interruption cancels
        # the running check; it stays at the head of the queue and resumes after the next reply.
        while self.pending_checks and not self.closed:
            text, reply, generation = self.pending_checks[0]
            await self.check_product_turn(text, reply, generation)
            self.pending_checks.pop(0)

    async def check_product_turn(self, text, reply, generation, check=None):
        # Runs after speech so evidence inference does not compete with synthesis.
        if check is None:
            try:
                check = await self.companion.review(text, reply)
            except asyncio.CancelledError:
                raise
            except Exception:
                check = {"status": "unavailable", "ids": [], "quote": "", "question": ""}
        if self.closed and check["status"] != "unavailable":
            return
        check = {**check, "generation": generation, "user": text, "reply": reply}

        def change(saved):
            saved.setdefault("knowledge_checks", []).append(check)
            return check

        self.session = self.store.update(self.session["id"], self.session["revision"], "product_evidence_check", change)
        self.companion.review_findings = [c for c in self.session['knowledge_checks']
                                         if c['status'] == 'possible_conflict'][-2:]
        await self.emit("snapshot", session=self.session)
        await self.emit("knowledge_check", check=check)

    async def social_response(self, action):
        # Validate after acquiring the audio floor: an acknowledgement waiting
        # behind another utterance is frequently no longer appropriate.
        async with self.speech_lock:
            if self.paused or not self.listener.valid(action, self.generation, time.monotonic()):
                return
            self.listener.committed(action, time.monotonic())
            state = self.listener.snapshot()

            def change(session):
                session["listener"] = state
                return {"action": action.kind, "spoken": bool(action.text), "quiet": state["quiet"]}

            self.session = self.store.update(self.session["id"], self.session["revision"], "listener_action", change)
            await self.emit("snapshot", session=self.session)
            await self.emit("listener_action", action=action.kind, spoken=bool(action.text))
            if action.text:
                await self._speak(action.text, cue=True, cue_chunks=self.social_audio.get(action.text))

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
            recognised = spoken(result.get("text", ""))
            control = command(recognised) != "none" or social_intent(recognised)
            text = recognised if control else normal(" ".join([*self.continuation, recognised]))
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
                if self.tibi and not self.tibi_preview and (not self.prewarm or self.prewarm.done()):
                    # Mid-utterance: cache the likely evidence prompt while the participant is still talking.
                    self.prewarm = self.task(self.tibi.prewarm(text))
                return
            if self.tibi and command(recognised) == "none":
                # Prepare the reply (and its first audio) during the pause; nothing is spoken,
                # committed or saved unless the final transcript matches exactly.
                if not (self.tibi_preview and self.tibi_preview["text"] == text):
                    self.cancel_tibi_preview()
                    self.pause_checks()
                    if self.prewarm and not self.prewarm.done():
                        self.prewarm.cancel()  # Ollama frees its queue promptly on cancellation
                    self.tibi_preview = {"text": text, "turn": self.tibi.begin(text, speculative=True),
                                         "generation": generation, "audio": {}}
                    self.tibi_preview["feeder"] = self.task(self.prepare_preview(self.tibi_preview))
                return
            if self.listener_only or social_intent(recognised):
                # A partial can still grow into a factual answer: do not act yet.
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
            # A live partial is provisional, even when it includes the last VAD
            # speech frame. Decode the full utterance again for the final wording.
            await self.emit("state", state="transcribing", message="Checking the complete wording…")
            recognise = getattr(self.asr, "final", self.asr.infer)
            heard = self.last_recognition
            # Tibi: a settled partial that already covers every voiced sample is the final wording;
            # re-decoding it cost 0.2-0.5 s while the GPU was preparing the reply.
            if (self.tibi and heard and heard["generation"] == generation
                    and heard["voice"] == self.markers.get("speech_end_sample")):
                result = heard["result"]
            else:
                result = await recognise(pcm)
            if generation != self.generation or self.paused:
                return
            recognised = spoken(result.get("text", ""))
            if not recognised and normal(result.get("text", "")):
                # Only background sound (music, noise) was captioned: nobody spoke, so nobody is answered.
                await self.emit("listener_action", action="ignored_sound", spoken=False)
                return
            control = command(recognised) != "none" or social_intent(recognised)
            text = recognised if control else normal(" ".join([*self.continuation, recognised]))
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
                if direct == "recap" and self.tibi:
                    await self.tibi_chat(recognised, generation)
                elif direct == "recap" and self.companion:
                    await self.social_chat(recognised, generation)
                elif direct == "recap":
                    await self.show_recap()
                else:
                    await self.pause("Paused. Your provisional wording is saved. Resume when ready.")
                return
            if self.tibi:
                await self.tibi_chat(text, generation)
                return
            if self.companion:
                await self.social_chat(recognised, generation)
                return
            if social_intent(recognised):
                self.practice_help_given = False
                if self.speculation:
                    self.speculation.cancel()
                if self.prepared_voice:
                    self.prepared_voice.cancel()
                    self.prepared_voice = None
                action = self.listener.decide(recognised, generation, time.monotonic())
                await self.social_response(action)
                return
            if self.listener_only:
                await self.emit("listener_handoff", message="That reply needs the conversation reasoner. "
                                "This practice only exercises listening requests; no factual answer was inferred or saved.")
                if not self.practice_help_given:
                    self.practice_help_given = True
                    await self.speak("This practice only responds to listening requests. Try asking me for a moment to think.")
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

    async def speak(self, text, allow_paused=False, prepared=None, cue=False, style=None):
        generation = self.generation
        async with self.speech_lock:
            if generation != self.generation or (self.paused and not allow_paused):
                return
            await self._speak(text, allow_paused, prepared, cue, style=style)

    async def _speak(self, text, allow_paused=False, prepared=None, cue=False, cue_chunks=None, style=None):
        generation = self.generation
        await self.emit("speech", text=text.replace("[chuckle] ", ""), cue=cue)
        index = 0
        # The existing speech grammar/grounding check has already checked generated questions.
        planned_delivery = (cue or getattr(self.speaker, "engine", "") in ("pocket", "chatterbox", "qwen_custom", "higgs", "higgs_female")
                            or (prepared and prepared.text == text))
        sentences = [text] if planned_delivery else re.split(r"(?<=[.!?])\s+", text)
        for sentence in sentences:
            if not sentence.strip():
                continue
            async def cached_cue():
                for chunk in (cue_chunks or []):
                    yield chunk
            chunks = (cached_cue() if cue else
                      prepared.stream() if prepared and prepared.text == text else
                      self.speaker.stream(sentence.strip(), style=style) if getattr(self.speaker, "engine", "") == "qwen_custom" else
                      self.speaker.stream(sentence.strip()))
            emitted = await self._emit_audio(chunks, generation, allow_paused, cue)
            if emitted is None:
                return
            index += emitted
        if generation == self.generation:
            await self.emit("audio_end")
        if cue:
            # asyncio.timeout, not wait_for: on Python 3.11 wait_for can swallow an
            # interruption's cancellation when the awaited event completes simultaneously.
            async with asyncio.timeout(15):
                await self.audio_empty.wait()
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
        if self.companion:
            await self.emit("state", state="warming", message="Preparing the local conversation model…")
            await self.companion.warm()
        elif self.defer_reviews and not self.listener_only:
            await self.warm_planner()
        self.sequence = -1
        self.samples = 0
        self.last_voice = 0
        self.voiced = 0
        self.recap = self.paused = False
        self.last_frame_at = time.monotonic()
        if not self.text_only:
            await self.vad.infer(b"")
        await self.emit("ready")

    async def close(self):
        self.closed = True
        self.interrupt()
        for task in tuple(self.work):
            task.cancel()
        await asyncio.gather(*self.work, return_exceptions=True)
        await asyncio.gather(self.asr.close(), self.vad.close(),
                             *([] if getattr(self.speaker, "shared", False) else [self.speaker.close()]))
        for text, reply, generation in self.pending_checks:
            # Recorded, never silently lost: the session ended before this check could run.
            with suppress(Exception):
                await self.check_product_turn(text, reply, generation, {
                    "status": "unavailable", "ids": [], "quote": "", "question": "",
                    "reason": "The session ended before the evidence check completed."})
        self.pending_checks.clear()
        for question_id, _, _ in self.deferred_reviews:
            if self.session["status"] == "active":
                self.session = self.store.audit_question(self.session, question_id, {
                    "verdict": "unavailable", "reason": "Session closed before queued question review completed."})
        self.deferred_reviews.clear()
        self.interviews.store.pause(self.session["id"], "disconnect")


def attach_conversation(app, runtime, token, interviews):
    owner = set()
    voices = {}

    async def resident_voice(engine):
        # One resident worker per voice across reconnections: a Higgs reload costs ~5 s and 12 GB.
        for other in [e for e in voices if e != engine]:
            await voices.pop(other).close()
        if engine not in voices:
            voices[engine] = SpeechWorker(engine, runtime)
            voices[engine].shared = True
        return voices[engine]

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
            practice = hello.get("listener_practice") is True or saved.get("listener_practice", False)
            if practice and (os.environ.get("SME_LISTENER_LAB") != "1"
                             or (saved.get("conversation") and not saved.get("listener_practice"))):
                raise Conflict("Start a fresh listener practice in the Charles candidate.")
            speaker = None
            if os.environ.get("SME_SOCIAL_CHAT") == "1":
                engine = social_voice_engine(saved, hello)
                if engine not in ("chatterbox", "qwen_custom", "pocket", "higgs", "higgs_female"):
                    raise ValueError("Unknown social voice")
                speaker = await resident_voice(engine)
            session = Conversation(runtime, interviews, saved, send, listener_only=practice,
                                   **({"speaker": speaker, "text_only": hello.get("text_only") is True} if speaker else {}))
            await session.start()
            while True:
                raw = await socket.receive_text()
                if len(raw) > 500_000:
                    raise ValueError("Oversized conversation message")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("Invalid message")
                kind = data.get("type")
                if kind == "social_text" and session.companion:
                    text = data.get("text")
                    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 1200:
                        raise ValueError("Invalid practice reply")
                    session.interrupt()
                    session.speech = False
                    session.frames.clear()
                    if command(text) == "pause":
                        await session.pause("Paused. Resume when you are ready.")
                    elif session.tibi:
                        session.reply = session.task(session.tibi_chat(text.strip(), session.generation))
                    else:
                        session.reply = session.task(session.social_chat(text.strip(), session.generation))
                elif kind == "frame":
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
        except Exception as exc:
            logging.getLogger(__name__).exception('Continuous voice startup or connection failed')
            with suppress(RuntimeError, WebSocketDisconnect):
                await send(
                    {"type": "error", "message": str(exc) if isinstance(exc, PreparationError) else
                     "Continuous voice is unavailable. Your saved text is safe; reopen the saved conversation to retry."}
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


def social_voice_engine(saved, hello):
    if os.environ.get("SME_SALES_VOICE") == "higgs":
        # Migrate older sales sessions to the selected family, preserving a
        # previously selected Higgs female voice when no new choice is supplied.
        selected = hello.get("social_voice") or saved.get("social_engine")
        return selected if selected in ("higgs", "higgs_female") else "higgs"
    return saved.get("social_engine") or hello.get("social_voice", "chatterbox")
