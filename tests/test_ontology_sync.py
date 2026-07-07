"""Ontology rebuild/sync tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from assistant.api.auth import AuthService
from assistant.compliance.latest import ComplianceLatestReviewStore
from assistant.ontology import OntologyStore, ontology_id, rebuild_ontology
from assistant.process.registry import ProcessRegistry
from assistant.sources.register import SourceRegister
from assistant.sources.service import register_upload

PASSWORD = "test-pass"


def test_rebuild_populates_sources_processes_deduped_entities_and_compliance_links(tmp_path) -> None:
    register = SourceRegister(tmp_path)
    first_id, second_id = _seed_approved_process_sources(register)
    process_registry = ProcessRegistry(register.base_dir)
    compliance_latest = ComplianceLatestReviewStore(register.base_dir)
    compliance_latest.save(
        status={"job_id": "cr-ontology", "status": "completed", "review_mode": "external_vs_internal"},
        findings=[
            {
                "id": "finding-vat-1",
                "classification": "contradiction",
                "severity": "high",
                "rationale": "Internal guidance conflicts with VAT records retention.",
                "alignment_score": 0.82,
                "obligation_id": "vat-records-obligation",
                "internal_claim_id": "supplier-records-claim",
                "external_evidence": {
                    "source_id": "external-vat-notice",
                    "source_title": "VAT Notice 700",
                    "section_id": "10.6",
                    "heading": "Input tax records",
                    "text": "You must keep VAT invoice records.",
                    "url": "https://www.gov.uk/guidance/vat-guide-notice-700",
                    "content_sha256": "abc123",
                },
                "internal_evidence": {
                    "source_id": first_id,
                    "source_title": "Supplier Setup",
                    "section_id": f"{first_id}-rules",
                    "heading": "Key business rules",
                    "text": "Finance teams may delete supplier VAT invoice records after onboarding.",
                },
            }
        ],
    )
    store = OntologyStore(tmp_path / "ontology.db")

    first_result = rebuild_ontology(register, process_registry, compliance_latest, store)
    second_result = rebuild_ontology(register, process_registry, compliance_latest, store)

    assert second_result["counts"] == first_result["counts"]
    assert second_result["counts"]["objects"] == {
        "compliance_finding": 1,
        "control": 1,
        "internal_claim": 1,
        "obligation": 1,
        "process": 2,
        "role": 1,
        "source": 3,
        "system": 1,
    }
    assert second_result["counts"]["links"]["process_has_role"] == 2
    assert second_result["counts"]["links"]["process_uses_system"] == 2
    assert second_result["counts"]["links"]["process_enforced_by"] == 2
    assert second_result["counts"]["links"]["finding_affects_process"] == 1

    role = store.find("role", {"normalized_name": "finance approver"})[0]
    using_role = store.traverse(role.id, "process_has_role", direction="in")
    assert {item.properties["name"] for item in using_role} == {"Supplier Setup", "Article Setup"}

    supplier_process = store.get(ontology_id("process", first_id))
    assert supplier_process is not None
    assert any(
        fact == "Role responsibility: Finance approver - Approves readiness."
        for fact in supplier_process.properties["key_facts"]
    )
    assert any("Contracts must be checked before downstream use." in fact for fact in supplier_process.properties["key_facts"])

    system = store.find("system", contains="integration")[0]
    using_system = store.traverse(system.id, "process_uses_system", direction="in")
    assert len(using_system) == 2

    finding = store.get(ontology_id("compliance_finding", "finding-vat-1"))
    assert finding is not None
    assert finding.properties["classification"] == "contradiction"
    affected_processes = store.traverse(finding.id, "finding_affects_process")
    assert [item.primary_key_value for item in affected_processes] == [first_id]

    rejected = register_upload(
        register,
        "draft.md",
        b"# Draft\n\n## Roles and responsibilities\n\n| Role | Notes |\n|---|---|\n| Draft owner | Owns draft |",
        title="Rejected Draft",
    )
    register.update(rejected.id, approval_status="rejected")
    after_rejected = rebuild_ontology(register, process_registry, compliance_latest, store)

    assert after_rejected["counts"]["objects"]["source"] == 4
    assert after_rejected["counts"]["objects"]["process"] == 2


def test_rebuild_reconciles_system_and_role_aliases_to_canonical_entities(tmp_path) -> None:
    register = SourceRegister(tmp_path)
    first = register_upload(
        register,
        "fuel.md",
        _alias_process_doc(
            "Service Items Fuel and Special Non-Stock Lines",
            role="Compliance Manager (5)",
            system="Downstream retail / point-of-sale consumer - anonymised",
        ).encode(),
        title="Fuel Pack",
    )
    second = register_upload(
        register,
        "sales.md",
        _alias_process_doc(
            "End-to-End Article Setup and Bulk Upload Process",
            role="Compliance Manager (2)",
            system="POS",
        ).encode(),
        title="Sales Pack",
    )
    register.update(first.id, approval_status="approved")
    register.update(second.id, approval_status="approved")
    store = OntologyStore(tmp_path / "ontology.db")

    result = rebuild_ontology(register, ProcessRegistry(register.base_dir), None, store)

    assert result["counts"]["objects"]["system"] == 1
    assert result["counts"]["objects"]["role"] == 1
    pos = store.find("system", {"normalized_name": "point of sale"})[0]
    assert pos.properties["name"] == "Point of Sale"
    assert set(pos.properties["aliases"]) == {
        "Downstream retail / point-of-sale consumer - anonymised",
        "POS",
        "Point of Sale",
    }
    assert {item.properties["name"] for item in store.traverse(pos.id, "process_uses_system", direction="in")} == {
        "Service Items Fuel and Special Non-Stock Lines",
        "End-to-End Article Setup and Bulk Upload Process",
    }
    role = store.find("role", {"normalized_name": "compliance manager"})[0]
    assert role.properties["name"] == "Compliance Manager"
    assert {item.properties["name"] for item in store.traverse(role.id, "process_has_role", direction="in")} == {
        "Service Items Fuel and Special Non-Stock Lines",
        "End-to-End Article Setup and Bulk Upload Process",
    }


def test_manual_rebuild_endpoint_is_auth_protected_and_refreshes_ontology(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KP_DATA_DIR", str(tmp_path))
    from assistant.api.app import create_app

    register = SourceRegister(tmp_path)
    _seed_approved_process_sources(register)
    client = TestClient(create_app(register, AuthService(PASSWORD)))

    assert client.post("/api/ontology/rebuild").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    response = client.post("/api/ontology/rebuild")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "rebuilt"
    assert body["counts"]["objects"]["process"] == 2
    assert body["counts"]["objects"]["role"] == 1


def test_ontology_query_api_exposes_schema_search_detail_traversal_and_stats(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KP_DATA_DIR", str(tmp_path))
    from assistant.api.app import create_app

    register = SourceRegister(tmp_path)
    _seed_approved_process_sources(register)
    client = TestClient(create_app(register, AuthService(PASSWORD)))

    assert client.get("/api/ontology/schema").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})

    schema = client.get("/api/ontology/schema").json()
    assert schema["schema_version"] == "ontology-schema.v1"
    assert {item["api_name"] for item in schema["object_types"]} >= {"process", "role", "system"}

    before = client.get("/api/ontology/stats").json()
    assert before["objects"]["process"] == 2
    assert before["objects"]["role"] == 1
    assert client.get("/api/analytics/ontology-stats").json()["total_objects"] == before["total_objects"]

    process_search = client.get("/api/ontology/objects", params={"type": "process", "q": "supplier"}).json()
    assert process_search["count"] == 1
    process = process_search["objects"][0]
    assert process["properties"]["name"] == "Supplier Setup"
    assert process["citation"] == "Ontology: Process/Supplier Setup"

    filtered = client.get("/api/ontology/objects", params={"type": "process", "property.domain": "supplier"}).json()
    assert [item["properties"]["name"] for item in filtered["objects"]] == ["Supplier Setup"]

    detail = client.get(f"/api/ontology/objects/{process['id']}").json()
    assert detail["neighbors"]["process_has_role"]["out"][0]["properties"]["name"] == "Finance approver"
    assert detail["neighbors"]["process_uses_system"]["out"][0]["citation"] == "Ontology: System/Integration Layer"

    role_id = ontology_id("role", "finance approver")
    traversal = client.get(
        "/api/ontology/traverse",
        params={"from_id": role_id, "link": "process_has_role", "direction": "in"},
    ).json()
    assert {item["properties"]["name"] for item in traversal["objects"]} == {"Supplier Setup", "Article Setup"}

    assert client.get("/api/ontology/objects", params={"type": "missing"}).status_code == 404
    assert client.get(
        "/api/ontology/objects",
        params={"type": "process", "property.unknown": "x"},
    ).status_code == 400
    assert client.get(
        "/api/ontology/traverse",
        params={"from_id": role_id, "link": "process_has_role", "direction": "sideways"},
    ).status_code == 400

    after = client.get("/api/ontology/stats").json()
    assert after["total_objects"] == before["total_objects"]
    assert after["total_links"] == before["total_links"]


def _seed_approved_process_sources(register: SourceRegister) -> tuple[str, str]:
    first = register_upload(register, "supplier.md", _process_doc("Supplier Setup", "supplier").encode(), title="Supplier Setup")
    second = register_upload(register, "article.md", _process_doc("Article Setup", "article").encode(), title="Article Setup")
    register.update(first.id, approval_status="approved")
    register.update(second.id, approval_status="approved")
    return first.id, second.id


def _process_doc(title: str, domain: str) -> str:
    return f"""# {title}

## Roles and responsibilities

| Role | Responsibility |
|---|---|
| Finance approver | Approves readiness |

## Systems and data dependencies

| System | Purpose |
|---|---|
| Integration Layer | Sends approved records downstream |

## Key business rules

- Contracts must be checked before downstream use.

## Suggested tagging structure

- domain: {domain}
- capability: controlled onboarding
- control: Readiness gate
"""


def _alias_process_doc(title: str, *, role: str, system: str) -> str:
    return f"""# {title}

## Roles and responsibilities

| Role | Responsibility |
|---|---|
| {role} | Owns operating readiness |

## Systems and data dependencies

| System | Purpose |
|---|---|
| {system} | Publishes approved records downstream |

## Key business rules

- System and role alias fixture.

## Suggested tagging structure

- domain: sales
- capability: ontology reconciliation
- control: Readiness gate
"""
