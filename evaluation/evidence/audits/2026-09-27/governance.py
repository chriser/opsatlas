# ruff: noqa: E402
# Import application modules only after setting a disposable runtime and/or repository import path.
import hashlib
import importlib.util
import json
import sys
import tempfile
import threading
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from services.opsatlas_sales.ontology import ProductOntology

root = Path(tempfile.mkdtemp(prefix="governance-audit-")).resolve()
o = ProductOntology(root / "ontology.db")
record = {
    "id": "limitations",
    "title": "Updated limitations",
    "status": "available",
    "text": "The product now supports single sign-on.",
    "eligible": True,
    "sha256": "new-approved-hash",
    "source_id": "s",
}
o.ensure([record])
print(
    json.dumps(
        {"probe": "ontology after replacement approved record", "record_text": record["text"], "ontology_facts": o.overview("limitations")}
    )
)
spec = importlib.util.spec_from_file_location("h", ROOT / "tests/test_sales_statement_governance.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
desk, register, knowledge, _, _ = h.sales.__wrapped__(root / "stale")
desk.statements.run()
conflict = next(i for i in desk.agenda()["items"] if i.get("relation") == "conflict")
keep = "a" if conflict["statements"][0]["record_id"] == "security" else "b"
answer = desk.propose(
    {
        "issue_key": conflict["key"],
        "contributor": "Chris",
        "session_id": "s",
        "answer": "The security record is correct; withdraw the conflicting claim.",
        "resolution": {"decision": "supersede", "keep": keep},
    }
)
rows = knowledge.records()
claim = next(r for r in rows if r["id"] == "sso-claim")
claim["text"] = "The proof of concept does not support single sign-on with a corporate directory today."
body = ("# " + claim["title"] + "\n\n" + claim["text"] + "\n").encode()
claim["sha256"] = hashlib.sha256(body).hexdigest()
knowledge._save(rows)
register.write_content(claim["source_id"], body)
register.update(claim["source_id"], content_sha256=claim["sha256"], version=2, approval_status="approved")
h.ingest_source(register, desk.sections, claim["source_id"])
stale = any(x["relation"] == "conflict" for x in desk.statements.findings())
desk.review(answer["id"], answer["text_sha256"], True)
print(
    json.dumps(
        {
            "probe": "old resolution approved after contradictory record corrected",
            "stale_finding_still_visible": stale,
            "corrected_record_approval_after": register.get(claim["source_id"]).approval_status,
        }
    )
)
started = threading.Event()
release = threading.Event()
calls = []


def fake_run(progress=None):
    calls.append(1)
    started.set()
    release.wait(2)
    return {}


desk.statements.run = fake_run
desk.statements.start()
started.wait(1)
desk.statements.start()
release.set()
desk.statements.thread.join(3)
print(
    json.dumps(
        {
            "probe": "review requested during active run",
            "requested_runs": 2,
            "executed_runs": len(calls),
            "final_status": desk.statements.state["status"],
        }
    )
)
