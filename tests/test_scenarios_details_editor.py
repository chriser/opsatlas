"""Random scenarios for the details editor's scope fields (REF H3b): the dates and sites scope reads.

Promises (the Human's decisions of 3 October 2026), checked against a model kept beside the real record, written from
the promise text:
- one date reader: the value as sent is read as scope reads it (Python's ISO 8601 date reader); only null or "" clears
  a date; anything else scope cannot read is refused; a date is stored in one form (YYYY-MM-DD);
- the record as stored never ends before it starts, whatever the edits and however they interleave;
- plain site names: a list of names, ten at most, each up to 60 letters, digits, spaces, hyphens, apostrophes and full
  stops with at least one letter or digit; anything else (a string, a non-text entry, a blank or invisible entry, a
  comma, semicolon or bracket) is refused, nothing split or dropped;
- a refused edit changes nothing; two edits at once are applied one after the other.

Scenario kinds: dates in extended, basic and week ISO form, null and "", unreadable text (trailing digits, loosely
written, padded, another order), numbers, booleans, lists and objects; both dates in one edit; site lists that are
plain, too long, with a blank, invisible or underscored entry, punctuation, a name too long, not a list or not text;
two edits at once (one setting the start and one the end). The red teams' findings of rounds 3 and 4 are kinds here.
"""
import os
import socket
import threading
import unicodedata
from datetime import date

import pytest
from fastapi.testclient import TestClient
from iam_helpers import sign_in
from scenarios import explore
from test_space_leaks import hermetic, refuse

HEAD = {"X-OpsAtlas-Space": "acme"}
GOOD_DATES = ["2026-12-31", "20270101", "2027-W01-5", "2025-06-30", "2028-02-29", "2027-06-01"]
BAD_DATES = ["2026-12-311", "2026-01-015", "2027-1-1", " 2027-01-01", "2027-01-01 ", "31/12/2026", "soon", "2027-02-30",
             0, False, True, [], 20261231, 1.5, {"day": 1}]
CLEAR = [None, ""]
GOOD_SITES = ["Leeds", "Bristol head office", "St John's Wood", "St. Ives", "Zürich", "Bristol-on-Avon", "Ward 7",
              "  Leeds   distribution  centre "]
BAD_SITES = ["DC (A)", "Leeds, York", "Leeds; In force until 1 January 2020", "", "   ", "​", "Leeds​", "A_B",
             "x" * 61, "...", 42, None]


def _day(value):
    """The promise's reading of a date: None to clear, a day, or False when scope cannot read it."""
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value)
    except ValueError:
        return False


def _plain(name: str) -> bool:
    return 0 < len(name) <= 60 and all(ch.isalnum() or ch in " -.'’" for ch in name) and any(ch.isalnum() for ch in name)


def _sites(value):
    """The promise's reading of a site list: the names to store, or False when it is refused."""
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(a, str) for a in value):
        return False
    names = [" ".join(unicodedata.normalize("NFC", a).split()) for a in value]
    return names if len(names) <= 10 and all(_plain(n) for n in names) else False


def _apply(model: dict, fields: dict):
    """The record after an edit, or None when the edit is refused."""
    new = dict(model)
    if "effective_from" in fields or "effective_to" in fields:
        for key in ("effective_from", "effective_to"):
            if key in fields:
                day = _day(fields[key])
                if day is False:
                    return None
                new[key] = day.isoformat() if day else None
        start, end = (date.fromisoformat(new[k]) if new[k] else None for k in ("effective_from", "effective_to"))
        if start and end and end < start:
            return None
    if "applies_to" in fields:
        sites = _sites(fields["applies_to"])
        if sites is False:
            return None
        new["applies_to"] = sites
    return new


@pytest.fixture
def editor(tmp_path, monkeypatch):
    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ.update({"SME_TIBI_VOICE_URL": "http://127.0.0.1:9", "SALES_GOVERNANCE_AUTO_REVIEW": "0"})
    app = create_sales_app(tmp_path / "sales")
    hermetic(app)
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        assert client.post("/api/spaces", json={"name": "Acme"}).status_code == 200
        core = app.state.cores["acme"]
        hermetic(core)
        up = client.post("/api/sources/upload", headers=HEAD,
                         files={"file": ("window.md", b"# Delivery window\n\nDeliveries arrive between six and nine.\n",
                                         "text/markdown")})
        sid = up.json()["id"] if "id" in up.json() else up.json()["source"]["id"]
        assert client.post(f"/api/sources/{sid}/ingest", headers=HEAD).status_code == 200
        yield client, core, sid


