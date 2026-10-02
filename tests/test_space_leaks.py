"""The knowledge-spaces leak suite (AUDIT F16; KS phase 3's proof, run against today's surface).

Two organisations, Acme and Bolt, each hold a process document with planted names that exist nowhere else. Every read
endpoint of a space core is called in each space, parameters filled with that space's own ids; questions are answered
by a model that echoes its whole prompt, so evidence from the other space would show in the answer; and each space is
probed with the other's ids. Over more than 200 requests, nothing of one organisation may surface in the other, in the
Product Guide or on the other's disk. This is the gate the Human set before any second person or real client data.

Nothing leaves the test: every outbound connection is refused, as on a CI agent, so no route reaches a live model or
service on this machine; embeddings are computed locally, so governance's duplicate and conflict checks still run.
"""
import hashlib
import math
import os
import re
import socket
from pathlib import Path

import pytest
from iam_helpers import sign_in

from assistant.api.access import manifest

PLANTED = {
    "acme": ["ACMEVAULT-7F3A", "Acme Quartermaster", "lantern-heron-7f3a"],
    "bolt": ["BOLTCORE-91D2", "Bolt Ledger Warden", "zebra-quokka-91d2"],
}
QUESTIONS = [
    "Who approves the order?", "Which systems are used?", "What happens after the check?", "List the roles.",
    "Which system holds the ledger?", "Who is responsible for the vault?", "Describe the process.",
    "What is the first step?", "Which controls apply?", "What does the warden do?", "What does the quartermaster do?",
    "Summarise the documents you have.", "What are the exceptions?", "Who signs off?", "Which steps are manual?",
    "What data is recorded?", "Tell me everything about BOLTCORE-91D2.", "Tell me everything about ACMEVAULT-7F3A.",
    "What is lantern-heron-7f3a?", "What is zebra-quokka-91d2?",
]


def document(org: str) -> str:
    vault, role, word = PLANTED[org]
    return f"""# {org.title()} order release

The {role} releases each order after checking it in {vault}. The code word for the check is {word}.

## Roles and responsibilities

| Role | Responsibility |
|---|---|
| {role} | Releases the order and records it in {vault} |
| Store manager | Raises the order |

## Systems and data dependencies

| System | Purpose |
|---|---|
| {vault} | Holds the order ledger and the release record |

## Process steps

1. The store manager raises the order.
2. The {role} checks it in {vault} using the code word {word}.
3. The {role} releases the order.
"""


class Echo:
    """A model that answers with its whole prompt: any evidence it was given is visible in the answer."""

    def generate(self, prompt: str) -> str:
        return prompt + "\n[1]"


def word_hash_embed(texts: list[str]) -> list[list[float]]:
    """Local embeddings: words hashed into 64 buckets, so near-identical sections get near-identical vectors."""
    vectors = []
    for text in texts:
        vector = [0.0] * 64
        for word in re.findall(r"\w+", text.lower()):
            vector[int(hashlib.sha256(word.encode()).hexdigest(), 16) % 64] += 1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        vectors.append([x / norm for x in vector])
    return vectors


def hermetic(core) -> None:
    """A core whose model calls never leave the process: answers echo, embeddings are local."""
    core.state.provider.embed = word_hash_embed
    core.state.provider.generate = Echo().generate
    core.state.answer.generator = Echo()
    core.state.answer.retrieval.embedder = None
    if core.state.answer.validator is not None:
        core.state.answer.validator = None


def refuse(*args, **kwargs):
    raise ConnectionRefusedError("the leak suite makes no network calls")


