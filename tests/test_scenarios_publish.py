"""Random scenarios for publishing a new version of a document (REF S23, a staged publish).

Promises, checked against a model of the live version kept beside the real stores (scope on or off):
- S1/S2: a reader that holds a document's record takes that record's text and passages or none of them, never another
  version's; until a publish's record is written, readers hold the live version;
- S3: a publish that fails at any step (an unreadable text, the text, passages or record write) leaves the live version
  whole: its text, passages, version and approval;
- S4: a version number is given only to a version that went live, and names one text;
- S5: after a publish the facts map is in step with the register and holds no fact from a text that is not live;
- two publishes at once, or a publish with a details edit, are applied one after the other.

Scenario kinds: publishes that succeed; a text that cannot be split; a publish failing at staging the text or the
passages, or at the record's write (the commit); an answer (scope on or off) or a facts-map rebuild landing inside the
swap, before the record is written; a committed version whose move into place fails (readers move it) or never runs
(a crash: the next writer settles it); an earlier text published again (a restore); a history entry written but
reported failed; the event store down;
two publishes at once; a details edit during a publish. The red teams' findings of 3 October 2026 (REF H3b, rounds 5
and 6) are kinds here.
"""
import hashlib
import os
import socket
import sqlite3
import threading

import pytest
from fastapi.testclient import TestClient
from iam_helpers import sign_in
from scenarios import explore
from test_space_leaks import hermetic, refuse

HEAD = {"X-OpsAtlas-Space": "acme"}


def process_text(marker: str) -> bytes:
    return (f"# Returns release\n\nThe returns desk handles every request ({marker}).\n\n"
            f"## Roles and responsibilities\n\n| Role | Responsibility |\n|---|---|\n"
            f"| Clerk {marker} | Approves the returns request and records it |\n").encode()


class Echo:
    def generate(self, prompt: str) -> str:
        return prompt + "\n[1]"


@pytest.fixture
def desk(tmp_path, monkeypatch):
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ.update({"SME_TIBI_VOICE_URL": "http://127.0.0.1:9", "SALES_GOVERNANCE_AUTO_REVIEW": "0",
                       "KP_SCOPE_TODAY": "2026-10-03"})
    app = create_sales_app(tmp_path / "sales")
    hermetic(app)
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        assert client.post("/api/spaces", json={"name": "Acme"}).status_code == 200
        core = app.state.cores["acme"]
        hermetic(core)
        up = client.post("/api/sources/upload", files={"file": ("returns.md", process_text("LIVE0"), "text/markdown")},
                         headers=HEAD)
        sid = up.json()["id"] if "id" in up.json() else up.json()["source"]["id"]
        assert client.post(f"/api/sources/{sid}/ingest", headers=HEAD).status_code == 200
        assert client.post(f"/api/governance/sources/{sid}/approve", headers=HEAD).status_code == 200
        core.state.answer.generator = Echo()
        yield client, core, sid


def _facts_dump(core) -> str:
    store = core.state.answer.ontology_query.store
    conn = store._connect()
    try:
        return " ".join(str(row) for row in conn.execute("SELECT properties FROM objects").fetchall())
    finally:
        conn.close()


