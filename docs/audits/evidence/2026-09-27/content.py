# ruff: noqa: E402
# Import application modules only after setting a disposable runtime and/or repository import path.
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
os.environ["KP_DATA_DIR"] = tempfile.mkdtemp(prefix="audit-data-")
os.environ["SALES_GOVERNANCE_AUTO_REVIEW"] = "0"
os.environ["SME_TIBI_VOICE_URL"] = "http://127.0.0.1:9"
from fastapi.testclient import TestClient

from services.opsatlas_sales.app import create_sales_app

root = Path(tempfile.mkdtemp(prefix="opsatlas-content-audit-")).resolve()
app = create_sales_app(root)
app.state.retrieval.embedder = None
with TestClient(app) as c:
    token = c.post("/api/auth/login", json={"password": (root / "local-access.key").read_text().strip()}).json()["token"]
    c.headers.update({"Authorization": "Bearer " + token})
    rows = c.get("/api/tibi/knowledge").json()["records"]
    r = next(r for r in rows if any(app.state.register.get(ref["source_id"]).filename.endswith(".md") for ref in r["references"]))
    ref = next(ref for ref in r["references"] if app.state.register.get(ref["source_id"]).filename.endswith(".md"))
    before = c.post(f"/api/tibi/knowledge/{r['id']}/review", json={"expected_hash": r["sha256"], "approve": True}).json()
    digest_before = app.state.sales.digest()
    sid = ref["source_id"]
    draft = c.put(
        f"/api/content/documents/{sid}/draft",
        json={
            "text": "# Withdrawn evidence\n\nThe previous claims are withdrawn. This document no longer supports any product capability.\n"
        },
    ).json()
    c.post(f"/api/content/documents/{sid}/submit", json={"note": "Synthetic audit probe"})
    result = c.post(f"/api/content/documents/{sid}/publish", json={"draft_sha": draft["draft"]["sha"]})
    after = next(x for x in c.get("/api/tibi/knowledge").json()["records"] if x["id"] == r["id"])
    print(
        json.dumps(
            {
                "probe": "published evidence withdrawn",
                "publish_status": result.status_code,
                "record": r["id"],
                "eligible_before": before["eligible"],
                "eligible_after": after["eligible"],
                "record_wording_unchanged": r["text"] == after["text"],
                "reference_hash_changed": r["references"] != after["references"],
                "digest_unchanged": digest_before == app.state.sales.digest(),
            }
        )
    )
