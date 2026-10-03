"""Red team, round 5, REF H3b (scope) at 6446fd8. Each test that fails shows one break of a promise; the controls pass.

Hermetic: a Sales app in a temporary folder, sockets refused, the model replaced by an echo that shows the prompt.
"""
from __future__ import annotations

import os
import socket

import pytest

from tests.iam_helpers import sign_in
from tests.test_space_leaks import hermetic, refuse

HEAD = {"X-OpsAtlas-Space": "acme"}
TODAY = "2026-10-03"

PROCESS_DOC = """# Purchase Order Approval

## Purpose
The purchase order approval process decides who approves a purchase order. MARKER-PROCESS-DOC.

## Roles
The procurement manager approves every purchase order.

## Systems
SAP Ariba records every purchase order.

## Controls
Two-person approval applies to any purchase order over 10,000 pounds.
"""


class Show:
    """The model: echoes its prompt and cites the first passage, so the test sees what the model was given."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return prompt + "\n[1]"


@pytest.fixture
def space(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ["SME_TIBI_VOICE_URL"] = "http://127.0.0.1:9"
    os.environ["SALES_GOVERNANCE_AUTO_REVIEW"] = "0"
    for name in ("KP_SCOPE_EVIDENCE", "KP_SCOPE_TODAY", "KP_PLAN_PARTS", "KP_WITHHOLD_UNSUPPORTED"):
        os.environ.pop(name, None)
    app = create_sales_app(tmp_path / "sales")
    hermetic(app)
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        assert client.post("/api/spaces", json={"name": "Acme"}).status_code == 200
        core = app.state.cores["acme"]
        hermetic(core)
        show = Show()
        core.state.answer.generator = show
        yield client, core, show


def add(client, name: str, text: str, approve: bool = True) -> str:
    up = client.post("/api/sources/upload", files={"file": (name, text.encode(), "text/markdown")}, headers=HEAD)
    assert up.status_code == 200, up.text
    body = up.json()
    sid = body["id"] if "id" in body else body["source"]["id"]
    assert client.post(f"/api/sources/{sid}/ingest", headers=HEAD).status_code == 200
    if approve:
        assert client.post(f"/api/governance/sources/{sid}/approve", headers=HEAD).status_code == 200
    return sid


def scope_on() -> None:
    os.environ["KP_SCOPE_EVIDENCE"] = "1"
    os.environ["KP_SCOPE_TODAY"] = TODAY


def ask(client, show, question: str) -> tuple[dict, str]:
    before = len(show.prompts)
    response = client.post("/api/ask", json={"q": question}, headers=HEAD)
    assert response.status_code == 200, response.text
    prompt = "\n".join(show.prompts[before:])
    return response.json(), prompt


def details(client, sid: str, fields: dict):
    return client.patch(f"/api/content/documents/{sid}/details", json={"fields": fields}, headers=HEAD)


# ---- P6 / P7: a facts map out of step means documents only -----------------------------------------------------------

QUESTION_PROCESS = "Who approves a purchase order in the purchase order approval process?"


def test_scope_h3b_round5_control_facts_map_in_step_is_used(space):
    """Control: with scope on, nothing scoped and the facts map in step, the facts (or the registry) may answer."""
    client, core, show = space
    add(client, "po.md", PROCESS_DOC)
    scope_on()
    assert core.state.answer._facts_in_step([r for r in core.state.register.list() if r.approval_status == "approved"])


def test_scope_h3b_round5_out_of_step_facts_map_still_lets_process_registry_answer(space):
    """P6/P7: an approval not yet in the facts map (a second source approved without a rebuild) makes the map out of
    step, so the answer must use documents only; the process registry still adds its 'structured facts' item."""
    client, core, show = space
    add(client, "po.md", PROCESS_DOC)
    other = add(client, "other.md", "# Travel\n\nTrain tickets are booked through the travel desk.\n", approve=False)
    core.state.register.update(other, approval_status="approved")  # approved; the facts map not yet rebuilt
    scope_on()
    approved = [r for r in core.state.register.list() if r.approval_status == "approved"]
    assert not core.state.answer._facts_in_step(approved)  # the map is out of step with this reading
    result, prompt = ask(client, show, QUESTION_PROCESS)
    kinds = {c.get("citation_type") for c in result["citations"]}
    assert "Process registry:" not in prompt, "an out-of-step facts map must mean documents only (P6, P7)"
    assert kinds <= {"document"}, kinds


# ---- P6: an edit that lands while the answer is prepared applies from the next answer ---------------------------------


class EditAfterReading:
    """The register as the answer sees it: the first reading is returned as it was, and an edit lands right after it."""

    def __init__(self, real, action) -> None:
        self._real, self._action = real, action

    def list(self):
        rows = self._real.list()
        if self._action is not None:
            action, self._action = self._action, None
            action()
        return rows

    def __getattr__(self, name):
        return getattr(self._real, name)


def _publish_pending_v2(core, sid: str, text: str):
    """The first half of ContentService._write_version (publish): content written, version bumped and pending, sections
    re-ingested; the approval has not landed yet."""
    from assistant.ingestion.service import ingest_source
    register = core.state.register
    source = register.get(sid)
    register.write_content(sid, text.encode())
    register.update(sid, version=source.version + 1, approval_status="pending")
    ingest_source(register, core.state.answer.retrieval.section_store, sid)


def test_scope_h3b_round5_control_reading_text_reaches_answer(space):
    client, core, show = space
    add(client, "refunds.md", "# Refunds\n\nRefunds are paid within 14 days. MARKER-V1.\n")
    scope_on()
    _, prompt = ask(client, show, "How long do refunds take?")
    assert "MARKER-V1" in prompt


def test_scope_h3b_round5_new_version_landing_after_reading_reaches_this_answer(space, monkeypatch):
    """P6: the reading has version 1 approved. A new version (not yet approved) lands right after the reading; the
    answer's passages are read live from the section store, so the pending version-2 text reaches this answer."""
    client, core, show = space
    sid = add(client, "refunds.md", "# Refunds\n\nRefunds are paid within 14 days. MARKER-V1.\n")
    scope_on()
    answer = core.state.answer
    proxy = EditAfterReading(answer.retrieval.register,
                             lambda: _publish_pending_v2(core, sid, "# Refunds\n\nRefunds are paid within 90 days. MARKER-V2-PENDING.\n"))
    monkeypatch.setattr(answer.retrieval, "register", proxy)
    _, prompt = ask(client, show, "How long do refunds take?")
    assert core.state.register.get(sid).approval_status == "pending"  # version 2 was never approved
    assert "MARKER-V2-PENDING" not in prompt, "an edit landing while the answer is prepared applies from the next answer"


