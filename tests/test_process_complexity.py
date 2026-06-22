"""Process-complexity analytics tests."""

from __future__ import annotations

from assistant.analytics.process_complexity import build_process_complexity
from assistant.process.models import ProcessRecord, ProcessRule

COMPLEX_PACK = """# Anonymised Learning Pack 2 - Contract Change Approval Process

## 3. Roles and responsibilities

| Role | Responsibility |
|---|---|
| Commercial owner | Owns the commercial request. |
| Finance approver | Validates commercial impact. |
| Legal approver | Reviews contract wording. |
| Operations lead | Confirms operational readiness. |

## 4. Key business rules

- Manual exception handling is required when the owner is unclear.
- Contract changes must fail closed until finance and legal validation is complete.

## 5. Systems and data dependencies

| System / dependency | Purpose | Key data | Notes |
|---|---|---|---|
| Contract repository | Contract evidence. | Contract ID. | n/a |
| Finance workflow | Margin validation. | Approval ID. | n/a |
| Operations tracker | Operational readiness. | Task ID. | n/a |

## 8. JSON-style learning records

```json
{"record_id":"CON_001","topic":"trigger","role":"commercial_owner","rule":"owner raises the change request","confidence":"high"}
{"record_id":"CON_002","topic":"validation","role":"commercial_owner","rule":"owner gathers finance evidence","confidence":"medium"}
{"record_id":"CON_003","topic":"gate","role":"commercial_owner","rule":"owner is unclear and requires validation","confidence":"medium"}
{"record_id":"CON_004","topic":"approval","role":"finance_approver","rule":"finance validates margin impact","confidence":"high"}
```

## 9. Suggested tagging structure

- `domain: contract-management`
- `process: contract-change-approval`
- `capability: approval-routing`
- `dependency: finance-validation`
- `dependency: legal-review`
- `control: fail-closed-approval`
"""


def test_process_complexity_scores_are_explainable_and_sorted():
    complex_record = ProcessRecord(
        id="complex",
        source_id="complex",
        source_title="Contract pack",
        name="Contract Change Approval",
        domain="contract-management",
        process="contract-change-approval",
        roles=["Commercial owner", "Finance approver", "Legal approver", "Operations lead"],
        systems=["Contract repository", "Finance workflow", "Operations tracker"],
        controls=["fail-closed-approval"],
        dependencies=["finance-validation", "legal-review"],
        business_rules=[
            "Manual exception handling is required when the owner is unclear.",
            "Contract changes fail closed until validation is complete.",
        ],
        rules=[
            ProcessRule(role="commercial_owner", rule="commercial owner raises the change request"),
            ProcessRule(role="commercial_owner", rule="commercial owner gathers finance evidence"),
            ProcessRule(role="commercial_owner", rule="owner is unclear and requires validation"),
            ProcessRule(role="finance_approver", rule="finance validates margin impact"),
        ],
    )
    simple_record = ProcessRecord(
        id="simple",
        source_id="simple",
        source_title="Simple pack",
        name="Daily Status Check",
        roles=["Support analyst"],
        systems=["Support queue"],
        rules=[ProcessRule(role="support_analyst", rule="support analyst checks the queue")],
    )

    out = build_process_complexity([simple_record, complex_record])

    assert out["process_count"] == 2
    assert out["processes"][0]["id"] == "complex"
    assert out["processes"][0]["complexity_band"] == "high"
    assert out["processes"][0]["key_person_risk_band"] == "high"
    assert out["processes"][0]["signals"]["systems"] == 3
    assert out["processes"][0]["signals"]["dependencies"] == 2
    assert out["processes"][0]["signals"]["dominant_role_share"] == 0.75
    assert "Multiple systems involved" in out["processes"][0]["indicators"]
    assert "Ownership needs clarification" in out["processes"][0]["indicators"]
    assert out["processes"][0]["explanation"].startswith("Indicator only:")
    assert out["processes"][1]["complexity_band"] == "low"


def test_process_complexity_handles_empty_registry():
    out = build_process_complexity([])
    assert out == {
        "process_count": 0,
        "average_complexity": 0.0,
        "high_risk_count": 0,
        "processes": [],
    }


def test_process_complexity_endpoint_builds_from_approved_sources(tmp_path):
    from fastapi.testclient import TestClient

    from assistant.api.app import create_app
    from assistant.api.auth import AuthService
    from assistant.ingestion.store import SectionStore
    from assistant.retrieval.service import RetrievalService
    from assistant.sources.register import SourceRegister

    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    client = TestClient(create_app(reg, AuthService("pw"), retrieval=RetrievalService(reg, store)))
    token = client.post("/api/auth/login", json={"password": "pw"}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    rec = client.post(
        "/api/sources/upload",
        files={"file": ("contract.md", COMPLEX_PACK.encode(), "text/markdown")},
        data={"title": "Contract pack"},
    ).json()
    client.post(f"/api/sources/{rec['id']}/ingest")
    client.post(f"/api/governance/sources/{rec['id']}/approve")

    out = client.get("/api/analytics/process-complexity").json()

    assert out["process_count"] == 1
    assert out["average_complexity"] > 0
    assert out["processes"][0]["name"] == "Contract Change Approval Process"
    assert out["processes"][0]["complexity_score"] >= 67
    assert out["processes"][0]["key_person_risk_score"] >= 67
    assert out["processes"][0]["signals"]["roles"] == 4
    assert "Indicator only" in out["processes"][0]["explanation"]
