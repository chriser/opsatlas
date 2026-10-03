"""REF H3b: with scope on, no answer cites or states a fact from a source not in force on the date asked, replaced, or
for another site, whichever evidence path it comes through: passages, the facts map or the process registry. H3's
candidate filtered passages only, and the 2025 policy still reached answers through the facts map. Simplest design:
when scope keeps any approved source out of an answer, that answer uses documents only (the rule phase 1a uses for
restricted documents). With scope off, answers are as before."""
import os
import socket

import pytest
from fastapi.testclient import TestClient
from iam_helpers import sign_in
from test_space_leaks import hermetic, refuse

OLD = "Kestrel Ledger 2025"
NEW = "Merlin Ledger 2026"


def process(name, system):
    return f"""# Returns release {name}

The returns clerk releases each refund after checking it in {system}.

## Roles and responsibilities

| Role | Responsibility |
|---|---|
| Returns clerk | Releases the refund and records it in {system} |

## Systems and data dependencies

| System | Purpose |
|---|---|
| {system} | Holds the returns ledger |

## Process steps

1. The customer brings the item back.
2. The returns clerk checks it in {system}.
3. The returns clerk releases the refund.
"""


@pytest.fixture
def acme(tmp_path, monkeypatch):
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ.update({"SME_TIBI_VOICE_URL": "http://127.0.0.1:9", "SALES_GOVERNANCE_AUTO_REVIEW": "0", "KP_SCOPE_TODAY": "2026-10-03"})
    app = create_sales_app(tmp_path / "sales")
    hermetic(app)
    with TestClient(app) as client:
        head = {"Authorization": f"Bearer {sign_in(client, app)}"}
        assert client.post("/api/spaces", json={"name": "Acme"}, headers=head).status_code == 200
        core = app.state.cores["acme"]
        hermetic(core)
        head = {**head, "X-OpsAtlas-Space": "acme"}
        ids = {}
        for key, name, system, start, end in (("old", "2025", OLD, "2025-01-01", "2025-12-31"), ("new", "2026", NEW, "2026-01-01", None)):
            up = client.post("/api/sources/upload", files={"file": (f"returns-{name}.md", process(name, system).encode(), "text/markdown")},
                             headers=head).json()
            sid = up["id"] if "id" in up else up["source"]["id"]
            client.post(f"/api/sources/{sid}/ingest", headers=head)
            assert client.post(f"/api/governance/sources/{sid}/approve", headers=head).status_code == 200
            core.state.register.update(sid, effective_from=start, effective_to=end)
            ids[key] = sid
        yield client, core, head, ids


QUESTIONS = ["Which system holds the returns ledger?", "Who releases the refund?", "What are the steps for returns?"]


def test_the_facts_map_carries_the_old_policy_when_scope_is_off(acme):
    """The positive control: with scope off, the out-of-force system reaches answers (by the facts map or passages)."""
    client, core, head, ids = acme
    os.environ.pop("KP_SCOPE_EVIDENCE", None)
    said = " ".join(client.post("/api/ask", json={"q": q}, headers=head).text for q in QUESTIONS)
    assert OLD in said


def test_with_scope_on_no_path_carries_a_source_not_in_force(acme):
    client, core, head, ids = acme
    os.environ["KP_SCOPE_EVIDENCE"] = "1"
    for question in QUESTIONS:
        answer = client.post("/api/ask", json={"q": question}, headers=head).json()
        assert OLD not in answer["answer"], question  # the echo model would repeat any evidence it was given
        assert not [c for c in answer["citations"] if c["citation_type"] != "document"], question  # documents only
        assert all(c["source_id"] != ids["old"] for c in answer["citations"]), question


def test_with_scope_on_and_nothing_excluded_the_facts_map_still_answers(acme):
    """Scope off the facts map only when it keeps something out: with every source in force, structured answers stay."""
    client, core, head, ids = acme
    core.state.register.update(ids["old"], effective_to=None, effective_from="2025-01-01")
    os.environ["KP_SCOPE_EVIDENCE"] = "1"
    answer = client.post("/api/ask", json={"q": "Which system holds the returns ledger?"}, headers=head).json()
    assert answer["answer_path"] in ("oag", "rag+ontology") or any(c["citation_type"] != "document" for c in answer["citations"])
