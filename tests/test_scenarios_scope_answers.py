"""Random scenarios for scope through the answer service (REF H3b): what reaches an answer, with which label, and on
which reading of the register.

Promises (the Human's decisions of 3 October 2026), checked by an oracle written from the promise text. Hermetic: no
connection leaves the process, and the model echoes its prompt, so every passage it was given shows with its label.
- left out: no passage from an approved source expired today, replaced today or with an unreadable date reaches an
  answer, by the documents or the facts map; nor does a pending source's;
- facts only when nothing is left out or labelled;
- labelled, exactly: each passage that reaches it carries the label its source had when the answer began;
- one reading: each answer is judged on one reading of the register, taken as it begins; an edit that lands while it
  is prepared applies from the next answer, which is judged on the register as edited (the Human's decision after the
  third round of the stop rule: no mid-answer recheck); no answer is withheld for scope;
- no guessing: another question over the same register gives the same passages with the same labels;
- nothing scoped: with no source scoped, the answer is the one scope off gives.

Scenario kinds: answers from the whole guide, through retrieval (a large unrelated document in force or not) or from
the facts map (a process document, with nothing scoped, which opens it); dates in force, ending, later, expired,
unreadable (trailing digits) and basic ISO; sites with punctuation, months and two sites; supersedes; a pending
source; questions naming a site, a month, a year or nothing; mid-answer edits to a source the answer uses or does not
use, an approval (scoped or not; written straight to the register, or by the approval action, which rebuilds the
search index and the facts map, during generation or just after the reading), a withdrawal of approval, and a new
supersede, each followed by the next answer. The red teams' findings of 3 October 2026 are kinds here.
"""
import os
import socket
from datetime import date

import pytest
from fastapi.testclient import TestClient
from iam_helpers import sign_in
from scenarios import explore
from test_space_leaks import hermetic, refuse

TODAY = date(2026, 10, 3)
HEAD = {"X-OpsAtlas-Space": "acme"}
DATES = [None, None, None, "2026-01-01", "2026-10-03", "2026-10-02", "2027-01-01", "2026-12-31", "2025-12-31",
         "2026-12-311", "20261231"]
SITES = [[], [], [], ["Leeds"], ["March"], ["DC (A)"], ["Leeds", "Bristol"]]
QUESTIONS = ["What is the returns process?", "What is the returns process at Leeds?", "What is the returns process in March?",
             "What will the returns process be in 2027?", "What is the returns process at DC (A)?", "Which systems are used?"]
FIELDS = ("effective_from", "effective_to", "applies_to", "supersedes")
# Over the 24,000-character full-context limit, with no word of the questions: while it is in force, answers go through
# retrieval, and what an answer rests on is the passages it considered.
PROCESS = """# Returns release

Doc D5 says: the Returns Warden handles every returns request after checking it in RETVAULT.

## Roles and responsibilities

Doc D5 says: the roles are these.

| Role | Responsibility |
|---|---|
| Returns Warden | Approves the returns request and records it in RETVAULT |
| Store manager | Raises the returns request |

## Systems and data dependencies

Doc D5 says: the systems are these.

| System | Purpose |
|---|---|
| RETVAULT | Holds the returns ledger and the approval record |

## Process steps

Doc D5 says: the steps are these.

1. The store manager raises the returns request.
2. The Returns Warden checks it in RETVAULT.
3. The Returns Warden approves the returns request.
"""
# The pending source is a process too, so an approval that lands mid-answer could bring its facts in by the facts map.
PENDING_PROCESS = PROCESS.replace("Doc D5", "Doc D4").replace("Returns Warden", "Parcel Clerk").replace("RETVAULT", "PARCELDB")
FACT_OF = {4: "PARCELDB", 5: "RETVAULT"}
FILLER = "# Lighting\n\n" + "\n\n".join(f"## Bay {i}\n\nWarehouse lighting circuit {i} uses LED panels on timer {i}." for i in range(700))


class HookEcho:
    """The echo model, with an edit that lands while the answer is being prepared."""
    def __init__(self, edit=None):
        self.edit = edit

    def generate(self, prompt: str) -> str:
        if self.edit is not None:
            edit, self.edit = self.edit, None
            edit()
        return prompt + "\n[1]"


