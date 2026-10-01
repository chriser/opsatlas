# ruff: noqa: E402
# Import application modules only after setting a disposable runtime and/or repository import path.
import asyncio
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
spec = importlib.util.spec_from_file_location("h", ROOT / "tests/test_sme_continuous_tibi.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
from services.opsatlas_sales import conversations
from services.sme_interviewer.tibi import CONVERSATION, EVIDENCE


async def main():
    root = Path(tempfile.mkdtemp(prefix="tibi-audit-")).resolve()
    c, events, t, speaker = h.setup(
        root / "speculation", {EVIDENCE: ["OpsAtlas combines approved document retrieval with structured knowledge."]}
    )
    question = "What is OpsAtlas used for?"
    c.tibi_preview = {"text": question, "turn": t.begin(question, speculative=True), "generation": c.generation, "audio": {}}
    c.tibi_preview["feeder"] = c.task(c.prepare_preview(c.tibi_preview))
    await c.tibi_preview["feeder"]
    await c.tibi_preview["turn"].task
    t.evidence.live = "withdrawn-after-preparation"
    await c.tibi_chat(question, c.generation)
    print(
        json.dumps(
            {
                "probe": "evidence withdrawn after speculative preparation",
                "speech_events": [e["text"] for e in events if e["type"] == "speech"],
                "audio_chunks": sum(e["type"] == "audio_chunk" for e in events),
            }
        )
    )
    await c.close()
    c, events, t, speaker = h.setup(root / "interrupt", {CONVERSATION: ["OK\n", "Ready to listen. ", "How is your day?"]})
    c.conversation_log = root / "logs"
    original = c._emit_audio

    async def emit(chunks, generation, **kwargs):
        await original(chunks, generation, **kwargs)
        c.generation += 1
        return None

    c._emit_audio = emit
    await c.tibi_chat("Hello, how are you?", c.generation)
    print(
        json.dumps(
            {
                "probe": "ordinary turn interrupted after audio emitted",
                "audio_chunks": sum(e["type"] == "audio_chunk" for e in events),
                "logged_turns": len(conversations.turns(c.conversation_log)),
                "saved_transcript": c.interviews.store.get(c.session["id"]).get("social_transcript", []),
            }
        )
    )
    await c.close()


asyncio.run(main())
