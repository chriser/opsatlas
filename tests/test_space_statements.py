"""REF S22: channel text that makes claims comes under knowledge governance. A space's fixed sentences (refusal, off-topic
message, referral, notes, and Tibi's directions in the Product Guide) have versions and approvals; the words in use
were recorded once as version 1; an answer that says one records which version; a sentence changed in the space's
configuration is pending and not said until someone who may approve documents approves it."""
import json
import os
import socket

import pytest
from fastapi.testclient import TestClient
from iam_helpers import sign_in
from test_space_leaks import hermetic, refuse

GUIDE = "# Pricing\n\nOpsAtlas is a proof of concept; its guide does not state a price.\n"


def app_at(root):
    from services.opsatlas_sales.app import create_sales_app
    app = create_sales_app(root)
    hermetic(app)
    return app


def with_guide(client, head):
    up = client.post("/api/sources/upload", files={"file": ("pricing.md", GUIDE.encode(), "text/markdown")}, headers=head).json()
    sid = up["id"] if "id" in up else up["source"]["id"]
    client.post(f"/api/sources/{sid}/ingest", headers=head)
    assert client.post(f"/api/governance/sources/{sid}/approve", headers=head).status_code == 200


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ.update({"SME_TIBI_VOICE_URL": "http://127.0.0.1:9", "SALES_GOVERNANCE_AUTO_REVIEW": "0"})
    return tmp_path / "sales"


def test_the_words_in_use_become_version_one_and_answers_say_which_version(workspace):
    app = app_at(workspace)
    with TestClient(app) as client:
        head = {"Authorization": f"Bearer {sign_in(client, app)}"}
        listed = {s["key"]: s for s in client.get("/api/space-statements", headers=head).json()["statements"]}
        assert {"refusal", "scope_message", "referral", "note.0", "workspace_guidance", "workspace_no_guarantee"} <= set(listed)
        assert listed["referral"]["approved"]["version"] == 1 and listed["referral"]["pending"] == []
        with_guide(client, head)
        answer = client.post("/api/ask", json={"q": "What does OpsAtlas cost?"}, headers=head).json()
        assert not answer["refused"] and "contact the sales team" in answer["answer"]
        assert [(s["key"], s["version"]) for s in answer["statements"]] == [("referral", 1)]
        receipt = client.get(f"/api/answers/receipts/{answer['receipt_id']}", headers=head).json()
        assert receipt["statements"][0]["key"] == "referral" and receipt["statements"][0]["sha256"]
        # Tibi is given its directions in the workspace's approved words, and the contract names the statements.
        service = {"x-sales-token": (workspace / "local-access.key").read_text()}
        catalog = client.get("/api/sales/knowledge", headers=service).json()
        assert catalog["statements"]["workspace_guidance"]["version"] == 1
        contract = client.post("/api/sales/search", headers=service, json={"q": "What does it cost?"}).json()["contract"]
        assert contract["statements"]["referral"]["version"] == 1 and "cost" in contract["referral_topics"]


def test_a_changed_sentence_is_pending_until_approved(workspace):
    app = app_at(workspace)
    with TestClient(app):
        pass
    config_path = workspace / "core" / "space-config.json"
    config = json.loads(config_path.read_text())
    config["referral"]["sentence"] = "Ask the sales team for a quote."
    config_path.write_text(json.dumps(config))
    app = app_at(workspace)  # the owner edited the file and the core started again
    with TestClient(app) as client:
        head = {"Authorization": f"Bearer {sign_in(client, app)}"}
        referral = next(s for s in client.get("/api/space-statements", headers=head).json()["statements"] if s["key"] == "referral")
        assert referral["approved"]["version"] == 1 and [p["version"] for p in referral["pending"]] == [2]
        with_guide(client, head)
        said = client.post("/api/ask", json={"q": "What does OpsAtlas cost?"}, headers=head).json()
        assert "Ask the sales team for a quote." not in said["answer"] and said["statements"][0]["version"] == 1
        approved = client.post("/api/space-statements/referral/approve", json={"version": 2}, headers=head)
        assert approved.status_code == 200 and approved.json()["approved_by"]
        said = client.post("/api/ask", json={"q": "What does OpsAtlas cost?"}, headers=head).json()
        assert "Ask the sales team for a quote." in said["answer"] and said["statements"][0]["version"] == 2
        assert client.post("/api/space-statements/referral/approve", json={"version": 9}, headers=head).status_code == 404


def test_the_workspace_copy_is_the_product_ontologys_authority(workspace):
    """REF S22, the Human's decision: the repository file seeds an empty workspace; after that the workspace's copy is
    read, and the health details say whether it has drifted from the seed."""
    app = app_at(workspace)
    with TestClient(app) as client:
        head = {"Authorization": f"Bearer {sign_in(client, app)}"}
        copy = workspace / "core" / "product-ontology.json"
        assert copy.exists()
        assert client.get("/api/health/details", headers=head).json()["product_ontology"]["same_as_seed"] is True
    data = json.loads(copy.read_text())
    first = data["objects"][0]
    first["name"] = first.get("name", "") + " (governed)"
    copy.write_text(json.dumps(data))
    app = app_at(workspace)
    with TestClient(app) as client:
        head = {"Authorization": f"Bearer {sign_in(client, app)}"}
        details = client.get("/api/health/details", headers=head).json()["product_ontology"]
        assert details["authority"] == "workspace" and details["changed"] == [first["id"]] and not details["same_as_seed"]
