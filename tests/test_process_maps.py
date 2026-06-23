"""Process-map export tests."""

from __future__ import annotations

import io
import json
import zipfile

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.ingestion.service import ingest_source
from assistant.ingestion.store import SectionStore
from assistant.process.lucid import (
    LUCID_CREATE_ENDPOINT,
    LucidSettings,
    build_lucid_archive,
    build_lucid_standard_import,
    create_lucid_document,
)
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


def test_process_map_includes_lucid_ready_fields_and_mermaid():
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


def test_lucid_standard_import_includes_process_map_shapes_and_lines():
    record = parse_process("p1", "Launch pack", PACK)
    draft = build_process_map(record)

    document = build_lucid_standard_import(draft)
    page = document["pages"][0]
    shapes_by_id = {shape["id"]: shape for shape in page["shapes"]}
    lines_by_id = {line["id"]: line for line in page["lines"]}

    assert document["version"] == 1
    assert document["documentSettings"] == {"units": "px"}
    assert page["customData"][0] == {"key": "process_id", "value": "p1"}
    assert shapes_by_id["step_1"]["type"] == "bpmnActivity"
    assert shapes_by_id["step_1"]["taskType"] == "manual"
    assert shapes_by_id["step_2"]["customData"][-1] == {"key": "confidence", "value": "high"}
    assert shapes_by_id["controls_block"]["type"] == "stickyNote"
    assert shapes_by_id["systems_block"]["text"].startswith("<b>Systems</b>")
    assert shapes_by_id["decision_1"]["type"] == "decision"
    assert lines_by_id["flow_1"]["endpoint1"]["shapeId"] == "step_1"
    assert lines_by_id["flow_1"]["endpoint2"]["shapeId"] == "step_2"


def test_lucid_archive_contains_document_json():
    record = parse_process("p1", "Launch pack", PACK)
    draft = build_process_map(record)

    archive_bytes = build_lucid_archive(draft)

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        assert archive.namelist() == ["document.json"]
        document = json.loads(archive.read("document.json").decode("utf-8"))
    assert document["pages"][0]["title"] == "Store Launch Process"


def test_create_lucid_document_posts_standard_import_multipart():
    record = parse_process("p1", "Launch pack", PACK)
    draft = build_process_map(record)
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"documentId":"doc-123","editUrl":"https://lucid.app/lucidchart/doc-123/edit"}'

    def fake_opener(req, timeout):
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(req.headers)
        captured["body"] = req.data
        return FakeResponse()

    result = create_lucid_document(
        draft,
        LucidSettings(api_key="secret", parent_folder_id="1234"),
        opener=fake_opener,
    )

    assert captured["url"] == LUCID_CREATE_ENDPOINT
    assert captured["timeout"] == 45
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert b'name="product"\r\n\r\nlucidchart\r\n' in captured["body"]
    assert b'name="parent"\r\n\r\n1234\r\n' in captured["body"]
    assert b'filename="Store-Launch-Process.lucid"' in captured["body"]
    assert result["document_id"] == "doc-123"
    assert result["edit_url"].endswith("/edit")


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


def test_lucid_endpoints_download_archive_and_report_config(tmp_path, monkeypatch):
    monkeypatch.delenv("LUCID_API_KEY", raising=False)
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    client = TestClient(create_app(reg, AuthService("pw"), retrieval=RetrievalService(reg, store)))
    token = client.post("/api/auth/login", json={"password": "pw"}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    rec = register_upload(reg, "launch.md", PACK.encode(), title="Launch pack")
    ingest_source(reg, store, rec.id)
    reg.update(rec.id, approval_status="approved")

    config = client.get("/api/process/lucid/config").json()
    download = client.get(f"/api/process/maps/{rec.id}/lucid-import")
    create = client.post(f"/api/process/maps/{rec.id}/lucid")

    assert config["configured"] is False
    assert config["missing"] == ["LUCID_API_KEY"]
    assert download.status_code == 200
    assert download.headers["content-disposition"].endswith('.lucid"')
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        assert "document.json" in archive.namelist()
    assert create.status_code == 503
