# ruff: noqa: E402
# Import application modules only after setting a disposable runtime and/or repository import path.
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
spec = importlib.util.spec_from_file_location("helpers", ROOT / "tests/test_sme_tibi.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
from services.opsatlas_sales.claims import unsupported
from services.sme_interviewer.evaluate_engine import check, precision
from services.sme_interviewer.tibi import EVIDENCE

record = {
    "id": "r",
    "title": "Deployment",
    "text": "OpsAtlas runs locally. Deployment to 10 teams takes 2 weeks.",
    "status": "available",
    "eligible": True,
    "sha256": "hash",
    "source_id": "s",
    "references": [],
}
probes = [
    ("question figure", "OpsAtlas deploys to 500 teams in 2 weeks.", record["text"], "Can OpsAtlas deploy to 500 teams?"),
    ("swapped relation", "Deployment to 2 teams takes 10 weeks.", record["text"], ""),
    ("fabricated capability", "We automate payroll.", record["text"], ""),
]
for name, s, e, q in probes:
    print(
        json.dumps(
            {
                "probe": name,
                "reply": s,
                "reasons": unsupported(s, e, q),
                "score_precision": precision(s, {"evidence": [record]}),
                "score_grounded": check("grounded", s, {"evidence": [record]}, {"say": q}, {}),
            }
        )
    )


async def fallback():
    t = m.make({EVIDENCE: ["OpsAtlas costs £999999."]}, {"What does OpsAtlas do?": [m.hit("r", 0.8)]}, records={"r": record})
    t.evidence.live_digest = "withdrawn"
    segments, result = await m.run(t, "What does OpsAtlas do?")
    print(
        json.dumps({"probe": "fallback after evidence withdrawn", "spoken": [x.text for x in segments], "grounding": result["grounding"]})
    )


asyncio.run(fallback())
