"""Process-map export tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.ingestion.service import ingest_source
from assistant.ingestion.store import SectionStore
from assistant.process.maps import build_process_map
from assistant.process.parser import parse_process
from assistant.retrieval.service import RetrievalService
from assistant.sources.register import SourceRegister
from assistant.sources.service import register_upload

PACK = """# Anonymised Learning Pack 9 - Store Launch Process

## 3. Roles and responsibilities

| Role | Responsibility |
|---|---|
| Launch owner | Owns the launch process. |
| Finance owner | Confirms readiness. |

## 4. Key business rules

- Launch must not proceed until finance readiness is complete.
- Requires validation: exception ownership needs confirmation.

## 5. Systems and data dependencies

| System / dependency | Purpose | Key data | Notes |
|---|---|---|---|
| Launch tracker | Tracks launch. | Launch ID. | n/a |
| Finance system | Confirms checks. | Finance ID. | n/a |

## 8. JSON-style learning records

```json
{"record_id":"LAUNCH_001","topic":"trigger","role":"launch_owner","rule":"launch owner opens the launch request","confidence":"high"}
{"record_id":"LAUNCH_002","topic":"gate","role":"finance_owner","rule":"finance owner confirms launch readiness","confidence":"high"}
```

## 9. Suggested tagging structure

- domain: store-launch
- process: launch-readiness
- dependency: finance-readiness
- control: launch-gating
"""


def test_process_map_includes_internal_fields_and_mermaid():
    record = parse_process("p1", "Launch pack", PACK)

    draft = build_process_map(record)

    assert draft.name == "Store Launch Process"
    assert draft.roles == ["Launch owner", "Finance owner"]
    assert draft.systems == ["Launch tracker", "Finance system"]
    assert draft.controls == ["launch-gating"]
    assert draft.dependencies == ["finance-readiness"]
    assert len(draft.steps) == 2
    assert draft.edges[0].source == "step_1" and draft.edges[0].target == "step_2"
    assert "flowchart TD" in draft.mermaid
    assert "Control: launch-gating" in draft.mermaid
    assert "Dependency: finance-readiness" in draft.mermaid


def test_process_map_endpoint_builds_from_approved_sources(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    client = TestClient(create_app(reg, AuthService("pw"), retrieval=RetrievalService(reg, store)))
    token = client.post("/api/auth/login", json={"password": "pw"}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    rec = register_upload(reg, "launch.md", PACK.encode(), title="Launch pack")
    ingest_source(reg, store, rec.id)
    reg.update(rec.id, approval_status="approved")

    maps = client.get("/api/process/maps").json()
    detail = client.get(f"/api/process/maps/{rec.id}").json()

    assert len(maps) == 1
    assert maps[0]["process_id"] == rec.id
    assert detail["mermaid"].startswith("flowchart TD")
    assert client.get("/api/process/maps/nope").status_code == 404
