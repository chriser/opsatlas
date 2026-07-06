"""Enterprise Activity Model API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister
from assistant.sources.service import register_upload

PASSWORD = "eam-test-pass"


def test_eam_api_is_auth_protected_and_returns_model_taxonomy_and_svg(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KP_DATA_DIR", str(tmp_path))
    register = SourceRegister(tmp_path)
    _seed_approved_process_sources(register)
    client = TestClient(create_app(register, AuthService(PASSWORD)))

    assert client.get("/api/eam/model").status_code == 401
    assert client.get("/api/eam/taxonomy").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    before = client.get("/api/ontology/stats", headers=headers).json()

    taxonomy = client.get("/api/eam/taxonomy", headers=headers)
    assert taxonomy.status_code == 200
    assert taxonomy.json()["version"] == "eam-taxonomy.v1"
    assert len(taxonomy.json()["domains"]) == 12

    model = client.get("/api/eam/model", headers=headers)
    assert model.status_code == 200
    body = model.json()
    assert body["process_count"] == 2
    assert body["taxonomy_version"] == "eam-taxonomy.v1"
    assert body["coverage"]["score"] >= 0
    assert body["finding_counts"]["gap"] >= 1
    assert body["meta"]["domain_count"] == 12

    svg = client.get("/api/eam/svg", headers=headers)
    assert svg.status_code == 200
    assert svg.headers["content-type"].startswith("image/svg+xml")
    assert "Enterprise Activity Model" in svg.text
    assert "Activity canvas route ready" not in svg.text
    assert 'data-node-id="process:' in svg.text

    unsupported = client.get("/api/eam/svg", params={"view": "risk"}, headers=headers)
    assert unsupported.status_code == 400

    after = client.get("/api/ontology/stats", headers=headers).json()
    assert after["total_objects"] == before["total_objects"]
    assert after["total_links"] == before["total_links"]


def _seed_approved_process_sources(register: SourceRegister) -> None:
    first = register_upload(register, "ordering.md", _process_doc("Supplier Ordering", "ordering").encode(), title="Supplier Ordering")
    second = register_upload(register, "ranging.md", _process_doc("Article Ranging", "ranging").encode(), title="Article Ranging")
    register.update(first.id, approval_status="approved")
    register.update(second.id, approval_status="approved")


def _process_doc(title: str, domain: str) -> str:
    return f"""# {title}

## Roles and responsibilities

| Role | Responsibility |
|---|---|
| Data owner | Approves readiness |

## Systems and data dependencies

| System | Purpose |
|---|---|
| Operational master data tool | Publishes approved setup downstream |

## Structured process steps

| Step | Activity | Role | What happens | Output | Validation |
|---|---|---|---|---|---|
| 1 | Validate setup | Data owner | Mandatory fields are checked | Ready record | Readiness gate |

## Key business rules

- Activation waits for validation before release.

## Suggested tagging structure

- domain: {domain}
- capability: operating model projection
- control: Readiness gate
"""
