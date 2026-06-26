"""Main-app integration with the local process diagram microservice."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from assistant.api.routes_process import build_process_router
from assistant.ingestion.service import ingest_source
from assistant.ingestion.store import SectionStore
from assistant.process.diagram import ProcessDiagramClient, ProcessDiagramServiceError, build_diagram_payload
from assistant.process.maps import build_process_map
from assistant.process.registry import ProcessRegistry
from assistant.sources.register import SourceRegister
from assistant.sources.service import register_upload


def test_from_env_tolerates_invalid_timeout(monkeypatch):
    monkeypatch.setenv("PROCESS_DIAGRAM_TIMEOUT_SECONDS", "4s")  # invalid
    assert ProcessDiagramClient.from_env().timeout == 4  # falls back, does not raise
    monkeypatch.setenv("PROCESS_DIAGRAM_TIMEOUT_SECONDS", "9")
    assert ProcessDiagramClient.from_env().timeout == 9


def test_non_local_diagram_host_is_refused():
    # A non-loopback base URL must be refused before any request is made (SSRF guard).
    def fail_opener(*_args, **_kwargs):  # pragma: no cover - must not be called
        raise AssertionError("request should not be attempted for a non-local host")

    client = ProcessDiagramClient(base_url="http://169.254.169.254", opener=fail_opener)
    with pytest.raises(ProcessDiagramServiceError):
        client.health()

PACK = """# Supplier Setup Process

## 3. Roles and responsibilities

| Role | Responsibility |
|---|---|
| Buyer | Completes the supplier setup form. |
| Trading support | Reviews setup requests. |

## 4. Key business rules

- Due diligence and credit checks are gating controls.

## 5. Systems and data dependencies

| System / dependency | Purpose | Key data | Notes |
|---|---|---|---|
| Supplier master data tool | Supplier creation. | Supplier code. | n/a |

## 8. JSON-style learning records

```json
{"record_id":"SUP_001","topic":"trigger","role":"buyer","rule":"setup starts with a request","confidence":"high"}
{"record_id":"SUP_002","topic":"review","role":"trading_support","rule":"support reviews the setup request","confidence":"high"}
```

## 9. Suggested tagging structure

- `domain: supplier-onboarding`
- `process: supplier-setup`
- `control: credit-check`
"""


class FakeDiagramClient:
    base_url = "http://diagram-service.test"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.payloads: list[dict] = []

    def render(self, payload: dict) -> dict:
        if self.fail:
            raise ProcessDiagramServiceError("Diagram service unavailable: test")
        self.payloads.append(payload)
        return {
            "chart_id": "chart-1",
            "title": payload["process_model"]["title"],
            "nodes": [{"id": "step_1", "type": "task", "label": "setup", "x": 1, "y": 2}],
            "edges": [],
            "animation_steps": [],
            "narration_script": [],
        }

    def render_svg(self, payload: dict) -> str:
        if self.fail:
            raise ProcessDiagramServiceError("Diagram service unavailable: test")
        self.payloads.append(payload)
        return '<svg xmlns="http://www.w3.org/2000/svg"><text>Supplier Setup Process</text></svg>'


def _seed(tmp_path):
    register = SourceRegister(tmp_path)
    store = SectionStore(register.base_dir)
    record = register_upload(register, "supplier.md", PACK.encode(), title="Supplier setup")
    ingest_source(register, store, record.id)
    register.update(record.id, approval_status="approved")
    registry = ProcessRegistry(register.base_dir)
    registry.build_from_sources(register)
    return register, registry, record


def _client(tmp_path, diagram_client) -> TestClient:
    register, registry, _ = _seed(tmp_path)
    app = FastAPI()
    app.include_router(build_process_router(register, registry, diagram_client=diagram_client))
    return TestClient(app)


def test_process_map_payload_targets_local_diagram_service_schema(tmp_path):
    _, registry, _ = _seed(tmp_path)
    draft = build_process_map(registry.list()[0])

    payload = build_diagram_payload(draft)

    assert payload["style"] == "plain"
    assert payload["process_model"]["title"] == "Supplier Setup Process"
    assert {"id": "buyer", "type": "lane", "label": "buyer"} in payload["process_model"]["nodes"]
    assert any(node["type"] == "control" and node["label"] == "credit-check" for node in payload["process_model"]["nodes"])
    assert payload["process_model"]["edges"][0]["from"] == "step_1"


def test_resolve_process_diagram_returns_available_chart_for_matched_question(tmp_path):
    fake = FakeDiagramClient()
    client = _client(tmp_path, fake)

    response = client.post("/api/process/diagrams/resolve", json={
        "question": "Who reviews the supplier setup request?",
        "citations": [],
    })

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "available"
    assert body["process_name"] == "Supplier Setup Process"
    assert body["service_url"] == "http://diagram-service.test"
    assert body["svg"].startswith("<svg")
    assert fake.payloads[0]["process_model"]["title"] == "Supplier Setup Process"


def test_process_diagram_endpoint_returns_available_chart_by_process_id(tmp_path):
    fake = FakeDiagramClient()
    register, registry, record = _seed(tmp_path)
    app = FastAPI()
    app.include_router(build_process_router(register, registry, diagram_client=fake))
    client = TestClient(app)

    response = client.get(f"/api/process/diagrams/{record.id}")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "available"
    assert body["process_id"] == record.id
    assert body["process_name"] == "Supplier Setup Process"
    assert body["svg"].startswith("<svg")
    assert fake.payloads[0]["process_model"]["title"] == "Supplier Setup Process"


def test_resolve_process_diagram_falls_back_to_citation_source_match(tmp_path):
    fake = FakeDiagramClient()
    register, registry, record = _seed(tmp_path)
    app = FastAPI()
    app.include_router(build_process_router(register, registry, diagram_client=fake))
    client = TestClient(app)

    response = client.post("/api/process/diagrams/resolve", json={
        "question": "What visual context applies here?",
        "citations": [{"source_id": record.id, "source_title": "Supplier setup", "heading": "Overview", "ordinal": 1}],
    })

    assert response.json()["status"] == "available"


def test_resolve_process_diagram_returns_unavailable_without_breaking_answer_context(tmp_path):
    client = _client(tmp_path, FakeDiagramClient(fail=True))

    response = client.post("/api/process/diagrams/resolve", json={
        "question": "Who reviews the supplier setup request?",
        "citations": [],
    })

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "unavailable"
    assert body["process_name"] == "Supplier Setup Process"
    assert "Diagram service unavailable" in body["message"]


def test_resolve_process_diagram_returns_empty_when_no_process_matches(tmp_path):
    client = _client(tmp_path, FakeDiagramClient())

    response = client.post("/api/process/diagrams/resolve", json={
        "question": "What is the weather today?",
        "citations": [],
    })

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "empty"
    assert body["chart"] is None