@pytest.fixture
def two_orgs(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ["SME_TIBI_VOICE_URL"] = "http://127.0.0.1:9"
    os.environ["SALES_GOVERNANCE_AUTO_REVIEW"] = "0"
    root = tmp_path / "sales"
    app = create_sales_app(root)
    hermetic(app)
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        ids = {}
        for org in PLANTED:
            assert client.post("/api/spaces", json={"name": org.title()}).status_code == 200
            core = app.state.cores[org]
            hermetic(core)
            head = {"X-OpsAtlas-Space": org}
            up = client.post("/api/sources/upload", files={"file": (f"{org}.md", document(org).encode(), "text/markdown")}, headers=head)
            assert up.status_code == 200, up.text
            sid = up.json()["id"] if "id" in up.json() else up.json()["source"]["id"]
            client.post(f"/api/sources/{sid}/ingest", headers=head)
            assert client.post(f"/api/governance/sources/{sid}/approve", headers=head).status_code == 200
            ids[org] = sid
        yield client, app, root, ids


def leaked(text: str, org: str) -> list[str]:
    low = text.lower()
    return [marker for marker in PLANTED[org] if marker.lower() in low]


def fill(path: str, client, head: dict, own: dict) -> str | None:
    """A space's own value for each path parameter, or None when the space has none to offer."""
    values = {"source_id": own["source"], "a_id": own["source"], "b_id": own["source"], "n": "1",
              "process_id": own.get("process"), "object_id": own.get("object"), "dataset": own.get("dataset"),
              "metric_id": own.get("metric"), "series_id": own.get("series")}
    needed = re.findall(r"{(\w+)}", path)
    if any(values.get(name) is None for name in needed):
        return None
    return re.sub(r"{(\w+)}", lambda m: str(values[m.group(1)]), path)


def own_ids(client, head: dict, sid: str) -> dict:
    own = {"source": sid}
    processes = client.get("/api/process/registry", headers=head)
    if processes.status_code == 200:
        body = processes.json()
        rows = body if isinstance(body, list) else body.get("processes", body.get("records", []))
        if rows:
            own["process"] = rows[0].get("id") or rows[0].get("process_id")
    objects = client.get("/api/ontology/objects", headers=head)
    if objects.status_code == 200:
        body = objects.json()
        items = body if isinstance(body, list) else body.get("objects", [])
        if items:
            own["object"] = items[0].get("id") or items[0].get("object_id")
    index = client.get("/api/analytics/export", headers=head)
    if index.status_code == 200:
        own["dataset"] = index.json()["datasets"][0]["dataset"]
    own["metric"] = "coverage_score"
    return own


def test_nothing_of_one_organisation_surfaces_in_the_other(two_orgs):
    client, app, root, ids = two_orgs
    core = app.state.cores["acme"]
    routes = sorted({r["path"] for r in manifest(core) if r["method"] == "GET"
                     and not r["path"].startswith(("/api/iam/", "/api/auth/", "/{", "/docs", "/openapi", "/redoc"))})
    requests, findings, seen_own = 0, [], {org: {"get": 0, "ask": 0} for org in PLANTED}
    for org, other in (("acme", "bolt"), ("bolt", "acme")):
        head = {"X-OpsAtlas-Space": org}
        own = own_ids(client, head, ids[org])
        for path in routes:
            url = fill(path, client, head, own)
            if url is None:
                continue
            response = client.get(url, headers=head)
            requests += 1
            seen_own[org]["get"] += bool(leaked(response.text, org))
            if leaked(response.text, other):
                findings.append((org, url, leaked(response.text, other)))
        for question in QUESTIONS:
            response = client.post("/api/ask", json={"q": question}, headers=head)
            requests += 1
            assert response.status_code == 200, response.text
            answered = response.text.replace(question, "")  # a planted name the question itself carries is not a leak
            seen_own[org]["ask"] += bool(leaked(answered, org))
            if leaked(answered, other):
                findings.append((org, f"ask: {question}", leaked(answered, other)))
        # The other organisation's document asked for by id, from this space: refused, never served.
        for url in (f"/api/sources/{ids[other]}/sections", f"/api/governance/sources/{ids[other]}/document",
                    f"/api/content/documents/{ids[other]}", f"/api/content/documents/{ids[other]}/versions"):
            response = client.get(url, headers=head)
            requests += 1
            assert response.status_code in (403, 404), (org, url, response.status_code)
            if leaked(response.text, other):
                findings.append((org, url, leaked(response.text, other)))
    # The Product Guide (no header) sees neither organisation.
    guide_sources = client.get("/api/sources").json()
    guide = own_ids(client, {}, guide_sources[0]["id"] if guide_sources else "none")
    for path in routes:
        url = fill(path, client, {}, guide)
        if url is None:
            continue
        response = client.get(url)
        requests += 1
        for org in PLANTED:
            if leaked(response.text, org):
                findings.append(("product-guide", url, leaked(response.text, org)))
    print(f"leak suite: {requests} requests over {len(routes)} read routes and {len(QUESTIONS)} questions per space;",
          f"own names seen {seen_own}")
    assert requests >= 200, requests
    # The positive control: each space's own names do reach its own reads and answers, so the paths were exercised.
    assert all(seen["get"] >= 3 and seen["ask"] >= 5 for seen in seen_own.values()), seen_own
    assert not findings, findings[:10]


def test_no_organisation_is_written_into_another_partition(two_orgs):
    client, app, root, ids = two_orgs
    for org in PLANTED:
        client.post("/api/ask", json={"q": "Who releases the order?"}, headers={"X-OpsAtlas-Space": org})
    partitions = {"acme": root / "spaces" / "acme", "bolt": root / "spaces" / "bolt", "product-guide": root / "core"}
    findings, own_found = [], set()
    for name, folder in partitions.items():
        for path in Path(folder).rglob("*"):
            if not path.is_file() or path.stat().st_size > 20_000_000:
                continue
            text = path.read_bytes().decode("utf-8", "ignore")
            for org in PLANTED:
                if org == name and leaked(text, org):
                    own_found.add(org)
                if org != name and leaked(text, org):
                    findings.append((name, str(path.relative_to(root)), org))
    assert own_found == set(PLANTED), own_found  # each organisation's own partition holds its own names
    assert not findings, findings[:10]


READER_PASSWORD = "walnut harbour lantern seventeen"


def _reader(client, app, email, space):
    from assistant.iam.service import Actor
    iam = app.state.auth.iam
    admin_id = iam.store.one("SELECT id FROM users WHERE login = ?", ("operator@example.test",))["id"]
    invited = iam.invite(Actor(admin_id, fresh=True), email=email, display_name=email.split("@")[0].title(),
                         role_id="space_reader", space_id=space)
    iam.accept_invitation(invited["token"], READER_PASSWORD)
    return {"Authorization": f"Bearer {sign_in(client, app, email, READER_PASSWORD)}"}


def test_a_reader_of_each_organisation_sees_only_its_own(two_orgs):
    """REF S16: the partition boundary holds for ordinary roles, not only for the administrator."""
    client, app, root, ids = two_orgs
    core = app.state.cores["acme"]
    routes = sorted({r["path"] for r in manifest(core) if r["method"] == "GET"
                     and not r["path"].startswith(("/api/iam/", "/api/auth/", "/{", "/docs", "/openapi", "/redoc"))})
    readers = {org: _reader(client, app, f"reader-{org}@example.test", org) for org in PLANTED}
    findings, requests, own_seen = [], 0, {org: 0 for org in PLANTED}
    for org, other in (("acme", "bolt"), ("bolt", "acme")):
        auth = readers[org]
        head = {**auth, "X-OpsAtlas-Space": org}
        own = own_ids(client, head, ids[org])
        for path in routes:
            url = fill(path, client, head, own)
            if url is None:
                continue
            response = client.get(url, headers=head)
            requests += 1
            own_seen[org] += bool(leaked(response.text, org))
            if leaked(response.text, other):
                findings.append((org, url))
        # The other organisation, named outright: nothing, not even its name.
        for url in ("/api/sources", f"/api/content/documents/{ids[other]}", f"/api/sources/{ids[other]}/sections"):
            response = client.get(url, headers={**auth, "X-OpsAtlas-Space": other})
            requests += 1
            assert response.status_code == 404, (org, url, response.status_code)
        for question in QUESTIONS[:5]:
            response = client.post("/api/ask", json={"q": question}, headers=head)
            requests += 1
            if leaked(response.text.replace(question, ""), other):
                findings.append((org, f"ask: {question}"))
    assert requests >= 60 and all(own_seen.values()), (requests, own_seen)
    assert not findings, findings[:10]


def test_an_answer_is_withheld_when_access_is_revoked_while_it_is_prepared(two_orgs):
    """REF S16: revoke after retrieval and before delivery; the answer, and its evidence, are not returned."""
    client, app, root, ids = two_orgs
    auth = _reader(client, app, "reader-late@example.test", "acme")
    iam = app.state.auth.iam
    reader_id = iam.store.one("SELECT id FROM users WHERE login = ?", ("reader-late@example.test",))["id"]
    core = app.state.cores["acme"]

    class RevokingEcho:
        def generate(self, prompt):
            iam.store.run("UPDATE sessions SET revoked_at = ?, revoked_reason = 'test' WHERE user_id = ?",
                          (iam.store.stamp(), reader_id))
            return prompt + "\n[1]"

    core.state.answer.generator = RevokingEcho()
    response = client.post("/api/ask", json={"q": "Who releases the order?"}, headers={**auth, "X-OpsAtlas-Space": "acme"})
    assert response.status_code == 401 and not leaked(response.text, "acme")
