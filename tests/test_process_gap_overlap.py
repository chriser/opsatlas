"""Process gap, overlap and clash visualisation tests."""

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.process.coverage import build_process_gap_overlap_report
from assistant.process.models import ProcessRecord
from assistant.sources.register import SourceRegister

PASSWORD = "gap-overlap-test-pass"


def _records() -> list[ProcessRecord]:
    return [
        ProcessRecord(
            id="supplier-activation",
            source_id="src-1",
            source_title="Supplier activation pack",
            name="Supplier activation",
            roles=["Trading Support"],
            systems=["Finance master data"],
            controls=["Contract readiness check"],
            dependencies=["Finance identifier mapping"],
            business_rules=["Supplier can activate only after finance mapping is complete."],
        ),
        ProcessRecord(
            id="article-activation",
            source_id="src-2",
            source_title="Article activation pack",
            name="Article activation",
            roles=["Master Data Owner"],
            systems=["Finance master data"],
            controls=[],
            dependencies=["Finance identifier mapping"],
            business_rules=["Article is released after tax validation and downstream mapping."],
        ),
        ProcessRecord(
            id="orphan-process",
            source_id="src-3",
            source_title="Thin process pack",
            name="Thin process",
            business_rules=["A manual exception is reviewed later."],
        ),
    ]


def test_gap_overlap_report_finds_gaps_overlaps_and_clashes():
    report = build_process_gap_overlap_report(_records())

    assert report.process_count == 3
    assert report.finding_count >= 3
    assert report.gap_count >= 1
    assert report.overlap_count >= 1
    assert report.clash_count >= 1
    assert any(finding.finding_type == "gap" and "Thin process" in finding.title for finding in report.findings)
    assert any(finding.finding_type == "overlap" and "Finance master data" in "; ".join(finding.evidence) for finding in report.findings)
    assert any(finding.finding_type == "clash" and finding.severity in {"high", "medium"} for finding in report.findings)
    assert report.rubric["boundary"].startswith("Findings are deterministic")


def test_gap_overlap_endpoint_is_protected_and_empty_safe(tmp_path):
    register = SourceRegister(tmp_path)
    client = TestClient(create_app(register, AuthService(PASSWORD)))

    assert client.get("/api/process/gap-overlap").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    response = client.get("/api/process/gap-overlap", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["process_count"] == 0
    assert body["gap_count"] >= body["clash_count"]
    assert body["rubric"]["gap"]
