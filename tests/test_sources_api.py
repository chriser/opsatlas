"""API tests for health and the Knowledge Sources upload/list/delete flow."""

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

TEST_PASSWORD = "test-pass"


def make_client(tmp_path) -> TestClient:
    """An authenticated client (source routes require a bearer token)."""
    client = TestClient(create_app(SourceRegister(tmp_path), AuthService(TEST_PASSWORD)))
    token = client.post("/api/auth/login", json={"password": TEST_PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_health_ok(tmp_path):
    client = make_client(tmp_path)
    response = TestClient(client.app).get("/api/health")  # public: liveness only, no counts or model details (IAM F5)
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "knowledge-platform"}
    details = client.get("/api/health/details").json()
    assert details["sources"] == 0 and "models" in details
    assert TestClient(client.app).get("/api/health/details").status_code == 401


def test_upload_list_delete_roundtrip(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/api/sources").json() == []

    response = client.post(
        "/api/sources/upload",
        files={"file": ("supplier-setup.txt", b"anonymised process knowledge", "text/plain")},
        data={"title": "Supplier setup process"},
    )
    assert response.status_code == 200, response.text
    record = response.json()
    assert record["title"] == "Supplier setup process"
    assert record["sensitivity"] == "anonymised"
    assert record["processing_state"] == "registered"
    assert len(record["content_sha256"]) == 64

    listing = client.get("/api/sources").json()
    assert len(listing) == 1
    assert client.get("/api/health/details").json()["sources"] == 1

    source_id = record["id"]
    assert client.delete(f"/api/sources/{source_id}").status_code == 200
    assert client.get("/api/sources").json() == []


def test_upload_generates_readable_title_when_title_is_missing(tmp_path):
    client = make_client(tmp_path)

    response = client.post(
        "/api/sources/upload",
        files={"file": ("supplier-process-v3-final.md", b"# Supplier onboarding controls\n\nCheck supplier risk.", "text/markdown")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Supplier onboarding controls"


def test_upload_rejects_unsupported_type(tmp_path):
    client = make_client(tmp_path)
    response = client.post(
        "/api/sources/upload",
        files={"file": ("malware.exe", b"nope", "application/octet-stream")},
    )
    assert response.status_code == 400


def test_delete_missing_source_returns_404(tmp_path):
    client = make_client(tmp_path)
    assert client.delete("/api/sources/does-not-exist").status_code == 404


def test_deleting_a_source_takes_its_facts_out_of_the_map(tmp_path):
    """ARCH F2: a deleted document's facts were served until the next rebuild."""
    from assistant.ontology import ontology_id

    client = make_client(tmp_path)
    response = client.post("/api/sources/upload", data={"title": "Returns guide"},
                           files={"file": ("guide.md", b"# Returns guide\n\nRefunds go on the card machine.", "text/markdown")})
    assert response.status_code == 200, response.text
    source_id = response.json()["id"]
    register = client.app.state.register
    register.update(source_id, approval_status="approved")
    client.app.state.rebuild_ontology()
    assert client.app.state.ontology.get(ontology_id("source", source_id)) is not None
    assert client.delete(f"/api/sources/{source_id}").status_code == 200
    assert client.app.state.ontology.get(ontology_id("source", source_id)) is None