def one_run(run, client, core, sid):
    core.state.register.update(sid, effective_from=None, effective_to=None, applies_to=[])
    model = {"effective_from": None, "effective_to": None, "applies_to": []}

    def stored():
        record = core.state.register.get(sid)
        return {"effective_from": record.effective_from, "effective_to": record.effective_to, "applies_to": record.applies_to}

    def a_date():
        roll = run.rng.random()
        return run.rng.choice(GOOD_DATES if roll < 0.55 else BAD_DATES if roll < 0.85 else CLEAR)

    def a_site_list():
        roll = run.rng.random()
        if roll < 0.08:
            return run.rng.choice(["Leeds", 42, {"site": "Leeds"}, None])  # not a list (None clears)
        names = run.rng.sample(GOOD_SITES, run.rng.randint(0, 4))
        if roll < 0.45:
            names.insert(run.rng.randint(0, len(names)), run.rng.choice(BAD_SITES))
        elif roll < 0.55:
            names = [f"Site {i}" for i in range(run.rng.choice([10, 11, 12]))]
        return names

    for _ in range(run.rng.randint(2, 8)):
        kind = run.rng.choice(["date", "date", "pair", "sites", "sites", "at-once"])
        if kind == "at-once":
            first, second = {"effective_from": a_date()}, {"effective_to": a_date()}
            run.step(kind, f"{first} with {second}")
            real_source, waited, barrier = core.state.content._source, [], threading.Barrier(2)

            def both_read_first(source_id):  # each tries to read before either writes; the editor's lock decides
                record = real_source(source_id)
                if len(waited) < 2:
                    waited.append(1)
                    try:
                        barrier.wait(timeout=0.15)
                    except threading.BrokenBarrierError:
                        pass
                return record
            core.state.content._source = both_read_first
            try:
                jobs = [threading.Thread(target=lambda f=f: client.patch(f"/api/content/documents/{sid}/details",
                                                                       json={"fields": f}, headers=HEAD))
                        for f in (first, second)]
                for job in jobs:
                    job.start()
                for job in jobs:
                    job.join()
            finally:
                core.state.content._source = real_source
            outcomes = []
            for a, b in ((first, second), (second, first)):
                after_a = _apply(model, a) or model
                outcomes.append(_apply(after_a, b) or after_a)
            run.promise("two edits at once are applied one after the other", stored() in outcomes, f"{stored()} not in {outcomes}")
            model = stored()
        else:
            if kind == "date":
                fields = {run.rng.choice(["effective_from", "effective_to"]): a_date()}
            elif kind == "pair":
                fields = {"effective_from": a_date(), "effective_to": a_date()}
            else:
                fields = {"applies_to": a_site_list()}
            run.step(kind, repr(fields))
            response = client.patch(f"/api/content/documents/{sid}/details", json={"fields": fields}, headers=HEAD)
            expected = _apply(model, fields)
            if expected is None:
                run.promise("what scope cannot read is refused", 400 <= response.status_code < 500,
                            f"{fields} gave {response.status_code}")
            else:
                run.promise("what scope can read is accepted", response.status_code == 200, f"{fields}: {response.text[:200]}")
                model = expected
            run.promise("the record is what the edits make it", stored() == model, f"{stored()} vs {model}")
        record = stored()
        start, end = (_day(record[k]) for k in ("effective_from", "effective_to"))
        run.promise("dates are stored in one form", all(v is None or (isinstance(v, str) and len(v) == 10) for v in
                                                        (record["effective_from"], record["effective_to"])), str(record))
        run.promise("the record never ends before it starts", not (start and end and end < start), str(record))


def test_the_details_editor_keeps_its_promises_over_random_scenarios(editor):
    client, core, sid = editor
    runs = max(1, int(os.environ.get("OPSATLAS_SCENARIO_RUNS", "2000")) // 20)
    assert explore("details-editor", lambda run: one_run(run, client, core, sid), runs=runs) >= 1