@pytest.fixture
def space(tmp_path, monkeypatch):
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ.update({"SME_TIBI_VOICE_URL": "http://127.0.0.1:9", "SALES_GOVERNANCE_AUTO_REVIEW": "0",
                       "KP_SCOPE_EVIDENCE": "1", "KP_SCOPE_TODAY": TODAY.isoformat()})
    app = create_sales_app(tmp_path / "sales")
    hermetic(app)
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        assert client.post("/api/spaces", json={"name": "Acme"}).status_code == 200
        core = app.state.cores["acme"]
        hermetic(core)
        ids = []
        for n in range(6):
            plain = f"# Returns note {n}\n\nDoc D{n} says: a customer brings the item back within 30 days.\n"
            text = PROCESS if n == 5 else PENDING_PROCESS if n == 4 else plain
            up = client.post("/api/sources/upload", files={"file": (f"d{n}.md", text.encode(), "text/markdown")}, headers=HEAD)
            sid = up.json()["id"] if "id" in up.json() else up.json()["source"]["id"]
            assert client.post(f"/api/sources/{sid}/ingest", headers=HEAD).status_code == 200
            if n != 4:  # d4 stays pending
                assert client.post(f"/api/governance/sources/{sid}/approve", headers=HEAD).status_code == 200
            ids.append(sid)
        up = client.post("/api/sources/upload", files={"file": ("lighting.md", FILLER.encode(), "text/markdown")}, headers=HEAD)
        filler = up.json()["id"] if "id" in up.json() else up.json()["source"]["id"]
        assert client.post(f"/api/sources/{filler}/ingest", headers=HEAD).status_code == 200
        assert client.post(f"/api/governance/sources/{filler}/approve", headers=HEAD).status_code == 200
        yield client, core, ids, filler


def _period(fields):
    def read(value):
        if value is None:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return False
    start, end = read(fields["effective_from"]), read(fields["effective_to"])
    if start is False or end is False or (end is not None and end < TODAY):
        return "out"
    if start is not None and start > TODAY:
        return "later" if end is None or start <= end else "out"
    return "now"


def _label(fields):
    parts = []
    start, end = fields["effective_from"], fields["effective_to"]
    if _period(fields) == "later":
        day = date.fromisoformat(start)
        parts.append(f"In force from {day.day} {day:%B %Y}")
    elif _period(fields) == "now" and end:
        day = date.fromisoformat(end)
        parts.append(f"In force until {day.day} {day:%B %Y}")
    if fields["applies_to"]:
        parts.append(f"Applies to: {', '.join(fields['applies_to'])}")
    return f"({'; '.join(parts)}.) " if parts else ""


def _judge(state):
    """The oracle: for each source, whether scope allows it and its label, from the promise text."""
    approved = {sid for sid, f in state.items() if f["approved"]}
    replaced = {old for sid in approved if _period(state[sid]) == "now" for old in state[sid]["supersedes"]}
    return {sid: (_period(f) != "out" and sid not in replaced, _label(f)) for sid, f in state.items()}


def _doc_passages(answer: str) -> dict[str, set[str]]:
    """The source documents' passages as given to the model, labels included, by document."""
    out: dict[str, set[str]] = {}
    for line in answer.splitlines():
        if line.startswith("[") and "Doc D" in line:
            body = line.split("] ", 1)[1]
            out.setdefault(body.split("Doc D", 1)[1][:1], set()).add(body)
    return out


def _labels(passages: dict[str, set[str]]) -> dict[str, set[str]]:
    """Each document's labels: what its passages say between their heading and their text."""
    return {doc: {body.split(") ", 1)[1].split("Doc D", 1)[0] for body in bodies} for doc, bodies in passages.items()}


def _check(run, result, ids, filler, state, judged, when):
    """The promises for one answer, against the register it was judged on."""
    allowed = [sid for sid in ids if state[sid]["approved"] and judged[sid][0]]
    closed = any(f["approved"] and (not judged[sid][0] or judged[sid][1]) for sid, f in state.items())
    run.promise("no answer is withheld for scope", result["mode"] != "evidence-changed", f"{when}: {result['mode']}")
    used = allowed  # the whole guide: every allowed source is given to the model
    if result["mode"] == "retrieval" or result.get("considered"):
        used = sorted({c.split("#")[0] for c in result.get("considered") or []})
        run.promise("retrieval considers only what scope allows", set(used) <= set(allowed) | {filler}, f"{when}: {used}")
    facts = result.get("answer_path") in ("oag", "rag+ontology")
    run.promise("facts only when nothing is left out or labelled", not (facts and closed), f"{when}: {result.get('answer_path')}")
    for n, fact in FACT_OF.items():
        if not (state[ids[n]]["approved"] and judged[ids[n]][0]):
            run.promise("left out, facts included", fact not in result["answer"], f"{when}: d{n}'s system {fact} answered")
    if not allowed:
        run.promise("nothing allowed, none of it answers", "Doc D" not in result["answer"], f"{when}: {result['mode']}")
        return
    if result["refused"] or result.get("answer_path") == "oag":
        return
    for n, sid in enumerate(ids):
        if sid in used:
            run.promise("labelled, exactly", f") {judged[sid][1]}Doc D{n} says" in result["answer"],
                        f"{when}: d{n} should say {judged[sid][1]!r}")
        elif sid not in allowed:
            run.promise("left out", f"Doc D{n} says" not in result["answer"], f"{when}: d{n} reached the answer")


