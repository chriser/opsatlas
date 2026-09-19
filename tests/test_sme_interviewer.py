"""Local audition safety and lifecycle checks without loading speech models."""

import array
import asyncio
import base64
import io
import math
import time
import wave

import pytest
from fastapi.testclient import TestClient

from services.sme_interviewer.app import MAX_BODY, TurnManager, audio_levels, create_app, trim_quiet_edges, validate_wave


def wav(frames=1600, channels=1, rate=16000, signal=False):
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(
            array.array("h", (int(3000 * math.sin(i / 10)) for i in range(frames * channels))).tobytes()
            if signal
            else b"\x00\x00" * frames * channels
        )
    return output.getvalue()


class FakeWorker:
    def __init__(self, engine, runtime):
        self.closed = False

    async def synthesize(self, candidate, text, output):
        await asyncio.sleep(0.01)
        output.write_bytes(wav())
        return {"total_ms": 10, "audio_seconds": 0.1}

    async def close(self):
        self.closed = True


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path, FakeWorker)
    with TestClient(app, base_url="http://127.0.0.1") as browser:
        browser.headers["x-sme-token"] = browser.get("/api/bootstrap").json()["token"]
        yield browser


def test_requires_local_origin_and_action_token(client):
    assert client.post("/api/turns", json={"candidate": "A", "text": "Hello"}, headers={"x-sme-token": "bad"}).status_code == 403
    assert client.get("/api/bootstrap", headers={"origin": "https://example.org"}).status_code == 403
    assert client.get("/api/bootstrap", headers={"host": "rebind.example"}).status_code == 400
    assert "frame-ancestors 'none'" in client.get("/").headers["content-security-policy"]


@pytest.mark.parametrize(
    "body",
    [
        {"candidate": [], "text": "Hello"},
        {"candidate": "A", "text": " "},
        {"candidate": "A", "text": "x" * 601},
        {"candidate": "X", "text": "Hello"},
    ],
)
def test_rejects_invalid_synthesis(client, body):
    assert client.post("/api/turns", json=body).status_code == 400


def test_body_and_sample_access_are_bounded(client):
    assert client.post("/api/transcribe", content=b"x" * (MAX_BODY + 1)).status_code == 413
    assert client.post("/api/transcribe", json={"wave": "bad!"}).status_code == 400
    assert client.get("/api/samples/A/unknown").status_code == 404
    assert client.get("/api/samples/A/%2e%2e%2fmodels").status_code == 404


@pytest.mark.parametrize("audio", [b"bad", wav(frames=1599), wav(frames=2880001), wav(channels=2), wav(rate=44100), wav()[:-4]])
def test_rejects_invalid_recordings(audio):
    with pytest.raises(ValueError):
        validate_wave(audio)


def test_valid_recording():
    assert validate_wave(wav()) == 0.1


def test_ready_audio_is_removed_on_cancel(client):
    job = client.post("/api/turns", json={"candidate": "A", "text": "Synthetic phrase"}).json()
    for _ in range(100):
        result = client.get(f"/api/turns/{job['id']}").json()
        if result["state"] == "ready":
            break
        time.sleep(0.01)
    assert result["state"] == "ready"
    assert "path" not in result
    assert client.get(f"/api/turns/{job['id']}/audio").status_code == 200
    assert client.post(f"/api/turns/{job['id']}/cancel").json()["state"] == "cancelled"
    assert client.get(f"/api/turns/{job['id']}/audio").status_code == 404


def test_running_cancel_and_single_active_turn(tmp_path):
    async def scenario():
        entered = asyncio.Event()
        cancelled = asyncio.Event()

        class SlowWorker(FakeWorker):
            async def synthesize(self, candidate, text, output):
                entered.set()
                try:
                    await asyncio.Future()
                except asyncio.CancelledError:
                    cancelled.set()
                    raise

        manager = TurnManager(tmp_path, SlowWorker)
        job = manager.create("A", text="Example")
        await entered.wait()
        with pytest.raises(Exception) as error:
            manager.create("B", text="Second request")
        assert error.value.status_code == 409
        await manager.cancel(job["id"])
        assert cancelled.is_set()
        assert manager.jobs[job["id"]]["state"] == "cancelled"
        await manager.close()
        assert all(worker.closed for worker in manager.workers.values())

    asyncio.run(scenario())