def one_run(run, client, core, sid, live):
    register, content, store = core.state.register, core.state.content, core.state.content.section_store

    def check(where):
        record = register.get(sid)
        run.promise("the live version is the model's", (record.version, record.approval_status) == (live["version"], "approved"),
                    f"{where}: {record.version} {record.approval_status} vs {live['version']}")
        run.promise("the text is the record's", register.read_content(sid, sha=record.content_sha256) == live["text"], where)
        passages = store.list_for_source(sid, sha=record.content_sha256)  # a reader holding the record moves any not moved
        run.promise("the passages are the record's", bool(passages) and store.fingerprint(sid) in (record.content_sha256, None),
                    where)
        named, rows = content.current_version(sid), [r for r in content.store.versions(sid) if r.get("committed", 1)]
        text_sha = hashlib.sha256(live["text"].decode("utf-8", "replace").encode()).hexdigest()
        run.promise("the record names its version", named is not None and named["n"] == record.history_n
                    and any(r["n"] == named["n"] and r["sha"] == text_sha for r in rows), f"{where}: {named}")
        run.promise("a version number names one text",
                    len({r["sha"] for r in rows if r["source_version"] == record.version}) == 1, where)
        approved = [r for r in register.list() if r.approval_status == "approved"]
        dump = _facts_dump(core)
        stale = [m for m in live["dead"] if m in dump]
        run.promise("no fact from a text that is not live", not stale, f"{where}: {stale}")
        if live["in_step"]:
            run.promise("the facts map is in step after a publish", core.state.answer._facts_in_step(approved), where)

    def publish(text: bytes) -> bool:
        try:
            content._write_version(register.get(sid), text, approve=True)
            return True
        except Exception:
            return False

    for k in range(run.rng.randint(2, 6)):
        marker = f"MK{run.seed}x{k}"
        text = process_text(marker)
        kind = run.rng.choice(["publish", "publish", "unreadable", "fail-text", "fail-passages", "fail-record",
                               "reader-inside", "rebuild-inside", "two-at-once", "edit-during", "move-fails",
                               "crash-after-commit", "restore", "history-lands-then-fails", "events-down"])
        run.step(kind, marker)
        if kind == "publish":
            ok = publish(text)
            run.promise("a readable publish succeeds", ok, marker)
        elif kind == "move-fails":  # committed, but the move into place fails: the next reader holding it moves it
            real_moves = register.promote_content, store.promote_for_source
            register.promote_content = store.promote_for_source = lambda source_id: (_ for _ in ()).throw(OSError("busy"))
            try:
                ok = publish(text)
            finally:
                register.promote_content, store.promote_for_source = real_moves
            run.promise("a committed publish is published", ok, marker)
        elif kind == "crash-after-commit":  # red team, S23 round 2: the move never runs; the next writer settles it
            real_move = content._move_into_place
            content._move_into_place = lambda source_id: None
            try:
                ok = publish(text)
            finally:
                content._move_into_place = real_move
            run.promise("a committed publish is published", ok, marker)
        elif kind == "restore":  # red team, S23 round 2: an earlier text published again, named as the new version
            earlier = [m for m in live["dead"] if m.startswith("MK") or m == "LIVE0"]
            if earlier:
                text = process_text(run.rng.choice(earlier))
                marker = text.decode().split("(")[1].split(")")[0]
                live["dead"] = [m for m in live["dead"] if m != marker]
            ok = publish(text)
            run.promise("a readable publish succeeds", ok, marker)
        elif kind == "history-lands-then-fails":  # red team, S23 round 3: the entry is written, the caller told it was not
            real_add = content.store.add_version

            def lands_then_fails(*args, **kwargs):
                real_add(*args, **kwargs)
                raise sqlite3.OperationalError("disk I/O error")
            content.store.add_version = lands_then_fails
            try:
                ok = publish(text)
            finally:
                content.store.add_version = real_add
            run.promise("a publish whose history entry failed fails", not ok, marker)
        elif kind == "events-down":  # red team, S23 round 3: no event failure fails a publish that went live
            real_record = content.events.record if content.events is not None else None
            if content.events is not None:
                content.events.record = lambda *a, **k: (_ for _ in ()).throw(OSError("event store down"))
            try:
                ok = publish(text)
            finally:
                if content.events is not None:
                    content.events.record = real_record
            run.promise("a publish is not failed by its events", ok, marker)
        elif kind == "unreadable":
            ok = publish(b"   \n")
            run.promise("an unreadable text is refused", not ok, marker)
        elif kind.startswith("fail-") or kind in ("reader-inside", "rebuild-inside"):
            where = kind[5:] if kind.startswith("fail-") else run.rng.choice(["text", "passages", "record"])
            fail = kind.startswith("fail-") or run.rng.random() < 0.5
            seen = {}
            real = {"text": register.stage_content, "passages": store.stage_for_source, "record": register.update}

            def inside(*args, **kwargs):
                is_new = (where == "text" and args[1] == text) or (where == "passages" and args[0] == sid) or \
                         (where == "record" and args[0] == sid and "content_sha256" in kwargs)
                if is_new and "done" not in seen:
                    seen["done"] = True
                    if where != "record":
                        real[where](*args, **kwargs)  # the step lands, then something happens before the next
                    if kind == "reader-inside":
                        os.environ["KP_SCOPE_EVIDENCE"] = run.rng.choice(["0", "1"])
                        seen["prompt"] = core.state.answer.answer("Who approves the returns request?", routing_mode="rag_only").answer
                    elif kind == "rebuild-inside":
                        core.state.rebuild_ontology()
                    if fail:
                        raise OSError("disk full")
                    if where != "record":
                        return None
                return real[where](*args, **kwargs)
            target = {"text": (register, "stage_content"), "passages": (store, "stage_for_source"),
                      "record": (register, "update")}[where]
            setattr(*target, inside)
            try:
                ok = publish(text)
            finally:
                setattr(*target, real[where])
            run.promise("the publish fails exactly when a step fails", ok == (not fail), f"{kind} at {where}: ok {ok}")
            if "prompt" in seen:
                run.promise("a reader inside the swap takes no text of the new version", marker not in seen["prompt"], where)
        elif kind == "two-at-once":
            other = process_text(marker + "b")
            results = {}
            jobs = [threading.Thread(target=lambda t=t: results.__setitem__(t, publish(t))) for t in (text, other)]
            for job in jobs:
                job.start()
            for job in jobs:
                job.join()
            run.promise("both publishes are applied, one after the other", all(results.values()), str(results))
            final = register.read_content(sid)
            run.promise("the later one is live", final in (text, other), "")
            for t in (text, other):
                if t != final:
                    live["dead"].append(t.decode().split("(")[1].split(")")[0])
            live.update(version=live["version"] + 2, text=final, sha=register.get(sid).content_sha256, in_step=True)
            check(kind)
            continue
        else:  # a details edit during the publish
            day = run.rng.choice(["2027-01-01", "2026-12-31"])
            edit = threading.Thread(target=lambda: client.patch(f"/api/content/documents/{sid}/details",
                                                               json={"fields": {"effective_to": day}}, headers=HEAD))
            real_stage = register.stage_content

            def stage_then_edit(source_id, data):
                real_stage(source_id, data)
                if data == text and not edit.is_alive() and edit.ident is None:
                    edit.start()  # the edit waits for the swap's lock
            register.stage_content = stage_then_edit
            try:
                ok = publish(text)
            finally:
                register.stage_content = real_stage
            edit.join(10)
            run.promise("the edit is applied after the publish", register.get(sid).effective_to == day, "")
            core.state.register.update(sid, effective_to=None)
        if ok:
            live["dead"].append(live["marker"])
            live.update(version=live["version"] + 1, text=text, sha=register.get(sid).content_sha256, marker=marker,
                        in_step=True)
        else:
            live["dead"].append(marker)
        check(f"after {kind}")


def test_publishing_keeps_its_promises_over_random_scenarios(desk):
    client, core, sid = desk
    record = core.state.register.get(sid)
    live = {"version": record.version, "text": core.state.register.read_content(sid), "sha": record.content_sha256,
            "marker": "LIVE0", "dead": [], "in_step": True}
    runs = max(1, int(os.environ.get("OPSATLAS_SCENARIO_RUNS", "2000")) // 20)
    assert explore("publish", lambda run: one_run(run, client, core, sid, live), runs=runs) >= 1


def test_sqlite_is_available():  # the facts map's store is SQLite; the dump above reads it directly
    assert sqlite3.sqlite_version
