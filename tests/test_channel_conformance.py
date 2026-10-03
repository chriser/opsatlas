"""REF S19, the conformance set: Written Query (the core's answer service) and Tibi's channels (voice and the Digital SME,
which share Tibi's evidence client and so its contract) must agree on permission, scope, citation and refusal; their
wording may differ. Checked where each decides: the written answer and its receipt, and Tibi's product contract
(/api/sales/search) for the person whose conversation it is. The engines themselves are compared end to end by
scripts/evaluate_evidence.py on a copy of the workspace."""
import os

import pytest
from fastapi.testclient import TestClient
from iam_helpers import sign_in

PW = "walnut harbour lantern seventeen"


@pytest.fixture
def family(tmp_path, monkeypatch):
    from test_space_leaks import hermetic

    from assistant.iam.service import Actor
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    os.environ.update({"SME_TIBI_VOICE_URL": "http://127.0.0.1:9", "SALES_GOVERNANCE_AUTO_REVIEW": "0"})
    root = tmp_path / "sales"
    app = create_sales_app(root)
    hermetic(app)
    app.state.retrieval.embedder = None
    service = {"x-sales-token": (root / "local-access.key").read_text()}
    with TestClient(app) as c:
        admin = {"Authorization": f"Bearer {sign_in(c, app)}"}
        rows = {r["id"]: r for r in c.get("/api/sales/knowledge", headers=service).json()["records"]}
        for record in ("overview", "commercial"):
            c.post(f"/api/tibi/knowledge/{record}/review", headers=admin, json={"approve": True, "expected_hash": rows[record]["sha256"]})
        iam = app.state.auth.iam
        admin_id = iam.store.one("SELECT id FROM users WHERE login = ?", ("operator@example.test",))["id"]
        invited = iam.invite(Actor(admin_id, fresh=True), email="gita@example.test", display_name="Gita")  # the guide only
        gita = iam.accept_invitation(invited["token"], PW)
        app.state.tibi_owners.record("c-gita", gita["id"], "text")
        app.state.tibi_owners.record("c-admin", admin_id, "interview")
        people = {"admin": admin, "gita": {"Authorization": f"Bearer {sign_in(c, app, 'gita@example.test', PW)}"}}
        yield c, app, service, people


def tibi(c, service, conversation, question):
    response = c.post("/api/sales/search", headers={**service, "x-tibi-conversation": conversation}, json={"q": question})
    assert response.status_code == 200, response.text
    return response.json()["contract"]


def test_permission_and_scope_agree_a_guide_reader_gets_the_guide_on_every_channel(family):
    c, app, service, people = family
    question = "What is OpsAtlas and what does it cost?"
    gitas = tibi(c, service, "c-gita", question)
    assert gitas["spaces"] == ["product-guide"] and gitas["request"]["channel"] == "digital_sme"
    assert {i["space"] for i in gitas["items"]} <= {"product-guide"}
    written = c.post("/api/ask", json={"q": question}, headers=people["gita"]).json()
    receipt = c.get(f"/api/answers/receipts/{written['receipt_id']}", headers=people["gita"]).json()
    assert receipt["contract"]["spaces"] == ["product-guide"]
    guide = {r.id for r in app.state.register.list()}
    assert {cit["source_id"] for cit in written["citations"] if cit["citation_type"] == "document"} <= guide
    # The administrator's conversation may use the whole family; the written path answers from the space asked.
    admins = tibi(c, service, "c-admin", question)
    assert set(admins["spaces"]) == {"product-guide", "sales-playbook", "system"} and admins["request"]["channel"] == "voice"
    assert "sales-playbook" in {i["space"] for i in admins["items"]}


def test_citations_agree_both_paths_name_the_version_of_what_they_rest_on(family):
    c, app, service, people = family
    question = "What is OpsAtlas?"
    for item in tibi(c, service, "c-admin", question)["items"]:
        assert item["sha256"] and item["source_id"] and item["locator"]
    written = c.post("/api/ask", json={"q": question}, headers=people["admin"]).json()
    documents = [cit for cit in written["citations"] if cit["citation_type"] == "document"]
    assert documents and all(cit["version"] and cit["sha256"] for cit in documents)


def test_refusal_agrees_same_wording_and_nothing_relevant_means_refuse(family):
    c, app, service, people = family
    off_topic = tibi(c, service, "c-gita", "Recommend a good restaurant near the river")
    assert off_topic["decision"] == "refuse" and off_topic["relevant"] == 0
    on_topic = tibi(c, service, "c-gita", "What is OpsAtlas?")
    assert on_topic["decision"] == "answer"
    config = app.state.answer.space_config
    assert off_topic["refusal"] == config.refusal and off_topic["referral"] == (config.referral.sentence or None)
    written = c.post("/api/ask", json={"q": "What is OpsAtlas?"}, headers=people["gita"]).json()
    receipt = c.get(f"/api/answers/receipts/{written['receipt_id']}", headers=people["gita"]).json()
    assert receipt["contract"]["refusal"] == off_topic["refusal"] and receipt["contract"]["referral"] == off_topic["referral"]


def test_delivery_rechecks_the_evidence(family):
    from assistant.evidence.contract import EvidenceBundle, EvidenceItem, EvidenceRequest
    bundle = EvidenceBundle(request=EvidenceRequest(person="p", spaces=["s"], question_sha256="q", channel="written"),
                            items=[EvidenceItem(kind="passage", source_id="a", space="s", title="A", sha256="v1")], refusal="No.")
    assert bundle.recheck(lambda item: True, lambda item: "v1")
    assert not bundle.recheck(lambda item: True, lambda item: "v2")  # the document changed meanwhile
    assert not bundle.recheck(lambda item: False, lambda item: "v1")  # no longer readable
