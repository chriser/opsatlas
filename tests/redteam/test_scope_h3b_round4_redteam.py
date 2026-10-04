"""Red team, round 4, on REF H3b (scope). Each break is a failing test with the promise it breaks; controls pass.

Hermetic: a Sales app in tmp_path, sockets refused, models faked (the generator echoes its prompt), no live services.
"""
from __future__ import annotations

import os
import socket
import threading
import time

import pytest

from tests.door_helpers import as_job, decide, writing
from tests.iam_helpers import sign_in
from tests.test_space_leaks import hermetic, refuse

SPACE = {"X-OpsAtlas-Space": "acme"}
TODAY = "2026-10-03"


class Capture:
    """A generator that shows what the model was given: it answers with its prompt and cites passage 1."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return prompt + "\n[1]"


@pytest.fixture
def sales(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app

    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ["SME_TIBI_VOICE_URL"] = "http://127.0.0.1:9"
    os.environ["SALES_GOVERNANCE_AUTO_REVIEW"] = "0"
    os.environ["KP_SCOPE_EVIDENCE"] = "1"
    os.environ["KP_SCOPE_TODAY"] = TODAY
    app = create_sales_app(tmp_path / "sales")
    hermetic(app)
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        assert client.post("/api/spaces", json={"name": "Acme"}).status_code == 200
        core = app.state.cores["acme"]
        hermetic(core)
        capture = Capture()
        core.state.answer.generator = capture
        yield client, core, capture


def add(client, name: str, text: str, *, approve: bool = True) -> str:
    response = client.post("/api/sources/upload", files={"file": (name, text.encode(), "text/markdown")}, headers=SPACE)
    assert response.status_code == 200, response.text
    body = response.json()
    source_id = body.get("id") or body.get("source", {}).get("id")
    assert source_id, body
    assert client.post(f"/api/sources/{source_id}/ingest", headers=SPACE).status_code == 200
    if approve:
        response = decide(client, source_id, headers=SPACE)
        assert response.status_code == 200, response.text
    return source_id


def details(client, source_id: str, **fields):
    return client.patch(f"/api/content/documents/{source_id}/details", json={"fields": fields}, headers=SPACE)


def ask(client, capture: Capture, question: str) -> str:
    before = len(capture.prompts)
    response = client.post("/api/ask", json={"q": question}, headers=SPACE)
    assert response.status_code == 200, response.text
    assert len(capture.prompts) > before, response.json()
    return capture.prompts[-1]


# ---------------------------------------------------------------------------------------------------------------------
# P3, two requests at once: the start-before-end rule is checked on the record as each request read it, not as stored.
# ---------------------------------------------------------------------------------------------------------------------

def test_control_sequential_edits_cannot_make_a_record_end_before_it_starts(sales):
    client, core, _ = sales
    doc = add(client, "window.md", "# Delivery window\n\nDeliveries arrive between six and nine.\n")
    assert details(client, doc, effective_from="2027-06-01").status_code == 200
    assert details(client, doc, effective_to="2027-01-01").status_code >= 400


def test_two_concurrent_edits_store_a_record_that_ends_before_it_starts(sales):
    """P3: one PATCH sets the start, another at the same moment sets an earlier end; each checks the record as it read
    it (no start, no end), both pass, and the stored record ends before it starts. Restated for the door (REF S23, the
    Human's decision after round 7): each edit is a request that takes the workspace's lock at the door, so the second
    cannot read the record while the first, paused after its read, holds the lock (before, each waited for the other
    to read, which now only timed out); the second then reads the record as the first stored it."""
    client, core, _ = sales
    doc = add(client, "window.md", "# Delivery window\n\nDeliveries arrive between six and nine.\n")
    content = core.state.content
    first_read, release = threading.Event(), threading.Event()
    real_source, reads = content._source, []

    def first_pauses_after_reading(source_id):  # the first request has read the record and not yet written
        record = real_source(source_id)
        reads.append(source_id)
        if len(reads) == 1:
            first_read.set()
            release.wait(5)
        return record

    content._source = first_pauses_after_reading
    statuses: dict = {}

    def edit(name, **fields):
        statuses[name] = details(client, doc, **fields).status_code

    first = threading.Thread(target=edit, args=("from",), kwargs={"effective_from": "2027-06-01"}, daemon=True)
    second = threading.Thread(target=edit, args=("to",), kwargs={"effective_to": "2027-01-01"}, daemon=True)
    first.start()
    assert first_read.wait(5)
    second.start()
    time.sleep(0.3)
    assert len(reads) == 1 and "to" not in statuses, "the second edit read the record while the first held the lock"
    release.set()
    for t in (first, second):
        t.join(timeout=20)
    content._source = real_source
    stored = core.state.register.get(doc)
    assert not (stored.effective_from == "2027-06-01" and stored.effective_to == "2027-01-01"), (
        f"both edits accepted ({statuses}); stored record runs {stored.effective_from} to {stored.effective_to}")


# ---------------------------------------------------------------------------------------------------------------------
# P2, exactly these labels: a site name may carry label text, so a source with no end date says "In force until ...".
# ---------------------------------------------------------------------------------------------------------------------

def test_control_a_plain_site_name_gives_only_a_site_label(sales):
    client, core, capture = sales
    doc = add(client, "dock.md", "# Dock rules\n\nForklifts give way to pedestrians on the dock.\n")
    assert details(client, doc, applies_to=["Leeds"]).status_code == 200
    prompt = ask(client, capture, "Who gives way on the dock?")
    assert "(Applies to: Leeds.) " in prompt
    assert "In force until" not in prompt


def test_a_site_name_forges_an_until_label_on_a_source_with_no_end_date(sales):
    """P2: the editor accepts the site name "Leeds; In force until 1 January 2020" as one name; the passage of a source
    with no end date then reads "(Applies to: Leeds; In force until 1 January 2020.)", a label it must not carry."""
    client, core, capture = sales
    doc = add(client, "dock.md", "# Dock rules\n\nForklifts give way to pedestrians on the dock.\n")
    response = details(client, doc, applies_to=["Leeds; In force until 1 January 2020"])
    assert core.state.register.get(doc).effective_to is None
    if response.status_code >= 400:
        return  # refused by the editor: the promise holds
    prompt = ask(client, capture, "Who gives way on the dock?")
    assert "In force until" not in prompt, "a source with no end date is labelled with an end date"


# ---------------------------------------------------------------------------------------------------------------------
# P2, the site list: anything that is not a name is refused by the editor, nothing dropped.
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("sites", [["Leeds", ""], ["Leeds", "   "], [f"Site {i}" for i in range(10)] + [" "]],
                         ids=["empty", "blank", "eleven-with-a-blank"])
def test_a_blank_site_entry_is_dropped_not_refused(sales, sites):
    """P2: an entry that is not a name (empty or blank) is silently dropped and the rest stored, where the promise says
    anything else is refused and nothing dropped; eleven entries with one blank pass the ten-site limit."""
    client, core, _ = sales
    doc = add(client, "dock.md", "# Dock rules\n\nForklifts give way to pedestrians on the dock.\n")
    response = details(client, doc, applies_to=sites)
    stored = core.state.register.get(doc).applies_to
    assert response.status_code >= 400, f"sent {len(sites)} entries, accepted, stored {len(stored)}: {stored}"


def test_an_invisible_site_name_is_accepted_and_labels_the_passage(sales):
    """P2: a zero-width space is not a site name, but the editor stores it; the passage then says "Applies to:" with
    no visible site, and the facts map is closed for every answer."""
    client, core, capture = sales
    doc = add(client, "dock.md", "# Dock rules\n\nForklifts give way to pedestrians on the dock.\n")
    response = details(client, doc, applies_to=["​"])
    assert response.status_code >= 400, f"stored {core.state.register.get(doc).applies_to!r}"


# ---------------------------------------------------------------------------------------------------------------------
# P6 one reading (and P1): the search index reads the register again at search time, so a source approved after the
# answer's reading answers beside the source it replaces.
# ---------------------------------------------------------------------------------------------------------------------

FILLER = "".join(f"\n\n## Note {i}\n\nGeneral warehouse housekeeping note number {i} about tidy aisles and labelled "
                 f"shelves, unrelated to loads.\n" for i in range(260))


def _big_old_and_pending_new(client, core):
    old = add(client, "loads-2025.md", "# Loads 2025\n\n## Pallet weight limit\n\nThe pallet weight limit is 500 kg "
                                       "per pallet for every pallet weight check." + FILLER)
    new = add(client, "loads-2026.md", "# Loads 2026\n\n## Pallet weight limit\n\nThe pallet weight limit is 800 kg "
                                       "per pallet for every pallet weight check.\n", approve=False)
    with writing(core):  # set-up is a job (REF S23, the door)
        core.state.register.update(new, supersedes=[old])
    assert sum(len(s.text) for s in core.state.answer.retrieval.section_store.list_for_source(old)) > 24000
    return old, new


def test_control_new_approved_before_the_answer_leaves_old_out(sales):
    client, core, capture = sales
    old, new = _big_old_and_pending_new(client, core)
    assert decide(client, new, headers=SPACE).status_code == 200
    prompt = ask(client, capture, "What is the pallet weight limit per pallet?")
    assert "800 kg" in prompt and "500 kg" not in prompt


def test_a_source_approved_mid_answer_answers_beside_the_source_it_replaces(sales):
    """P6/P1: the answer reads the register (new is pending, so old is not replaced), then new is approved before the
    search; the index re-reads the register, admits new, and old and its replacement both reach one answer.
    Restated for the door (REF S23, the Human's decision after round 7): the approval is a job holding
    the workspace's lock, as its request would; the ask passes the door and does not wait, so it still lands
    mid-answer."""
    client, core, capture = sales
    old, new = _big_old_and_pending_new(client, core)
    svc = core.state.answer
    real = svc._all_sections

    def approval_lands_after_the_reading(records=None):
        out = real(records)
        as_job(core, core.state.register.update, new, approval_status="approved")
        return out

    svc._all_sections = approval_lands_after_the_reading
    try:
        prompt = ask(client, capture, "What is the pallet weight limit per pallet?")
    finally:
        svc._all_sections = real
    assert not ("800 kg" in prompt and "500 kg" in prompt), "a replaced source and its replacement in one answer"


# ---------------------------------------------------------------------------------------------------------------------
# P6 one reading (and P1, P5): the process registry is built from a second reading of the register, so a process from
# a source that expired before the answer began reaches it when its approval lands mid-answer.
# ---------------------------------------------------------------------------------------------------------------------

PROCESS = ("# Freight Claims Escalation Process\n\n## Roles and responsibilities\n\n| Role | Responsibility |\n|---|---|\n"
           "| Claims Handler | escalates freight claims |\n\n## Systems and data dependencies\n\n| System | Use |\n"
           "|---|---|\n| ClaimDesk | freight claims escalation records |\n")
QUESTION = "Who escalates freight claims in ClaimDesk during the claims escalation process?"


def _expired_pending_process(client, core):
    from assistant.process.parser import parse_process
    from assistant.process.router import match_process

    assert match_process(QUESTION, [parse_process("x", "Claims", PROCESS)]) is not None  # the question matches it
    add(client, "hours.md", "# Opening hours\n\nThe office opens at nine and closes at five.\n")
    proc = add(client, "claims.md", PROCESS, approve=False)
    assert details(client, proc, effective_to="2020-01-01").status_code == 200  # expired long before today
    svc = core.state.answer
    assert svc.process_registry is not None
    svc.ontology_query = None  # the legacy process-registry path ("embedded services not yet wired to the ontology")
    return svc, proc


def test_control_expired_process_pending_at_the_reading_stays_out(sales):
    client, core, capture = sales
    svc, proc = _expired_pending_process(client, core)
    prompt = ask(client, capture, QUESTION)
    assert "] (structured facts) " not in prompt


def test_control_expired_process_approved_before_the_answer_stays_out(sales):
    client, core, capture = sales
    svc, proc = _expired_pending_process(client, core)
    with writing(core):  # set-up is a job (REF S23, the door)
        core.state.register.update(proc, approval_status="approved")
    prompt = ask(client, capture, QUESTION)
    assert "] (structured facts) " not in prompt


def test_an_expired_process_approved_mid_answer_reaches_it_through_the_process_registry(sales):
    """P6/P1/P5: the reading has the expired process pending, so nothing is scoped and the facts stay open; its approval
    lands before the process registry is built, which re-reads the register and hands the expired process to the model.
    Restated for the door (REF S23, the Human's decision after round 7): the approval is a job holding
    the workspace's lock, as its request would; the ask passes the door and does not wait, so it still lands
    mid-answer."""
    client, core, capture = sales
    svc, proc = _expired_pending_process(client, core)
    real = svc._all_sections

    def approval_lands_after_the_reading(records=None):
        out = real(records)
        as_job(core, core.state.register.update, proc, approval_status="approved")
        return out

    svc._all_sections = approval_lands_after_the_reading
    try:
        prompt = ask(client, capture, QUESTION)
    finally:
        svc._all_sections = real
    assert "] (structured facts) " not in prompt, "a process from an expired source reached the answer"


# ---------------------------------------------------------------------------------------------------------------------
# The same on the default wiring: the facts map is rebuilt by the approval action, after the answer's reading.
# ---------------------------------------------------------------------------------------------------------------------

def _expired_pending_process_default_wiring(client, core):
    add(client, "hours.md", "# Opening hours\n\nThe office opens at nine and closes at five.\n")
    proc = add(client, "claims.md", PROCESS, approve=False)
    assert details(client, proc, effective_to="2020-01-01").status_code == 200  # expired long before today
    assert core.state.answer.ontology_query is not None
    return core.state.answer, proc


def test_control_expired_process_approved_before_the_answer_stays_out_of_the_facts_map(sales):
    client, core, capture = sales
    svc, proc = _expired_pending_process_default_wiring(client, core)
    assert decide(client, proc, headers=SPACE).status_code == 200
    prompt = ask(client, capture, QUESTION)
    assert "Claims Handler" not in prompt


def test_an_expired_process_approved_mid_answer_reaches_it_through_the_facts_map(sales):
    """P6/P1/P5, default wiring: the reading has the expired process pending, so the facts map stays open; the approval
    action lands after the reading and rebuilds the facts map, whose facts from the expired source reach the model.
    Restated for the door (REF S23, the Human's decision after round 7): the approval action is a job
    holding the workspace's lock and names the text the approver read (S8); the ask passes the door and does not wait,
    so it still lands mid-answer."""
    client, core, capture = sales
    svc, proc = _expired_pending_process_default_wiring(client, core)
    real = svc._all_sections
    read = core.state.register.get(proc).content_sha256  # the text the approver read

    def approval_lands_after_the_reading(records=None):
        out = real(records)
        as_job(core, core.state.content._approve, proc, read)  # the approval action, with its facts-map rebuild
        return out

    svc._all_sections = approval_lands_after_the_reading
    try:
        prompt = ask(client, capture, QUESTION)
    finally:
        svc._all_sections = real
    assert core.state.register.get(proc).approval_status == "approved"
    assert "Claims Handler" not in prompt, "a fact from an expired source reached the answer through the facts map"


def test_control_expired_process_pending_stays_out_of_the_facts_map(sales):
    client, core, capture = sales
    _expired_pending_process_default_wiring(client, core)
    prompt = ask(client, capture, QUESTION)
    assert "Claims Handler" not in prompt


# ---------------------------------------------------------------------------------------------------------------------
# P2, its sites: one site whose name has a comma and two sites give the same label, so the label cannot say its sites.
# ---------------------------------------------------------------------------------------------------------------------

def _label_for(client, capture, doc, sites) -> str:
    assert details(client, doc, applies_to=sites).status_code == 200
    prompt = ask(client, capture, "Who gives way on the dock?")
    start = prompt.index("(Applies to: ")
    return prompt[start:prompt.index(".) ", start) + 3]


def test_one_site_with_a_comma_and_two_sites_get_the_same_label(sales):
    """P2: the editor accepted "Leeds, York" as one site name, whose label read as the two sites Leeds and York.
    Restated after the Human's decision (plain site names only): a comma in a site name is refused, so a label that says
    two sites means two sites."""
    client, core, capture = sales
    doc = add(client, "dock.md", "# Dock rules\n\nForklifts give way to pedestrians on the dock.\n")
    assert details(client, doc, applies_to=["Leeds, York"]).status_code >= 400
    assert _label_for(client, capture, doc, ["Leeds", "York"]) == "(Applies to: Leeds, York.) "