# ---- P2: labels -----------------------------------------------------------------------------------------------------


def test_scope_h3b_round5_control_plain_site_label(space):
    client, core, show = space
    sid = add(client, "leeds.md", "# Parking\n\nStaff park in the north car park. MARKER-SITE.\n")
    assert details(client, sid, {"applies_to": ["Leeds"]}).status_code == 200
    scope_on()
    _, prompt = ask(client, show, "Where do staff park?")
    assert "(Applies to: Leeds.) " in prompt


def test_scope_h3b_round5_site_name_passes_for_a_period_label(space):
    """P2 'exactly these labels': a site name with a full stop made a source with no end date say 'In force until 1
    January 2020'. Restated after the Human's decision (Latin letters only, no full stops): the name is refused."""
    client, core, show = space
    sid = add(client, "leeds.md", "# Parking\n\nStaff park in the north car park. MARKER-SITE.\n")
    response = details(client, sid, {"applies_to": ["Leeds. In force until 1 January 2020"]})
    assert response.status_code >= 400, response.text
    assert core.state.register.get(sid).effective_to is None
    scope_on()
    _, prompt = ask(client, show, "Where do staff park?")
    assert "In force until" not in prompt, "a passage from a source with no end date says until when"


@pytest.mark.parametrize("name", ["ㅤ", "ﾠ", "½", "Ⅷ"],
                         ids=["hangul-filler-invisible", "halfwidth-hangul-filler", "vulgar-half", "roman-numeral-eight"])