@pytest.mark.parametrize("cancel", [False, True])
def test_microphone_temporary_file_removed(tmp_path, cancel):
    async def scenario():
        paths = []
        entered = asyncio.Event()

        async def recognize(runtime, path):
            assert path.read_bytes() == wav()
            paths.append(path)
            entered.set()
            if cancel:
                await asyncio.Future()
            return "A draft transcript."

        manager = TurnManager(tmp_path, FakeWorker, recognize)
        job = manager.create("A", audio=wav())
        await entered.wait()
        if cancel:
            await manager.cancel(job["id"])
            assert "text" not in manager.jobs[job["id"]]
        else:
            await manager.jobs[job["id"]]["task"]
            assert manager.jobs[job["id"]]["text"] == "A draft transcript."
        assert not paths[0].exists()
        assert not paths[0].parent.exists()
        await manager.close()

    asyncio.run(scenario())


def test_recognition_does_not_trigger_synthesis(tmp_path):
    async def recognize(runtime, path):
        return "Reviewed separately"

    class MustNotSpeak(FakeWorker):
        async def synthesize(self, *args):
            raise AssertionError("Transcription must not generate speech")

    with TestClient(create_app(tmp_path, MustNotSpeak, recognize), base_url="http://127.0.0.1") as browser:
        browser.headers["x-sme-token"] = browser.get("/api/bootstrap").json()["token"]
        job = browser.post("/api/transcribe", json={"wave": base64.b64encode(wav(signal=True)).decode()}).json()
        for _ in range(100):
            result = browser.get(f"/api/turns/{job['id']}").json()
            if result["state"] != "running":
                break
            time.sleep(0.01)
        assert result["text"] == "Reviewed separately"
        assert browser.get(f"/api/turns/{job['id']}/audio").status_code == 404


def test_expiry_removes_transcript_and_audio(tmp_path):
    async def scenario():
        manager = TurnManager(tmp_path, FakeWorker)
        job = manager.create("A", text="A synthetic phrase")
        await manager.jobs[job["id"]]["task"]
        path = manager.jobs[job["id"]]["path"]
        assert path.exists()
        manager.jobs[job["id"]]["created"] -= 601
        manager.prune()
        assert not path.exists()
        assert not manager.jobs
        await manager.close()

    asyncio.run(scenario())


def test_duplicate_cancel_does_not_release_active_slot_before_worker_exit(tmp_path):
    async def scenario():
        entered, cleaning, released = asyncio.Event(), asyncio.Event(), asyncio.Event()

        class SlowCleanup(FakeWorker):
            async def synthesize(self, candidate, text, output):
                entered.set()
                try:
                    await asyncio.Future()
                except asyncio.CancelledError:
                    cleaning.set()
                    await released.wait()
                    raise

        manager = TurnManager(tmp_path, SlowCleanup)
        job = manager.create("B", text="Synthetic")
        await entered.wait()
        first = asyncio.create_task(manager.cancel(job["id"]))
        await cleaning.wait()
        second = asyncio.create_task(manager.cancel(job["id"]))
        await asyncio.sleep(0)
        assert manager.jobs[job["id"]]["state"] == "cancelling"
        assert not second.done()
        with pytest.raises(Exception) as error:
            manager.create("C", text="Must wait")
        assert error.value.status_code == 409
        released.set()
        await asyncio.gather(first, second)
        await manager.close()

    asyncio.run(scenario())


def test_silent_microphone_is_rejected_before_recognition(client):
    response = client.post("/api/transcribe", json={"wave": base64.b64encode(wav(frames=480000)).decode()})
    assert response.status_code == 400
    assert "No usable microphone signal" in response.json()["detail"]
    assert not client.app.state.manager.jobs


def test_long_recording_and_signal_metrics():
    audio = wav(frames=16000 * 45, signal=True)
    assert validate_wave(audio) == 45
    levels = audio_levels(audio)
    assert levels["audio_seconds"] == 45
    assert -25 < levels["rms_dbfs"] < -20
    assert validate_wave(wav(frames=16000 * 180)) == 180


def test_one_word_long_recording_is_flagged_for_review(tmp_path):
    async def scenario():
        async def recognize(runtime, path):
            return "you"

        manager = TurnManager(tmp_path, FakeWorker, recognize)
        job = manager.create("A", audio=wav(frames=16000 * 30, signal=True))
        await manager.jobs[job["id"]]["task"]
        result = manager.jobs[job["id"]]
        assert result["text"] == "you"
        assert result["audio_seconds"] == 30
        assert "Very few words" in result["warning"]
        await manager.close()

    asyncio.run(scenario())


def test_quiet_edges_trim_without_removing_speech_or_padding():
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * (35 * 16000) + b"\xe8\x03" * 16000 + b"\0\0" * 16000)
    trimmed, metrics = trim_quiet_edges(output.getvalue())
    assert metrics["trimmed_leading_seconds"] == 34.75
    assert validate_wave(trimmed) == 1.5
    with wave.open(io.BytesIO(trimmed), "rb") as audio:
        content = audio.readframes(audio.getnframes())
    assert content[4000 * 2 : 20000 * 2] == b"\xe8\x03" * 16000
