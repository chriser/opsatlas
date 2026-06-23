"""Operating-model coverage map tests."""

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.process.coverage import build_operating_model_coverage
from assistant.process.models import ProcessRecord, ProcessRule
from assistant.sources.register import SourceRegister

PASSWORD = "coverage-test-pass"


def _supplier_record() -> ProcessRecord:
    return ProcessRecord(
        id="supplier-setup",
        source_id="src-supplier",
        source_title="Supplier setup learning pack",
        name="Supplier setup",
        domain="supplier master data",
        roles=["Category Buyer", "Trading Support", "Finance Owner"],
        systems=["Excel", "Finance master data", "Operational master data tool"],
        controls=["Due diligence gate", "Credit check", "Contract readiness check"],
        dependencies=["Finance identifier mapping", "Supplier data completeness"],
        business_rules=[
            "Supplier setup starts with a formal request form.",
            "Supplier must pass due diligence and credit checks before activation.",
            "Supplier identifiers are mapped for finance reconciliation.",
        ],
        rules=[
            ProcessRule(topic="request", role="Category Buyer", rule="Buyer submits the supplier setup form.", confidence="high"),
            ProcessRule(topic="validation", role="Trading Support", rule="Support validates completeness.", confidence="high"),
        ],
    )


def _article_record() -> ProcessRecord:
    return ProcessRecord(
        id="article-tax",
        source_id="src-article",
        source_title="Article setup and tax handling pack",
        name="Article setup tax handling",
        domain="article product master data",
        roles=["Master Data Owner", "Compliance Owner"],
        systems=["Retail downstream platform"],
        controls=["Tax validation", "Age restriction review"],
        dependencies=["Pricing dependency", "Tax definition"],
        business_rules=[
            "Article activation waits for tax handling validation.",
            "Age restriction grouping is reviewed before downstream release.",
        ],
    )


def test_operating_model_coverage_maps_domains_and_process_matrix():
    report = build_operating_model_coverage([_supplier_record(), _article_record()])

    assert report.process_count == 2
    assert report.domain_count >= 6
    assert report.coverage_score > 0
    assert report.role_count >= 4
    assert report.system_count >= 3
    assert any(domain.domain_id == "supplier-vendor-master-data" and domain.process_count == 1 for domain in report.domains)
    assert any(domain.domain_id == "pricing-tax-and-commercial-controls" and domain.process_count >= 1 for domain in report.domains)
    assert any(row.process_id == "supplier-setup" and row.matched_domains for row in report.process_matrix)
    assert report.rubric["boundary"].startswith("Coverage shows")


def test_operating_model_coverage_endpoint_is_protected_and_empty_safe(tmp_path):
    register = SourceRegister(tmp_path)
    client = TestClient(create_app(register, AuthService(PASSWORD)))

    assert client.get("/api/process/coverage-map").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    response = client.get("/api/process/coverage-map", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["process_count"] == 0
    assert body["uncovered_domain_count"] == body["domain_count"]
    assert body["domains"][0]["coverage_status"] == "uncovered"