def test_scope_h3b_round5_site_name_without_a_letter_or_digit_is_accepted(space, name):
    """P2: a site name needs at least one letter or digit, and a blank entry is refused. A Hangul filler (renders as
    nothing) or a fraction sign is neither a letter nor a digit a reader can see, yet it is stored and labelled."""
    client, core, show = space
    sid = add(client, "leeds.md", "# Parking\n\nStaff park in the north car park.\n")
    response = details(client, sid, {"applies_to": [name]})
    assert response.status_code >= 400, f"{name!r} was accepted and stored as {core.state.register.get(sid).applies_to!r}"


@pytest.mark.parametrize("name", ["เชียงใหม่", "मुंबई"], ids=["thai-chiang-mai", "devanagari-mumbai"])
def test_scope_h3b_round5_site_name_in_letters_is_refused(space, name):
    """P2: Thai and Devanagari names were refused by accident (their vowel signs are Unicode marks). Restated after the
    Human's decision (Latin letters only, 3 October 2026): names in other scripts are refused by rule, with a message
    that says what a site name may be."""
    client, core, show = space
    sid = add(client, "site.md", "# Parking\n\nStaff park in the north car park.\n")
    response = details(client, sid, {"applies_to": [name]})
    assert response.status_code >= 400 and "Latin letters" in response.text, response.text


# ---- P6: the facts map holds to the reading (same ids and versions) ---------------------------------------------------


def test_scope_h3b_round5_control_scope_on_nothing_scoped_same_prompt_as_off(space):
    """Control for P7: nothing scoped, facts map in step: the model is given the same prompt with scope on and off."""
    client, core, show = space
    add(client, "po.md", PROCESS_DOC)
    off, prompt_off = ask(client, show, QUESTION_PROCESS)
    scope_on()
    on, prompt_on = ask(client, show, QUESTION_PROCESS)
    assert (prompt_on, on["answer"], on["refused"]) == (prompt_off, off["answer"], off["refused"])


TABLE_DOC = """# Purchase Order Approval

## Purpose
The purchase order approval process decides who approves a purchase order.

## Roles and responsibilities

| Role | Responsibility |
|---|---|
| Procurement manager | Approves every purchase order |
| Requester | Raises the purchase order |

## Systems and data dependencies

| System | Use |
|---|---|
| SAP Ariba | Records every purchase order |
"""


def test_scope_h3b_round5_facts_map_rebuilt_mid_publish_carries_unapproved_text(space):
    """P6/P9: a rebuild (another document's approval) lands while a publish of this document has written its new text;
    the publish then fails. Restated after the Human's decision (fix the publish order) to drive the real publish: the
    rebuild reads the new text against version 1's fingerprint and leaves it out. Restated again for the staged publish
    (REF S23): the swap fails and puts the old text and passages back; the record never changed. No fact from the
    never-approved text answers, and the map is in step with the register."""
    client, core, show = space
    sid = add(client, "po.md", TABLE_DOC)
    register, content = core.state.register, core.state.content
    real_stage = register.stage_content

    def stage_rebuild_then_fail(source_id, data):  # the staged publish (REF S23): the new text staged beside the live one
        real_stage(source_id, data)
        if b"Finance director" in data:
            core.state.rebuild_ontology()  # another approval's rebuild, landing as the new text is staged
            raise OSError("disk full")  # then the publish fails, and what was staged is discarded
    register.stage_content = stage_rebuild_then_fail
    try:
        with pytest.raises(Exception):
            content._write_version(register.get(sid), TABLE_DOC.replace("Procurement manager", "Finance director").encode(),
                                   approve=True)
    finally:
        register.stage_content = real_stage
    assert register.get(sid).approval_status == "approved" and register.get(sid).version == 1
    scope_on()
    approved = [r for r in register.list() if r.approval_status == "approved"]
    assert core.state.answer._facts_in_step(approved)  # rebuilt after the failed publish: in step again
    result, prompt = ask(client, show, "What roles are involved in the purchase order approval process?")
    seen = (result["answer"] + prompt).lower()
    assert "finance director" not in seen, "facts from text never approved reached the answer"