def one_run(run, client, core, ids, filler):
    state = {}
    plain = run.rng.random() < 0.25  # nothing scoped: the facts map is open
    for n, sid in enumerate(ids):
        fields = {"effective_from": run.rng.choice(DATES), "effective_to": run.rng.choice(DATES),
                  "applies_to": run.rng.choice(SITES), "supersedes": [], "approved": n != 4}
        if plain:
            fields.update(effective_from=None, effective_to=None, applies_to=[])
        elif run.rng.random() < 0.15:
            fields["supersedes"] = [run.rng.choice([i for i in ids if i != sid])]
        state[sid] = fields
        core.state.register.update(sid, **{k: fields[k] for k in FIELDS},
                                   approval_status="approved" if fields["approved"] else "pending")
    retrieval = plain or run.rng.random() < 0.35
    state[filler] = {"effective_from": None, "effective_to": None if retrieval else "2025-12-31", "applies_to": [],
                     "supersedes": [], "approved": True}
    core.state.register.update(filler, effective_to=state[filler]["effective_to"])
    core.state.rebuild_ontology()  # the facts map in step with the register as each run begins
    question = run.rng.choice(QUESTIONS)
    run.step("register", "; ".join(f"d{n}: {state[s]}" for n, s in enumerate(ids)))
    before = _judge(state)
    allowed = [sid for sid in ids if state[sid]["approved"] and before[sid][0]]
    used = allowed  # the whole guide: every allowed source is given to the model

    kind = run.rng.choice(["none", "none", "edit-used", "edit-unused", "approve", "approve-rebuild", "approve-after-reading",
                           "unapprove", "supersede"])
    after_state = {sid: dict(f) for sid, f in state.items()}
    change: dict = {}
    if kind == "edit-used" and used or kind == "edit-unused" and [s for s in ids if s not in used]:
        target = run.rng.choice(used if kind == "edit-used" else [s for s in ids if s not in used])
        field = run.rng.choice(["effective_from", "effective_to", "applies_to"])
        value = run.rng.choice(SITES if field == "applies_to" else DATES)
        change = {"sid": target, field: value}
    elif kind in ("approve", "approve-rebuild", "approve-after-reading"):
        change = {"sid": ids[4], "approval_status": "approved"}
    elif kind == "unapprove" and used:
        change = {"sid": run.rng.choice(used), "approval_status": "pending"}
    elif kind == "supersede":
        new, old = run.rng.sample(ids, 2)
        change = {"sid": new, "supersedes": [old]}
    if change:
        target = change["sid"]
        updates = {k: v for k, v in change.items() if k != "sid"}
        for key, value in updates.items():
            after_state[target]["approved" if key == "approval_status" else key] = (
                value == "approved" if key == "approval_status" else value)
        edit = lambda: core.state.register.update(target, **updates)  # noqa: E731
        if kind == "approve-rebuild":  # the approval action, which rebuilds the search index and the facts map
            edit = lambda: core.state.content._approve(ids[4])  # noqa: E731
    else:
        edit = None
    run.step("ask", f"{question!r} with {kind} {change}")
    service, real_sections = core.state.answer, core.state.answer._all_sections
    if kind == "approve-after-reading":  # red team, round 4: the approval lands after the reading, before any search
        edit = None

        def after_the_reading(records=None):
            service._all_sections = real_sections
            out = real_sections(records)
            core.state.content._approve(ids[4])
            return out
        service._all_sections = after_the_reading
    core.state.answer.generator = HookEcho(edit)
    try:
        result = client.post("/api/ask", json={"q": question}, headers=HEAD).json()
    finally:
        service._all_sections = real_sections
    after = _judge(after_state)
    _check(run, result, ids, filler, state, before, "this answer")
    if change:  # the next answer is judged on the register as edited
        core.state.answer.generator = HookEcho()
        _check(run, client.post("/api/ask", json={"q": question}, headers=HEAD).json(), ids, filler, after_state, after,
               "the next answer")
    if result["refused"] or result.get("answer_path") == "oag":
        return
    answer = result["answer"]
    if kind == "none" and run.rng.random() < 0.3:
        other = client.post("/api/ask", json={"q": run.rng.choice(QUESTIONS)}, headers=HEAD).json()
        mine, theirs = _doc_passages(answer), _doc_passages(other["answer"])
        if result["mode"] == other["mode"] == "full-context":  # the whole guide: the same passages, whatever is asked
            run.promise("no guessing", mine == theirs, "another question, other passages")
        else:  # retrieval follows the question; a passage both answers were given carries the same label
            mine, theirs = _labels(mine), _labels(theirs)
            run.promise("no guessing", all(mine[k] == theirs[k] for k in mine.keys() & theirs.keys()), "another label")
    scoped = any(f[k] for f in after_state.values() for k in FIELDS)
    if kind == "none" and not scoped:
        os.environ["KP_SCOPE_EVIDENCE"] = "0"
        try:
            off = client.post("/api/ask", json={"q": question}, headers=HEAD).json()
        finally:
            os.environ["KP_SCOPE_EVIDENCE"] = "1"
        run.promise("nothing scoped answers as scope off", off["answer"] == answer)


def test_scope_keeps_its_promises_through_the_answer_service(space):
    client, core, ids, filler = space
    runs = max(1, int(os.environ.get("OPSATLAS_SCENARIO_RUNS", "2000")) // 10)
    assert explore("scope-answers", lambda run: one_run(run, client, core, ids, filler), runs=runs) >= 1
