"""Bug #2191: the process-diagram route resolves only processes from documents the person may read (REF S13).

POST /api/process/diagrams/resolve matched the question against every approved process, and derived_guard covers only
GET requests, so a space contributor outside a restricted document's audience got that document's process name and
source title (the design red team on REF S19b found it, 4 October 2026).
"""
from __future__ import annotations

from assistant.iam.service import Actor
from tests.iam_helpers import sign_in

READER_PW = "walnut harbour lantern seventeen"
QUESTION = {"question": "How are kestrel payroll exceptions handled by the payroll officer?"}


def process_doc(title: str, roles: list[str], system: str) -> bytes:
    rows = "\n".join(f"| {r} | {r} does their part of {title.lower()} |" for r in roles)
    return (f"# {title}\n\nThe {title.lower()} work is done by {', '.join(roles)} in {system}.\n\n"
            f"## Roles and responsibilities\n\n| Role | Responsibility |\n|---|---|\n{rows}\n\n"
            f"## Systems and data dependencies\n\n| System | Purpose |\n|---|---|\n| {system} | Holds the {title.lower()} "
            f"record |\n\n## Process steps\n\n1. The first role starts the {title.lower()}.\n2. The second role checks it "
            f"in {system}.\n").encode()


def _restricted_process_and_a_contributor(ws):
    secret = ws.document(process_doc("Kestrel payroll exceptions", ["Payroll officer", "Finance lead"], "WOMBATLEDGER"),
                         "payroll.md", title="Kestrel payroll exceptions")
    iam = ws.app.state.auth.iam
    admin_id = iam.store.one("SELECT id FROM users WHERE login = ?", ("operator@example.test",))["id"]
    restricted = ws.client.put(f"/api/iam/spaces/{ws.space}/restrictions/document/{secret}",
                               json={"audience": [f"user:{admin_id}"], "reason": "Bug #2191"})
    assert restricted.status_code == 200, restricted.text
    invited = iam.invite(Actor(admin_id, fresh=True), email="cora@example.test", display_name="Cora",
                         role_id="space_contributor", space_id=ws.space)
    iam.accept_invitation(invited["token"], READER_PW)
    cora = {"Authorization": f"Bearer {sign_in(ws.client, ws.app, 'cora@example.test', READER_PW)}", **ws.headers}
    return secret, cora


def test_a_restricted_documents_process_is_not_resolved_for_a_person_outside_its_audience(sales_workspace):
    ws = sales_workspace
    secret, cora = _restricted_process_and_a_contributor(ws)
    assert ws.client.get(f"/api/content/documents/{secret}", headers=cora).status_code == 404  # the document: withheld
    resolved = ws.client.post("/api/process/diagrams/resolve", headers=cora, json=QUESTION)
    assert resolved.status_code == 200, resolved.text
    body = resolved.json()
    assert body["status"] == "empty" and not body.get("process_name") and not body.get("source_title")
    assert "Kestrel" not in resolved.text and "WOMBATLEDGER" not in resolved.text


def test_the_process_is_still_resolved_for_a_person_in_its_audience(sales_workspace):
    ws = sales_workspace
    _restricted_process_and_a_contributor(ws)
    resolved = ws.client.post("/api/process/diagrams/resolve", headers=ws.headers, json=QUESTION)  # the administrator
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] != "empty" and "Kestrel" in (resolved.json().get("source_title") or "")
