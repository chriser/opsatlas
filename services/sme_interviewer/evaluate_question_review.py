"""Labelled development checks for question review; not held-out factual validation."""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .conversation import REVIEW_MODEL, review_question

CASES = [
    (
        "new-detail",
        "I kept the supplier on hold because the insurance certificate had expired.",
        "What would show that the certificate issue had been resolved?",
        "pass",
    ),
    (
        "invented-event",
        "I kept the supplier on hold because the insurance certificate had expired.",
        "Why did you activate the supplier despite the expired certificate?",
        "reject",
    ),
    ("already-answered", "Finance approved the supplier because all required checks passed.", "Who approved the supplier?", "reject"),
    ("unknown", "I do not know who approves emergency requests.", "Who approves emergency requests?", "reject"),
    ("unknown-source", "I do not know who approves emergency requests.", "Who could help us find out?", "pass"),
    (
        "hypothetical",
        "Hypothetically we could ask Operations to approve an urgent supplier. This has not happened.",
        "What would Operations need to check before approving it?",
        "pass",
    ),
    (
        "hypothetical-as-fact",
        "Hypothetically we could ask Operations to approve an urgent supplier. This has not happened.",
        "Why did Operations approve the supplier?",
        "reject",
    ),
    (
        "check-occurrence",
        "Finance confirmed the payment details matched; that was not permission to activate the supplier.",
        "Did the supplier activation actually happen?",
        "pass",
    ),
]

CASES += [
    ("unstated-proceeding", "I waited for Finance approval.",
     "Did you receive Finance approval before proceeding?", "reject"),
    ("awaited-approval", "The buyer sent the bank details by email and I waited for Finance approval.",
     "What happened next after Finance approval was granted?", "reject"),
    ("unstated-approval", "Finance confirmed the payment details matched; that was not permission to activate the supplier.",
     "Who approved the supplier activation after Finance gave the green light?", "reject"),
    (
        "unstated-subordinate-event",
        "I kept the supplier on hold and asked the buyer for a renewed certificate.",
        "Did the order proceed once the buyer provided the renewed certificate?",
        "reject",
    ),
    (
        "supplied-reason",
        "The shift lead released the supplier because the order was urgent.",
        "Why did the shift lead release the supplier?",
        "reject",
    ),
]


async def run():
    records = []
    async with httpx.AsyncClient(base_url="http://127.0.0.1:11434", timeout=12, trust_env=False) as client:
        for name, account, question, expected in CASES:
            started = time.perf_counter()
            try:
                result = await review_question(client, account, [], question)
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                result = {"error": type(exc).__name__}
            records.append(
                {
                    "case": name,
                    "account": account,
                    "question": question,
                    "expected": expected,
                    "result": result,
                    "seconds": round(time.perf_counter() - started, 3),
                    "correct": result.get("verdict") == expected,
                }
            )
            print(name, result.get("verdict", result.get("error")), records[-1]["correct"], flush=True)
    report = {
        "at": datetime.now(timezone.utc).isoformat(),
        "model": REVIEW_MODEL,
        "purpose": "Developer-labelled calibration cases. Not held-out G2 acceptance or proof of factual correctness.",
        "cases": records,
    }
    path = Path(__file__).parent / ".runtime/question-review-evaluation.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(path)
    if not all(row["correct"] for row in records):
        raise SystemExit("A question-review calibration case failed")


if __name__ == "__main__":
    asyncio.run(run())
