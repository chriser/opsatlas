"""Exploratory multi-turn regression against local Ollama; fictional data only."""

import asyncio
import json
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .dialogue import MODEL, POLICY, LocalPlanner
from .evidence import FixtureEvidence
from .ledger import Ledger

STORY = (
    "A buyer requested a new supplier using a form with the company name, bank details and tax number. "
    "The buyer handed the completed form to Finance. Finance made the final activation decision. "
    "The required checks were a bank-account match and a tax-number check. "
    "We recorded the decision in the ERP. This was the usual UK standard route on 1 September 2026, using process version 3."
)
KNOWN = {"request_start", "required_inputs", "handoffs", "decision_owner", "required_checks", "record_location",
         "usual_or_exception", "region", "process_date"}
ANSWERS = {
    "decision_criteria": "I proceeded only when both check results were green and the approval reference was present.",
    "warning_signs": "A mismatch between the bank account name and company name would make me stop and investigate.",
    "record_changes": "I changed the supplier record from on hold to active after the approval was recorded.",
    "check_evidence": "The ERP kept timestamped check reports with pass results and the checker identity.",
    "exception_conditions": "An urgent request with incomplete checks required the emergency route and escalation.",
}


async def run():
    planner, turns, errors = LocalPlanner(), [], []
    with tempfile.TemporaryDirectory(prefix="sme-contextual-probe-") as directory:
        store = Ledger(Path(directory) / "ledger.sqlite")
        session = store.create(FixtureEvidence().snapshot(), {"region": "unknown", "variant": "unknown", "date": ""}, str(uuid.uuid4()))

        def save(text):
            nonlocal session
            session = store.mutate(session["id"], session["revision"], str(uuid.uuid4()), "segment_saved",
                                   {"text": text, "kind": "reported_practice", "state": "confirmed"})

        answered = set(KNOWN)
        for turn in range(9):
            session = store.mutate(session["id"], session["revision"], str(uuid.uuid4()), "plan_requested", {})
            start = time.perf_counter()
            plan = await planner.plan(session)
            seconds = round(time.perf_counter() - start, 3)
            store.apply_plan(session["id"], session["revision"], plan)
            session = store.get(session["id"])
            detail = plan.get("detail")
            checks = {
                "not_already_answered": detail not in answered,
                "grounded_current_anchor": not plan.get("anchor") or any(
                    s["id"] == plan["anchor"]["segment_id"] and s["revision"] == plan["anchor"]["segment_revision"]
                    and plan["anchor"]["quote"] in s["text"] for s in session["segments"]),
                "speech_length": len(plan["text"]) <= 600,
                "model_available_after_sequence": turn < 2 or plan["mode"] == "local_model",
                "no_premature_review": plan["question"] != "review" or set(ANSWERS) <= answered,
            }
            turns.append({"turn": turn, "seconds": seconds, "plan": plan, "checks": checks})
            print(turn, plan["mode"], detail or plan["question"], seconds, checks, flush=True)
            errors.extend(f"turn {turn}: {key}" for key, passed in checks.items() if not passed)
            if turn == 0:
                save(STORY)
            elif turn == 1:
                save("Yes, that sequence is correct.")
            elif detail in ANSWERS:
                save(ANSWERS[detail])
                answered.add(detail)
            elif detail:
                break  # Repeated or unexpected detail: retain evidence, fail below.
            elif plan["question"] == "hypothetical":
                save("I do not know. I would leave that hypothetical point open for the process owner.")
            elif plan["question"] == "followup":
                save("The process owner could confirm the arrangement.")
            else:
                break
    async with httpx.AsyncClient(trust_env=False, timeout=5) as client:
        tags = (await client.get("http://127.0.0.1:11434/api/tags")).json()
    model_digest = next(m["digest"] for m in tags["models"] if m["name"] == MODEL)
    report = {"model_digest": model_digest, "at": datetime.now(timezone.utc).isoformat(), "policy": POLICY, "model": MODEL,
              "purpose": "Development probe, not held-out G2 acceptance. Human-rated relevance remains required.",
              "story": STORY, "answers": ANSWERS, "turns": turns, "failures": errors}
    path = Path(__file__).parent / ".runtime/contextual-evaluation.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(path)
    if errors:
        raise SystemExit("; ".join(errors))


if __name__ == "__main__":
    asyncio.run(run())
