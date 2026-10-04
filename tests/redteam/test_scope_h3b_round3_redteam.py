"""Red team, round 3, for REF H3b (scope). Each test is hermetic: every outbound connection is refused, the model is a
local echo (its answer is its whole prompt, so the evidence and its labels show in the answer), embeddings are local.

The breaks found here triggered the stop rule a third time. The Human chose (3 October 2026): no mid-answer recheck
(each answer is judged on one reading of the register and one day, both taken as it begins; an edit that lands while it
is prepared applies from the next answer), and the details editor hands the value as sent to scope's one date reader
and checks the record as it will be stored. The interleaving tests are restated to that promise; the editor's breaks
hold as the red team wrote them. A withdrawal of approval mid-answer, and the avatar route's missing delivery checks,
belong to REF S19b #2137 and S16b #2136.
"""
import os
import socket
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from iam_helpers import sign_in  # noqa: E402
from test_space_leaks import hermetic, refuse  # noqa: E402

from tests.door_helpers import as_job, decide, writing

HEAD = {"X-OpsAtlas-Space": "acme"}
QUESTION = "How does the returns desk refund a parcel?"


def document(marker: str, title: str, flavour: str) -> str:
    return (f"# {title}\n\nThe returns desk logs each {flavour} parcel in {marker} before the refund is made.\n\n"
            f"## Steps\n\n1. The clerk logs the {flavour} parcel in {marker}.\n2. The supervisor signs the {flavour} "
            f"refund.\n3. The refund is paid.\n")


class Echo:
    """A model that answers with its whole prompt; ``during(n)`` runs inside its n-th call (an edit landing while the
    answer is prepared)."""

    def __init__(self, during=None) -> None:
        self.during, self.calls = during, 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        if self.during is not None:
            self.during(self.calls)
        return prompt + "\n[1]"


@pytest.fixture
def acme(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.opsatlas_sales.app import create_sales_app
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    os.environ["SME_TIBI_VOICE_URL"] = "http://127.0.0.1:9"
    os.environ["SALES_GOVERNANCE_AUTO_REVIEW"] = "0"
    app = create_sales_app(tmp_path / "sales")
    hermetic(app)
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {sign_in(client, app)}"})
        assert client.post("/api/spaces", json={"name": "Acme"}).status_code == 200
        core = app.state.cores["acme"]
        hermetic(core)
        os.environ["KP_SCOPE_EVIDENCE"] = "1"
        os.environ["KP_SCOPE_TODAY"] = "2026-10-03"

        def add(marker: str, title: str, flavour: str) -> str:
            up = client.post("/api/sources/upload", headers=HEAD,
                             files={"file": (f"{marker}.md", document(marker, title, flavour).encode(), "text/markdown")})
            assert up.status_code == 200, up.text
            sid = up.json()["id"] if "id" in up.json() else up.json()["source"]["id"]
            assert client.post(f"/api/sources/{sid}/ingest", headers=HEAD).status_code == 200
            approved = decide(client, sid, headers=HEAD)
            assert approved.status_code == 200, approved.text
            return sid

        yield client, core, add


def ask(client) -> dict:
    response = client.post("/api/ask", json={"q": QUESTION}, headers=HEAD)
    assert response.status_code in (200, 409), response.text
    return response.json() if response.status_code == 200 else {"answer": "", "refused": True, "status": 409}


def given(body: dict, marker: str) -> bool:
    return not body.get("refused") and marker in body.get("answer", "")


# ---- Midnight: "today" is taken as the answer begins, for the whole answer -------------------------------------------

class Clock(date):
    """The service's ``date``: today is whatever the test says it is now."""
    now = date(2026, 12, 31)

    @classmethod
    def today(cls):
        return cls.now


@pytest.fixture
def clock(monkeypatch):
    import assistant.answer.service as service
    os.environ.pop("KP_SCOPE_TODAY", None)  # judged by the real "today", as in production
    Clock.now = date(2026, 12, 31)
    monkeypatch.setattr(service, "date", Clock)
    return Clock


def test_scope_h3b_round3_control_last_day_in_force_is_given_and_labelled(acme, clock):
    client, core, add = acme
    os.environ.pop("KP_SCOPE_TODAY", None)
    old = add("PARCELBOOK-OLD", "Returns desk to year end", "boxed")
    with writing(core):  # set-up is a job (REF S23, the door)
        core.state.register.update(old, effective_to="2026-12-31")
    core.state.answer.generator = Echo()
    body = ask(client)
    assert given(body, "PARCELBOOK-OLD")
    assert "(In force until 31 December 2026.)" in body["answer"]


def test_scope_h3b_round3_expired_at_midnight_while_prepared_is_still_given(acme, clock):
    """Restated (one reading, one day): an answer begun on 31 December is judged on 31 December, label included; the
    next answer, on 1 January, leaves the expired source out."""
    client, core, add = acme
    os.environ.pop("KP_SCOPE_TODAY", None)
    old = add("PARCELBOOK-OLD", "Returns desk to year end", "boxed")
    with writing(core):  # set-up is a job (REF S23, the door)
        core.state.register.update(old, effective_to="2026-12-31")

    def midnight(_call):
        clock.now = date(2027, 1, 1)
    core.state.answer.generator = Echo(midnight)
    body = ask(client)
    assert given(body, "PARCELBOOK-OLD") and "(In force until 31 December 2026.)" in body["answer"]
    core.state.answer.generator = Echo()
    assert not given(ask(client), "PARCELBOOK-OLD"), "an expired source's passage reached an answer begun on 1 January"


def test_scope_h3b_round3_replaced_at_midnight_while_prepared_is_still_given(acme, clock):
    """Restated: begun on 31 December, the answer has the old source and the new one labelled 'In force from'; the next,
    begun on 1 January, has only the new one, unlabelled."""
    client, core, add = acme
    os.environ.pop("KP_SCOPE_TODAY", None)
    old = add("PARCELBOOK-OLD", "Returns desk, current", "boxed")
    new = add("TOTELEDGER-NEW", "Returns desk, next year", "crated")
    with writing(core):  # set-up is a job (REF S23, the door)
        core.state.register.update(new, effective_from="2027-01-01", supersedes=[old])

    def midnight(_call):
        clock.now = date(2027, 1, 1)
    core.state.answer.generator = Echo(midnight)
    body = ask(client)
    assert given(body, "PARCELBOOK-OLD") and "In force from 1 January 2027" in body["answer"]
    core.state.answer.generator = Echo()
    body = ask(client)
    assert not given(body, "PARCELBOOK-OLD"), "a replaced source's passage reached an answer begun on 1 January"
    assert given(body, "TOTELEDGER-NEW") and "In force from 1 January 2027" not in body["answer"]


# ---- Restated: an edit while an answer is prepared applies from the next answer, on every route ----------------------

def test_scope_h3b_round3_control_edit_inside_generation_is_withheld(acme):
    """Restated for the door (REF S23, the Human's decision after round 7): the edit inside the
    generation is a job holding the workspace's lock, as the details request would; the ask passes the door and does
    not wait, so the edit still lands while the answer is prepared."""
    client, core, add = acme
    sid = add("PARCELBOOK-OLD", "Returns desk", "boxed")

    def expire(_call):
        as_job(core, core.state.register.update, sid, effective_to="2026-01-01")
    core.state.answer.generator = Echo(expire)
    assert given(ask(client), "PARCELBOOK-OLD")  # judged on the reading taken as it began
    core.state.answer.generator = Echo()
    assert not given(ask(client), "PARCELBOOK-OLD")


def test_scope_h3b_round3_avatar_edit_during_render_is_given(acme):
    """The avatar route: an edit during its rendering applies from the next answer (its missing delivery checks for
    access and evidence are REF S16b #2136). Restated for the door (REF S23, the Human's decision after round 7): the
    edit is a job holding the workspace's lock, as the details request would; the avatar route passes the door and
    does not wait, so the edit still lands during the render."""
    client, core, add = acme
    sid = add("PARCELBOOK-OLD", "Returns desk", "boxed")
    service, state = core.state.answer, {"answered": False}
    original = service.answer

    def answer(*args, **kwargs):
        result = original(*args, **kwargs)
        state["answered"] = True
        return result

    def expire(_call):
        if state["answered"]:  # the natural-style render's model call, after the answer service returned
            as_job(core, core.state.register.update, sid, effective_to="2026-01-01")
    service.answer = answer
    service.generator = Echo(expire)
    response = client.post("/api/avatar/answer", json={"q": QUESTION, "style": "natural"}, headers=HEAD)
    assert response.status_code == 200, response.text
    assert core.state.register.get(sid).effective_to == "2026-01-01", "the edit did not land during the render"
    service.answer, service.generator = original, Echo()
    assert not given(ask(client), "PARCELBOOK-OLD")


def test_scope_h3b_round3_ask_edit_after_scope_recheck_before_delivery_is_given(acme):
    """On /api/ask, an edit landing after the answer is prepared and before it is delivered applies from the next.
    Restated for the door (REF S23, the Human's decision after round 7): the edit is a job holding
    the workspace's lock, as the details request would; the ask passes the door and does not wait."""
    client, core, add = acme
    sid = add("PARCELBOOK-OLD", "Returns desk", "boxed")
    service, state = core.state.answer, {"answered": False}
    original_answer, original_version = service.answer, service.version_of

    def answer(*args, **kwargs):
        result = original_answer(*args, **kwargs)
        state["answered"] = True
        return result

    def version_of(source_id, *read):
        if state["answered"]:
            as_job(core, core.state.register.update, sid, effective_to="2026-01-01")
        return original_version(source_id)
    service.answer, service.version_of, service.generator = answer, version_of, Echo()
    assert given(ask(client), "PARCELBOOK-OLD")
    assert core.state.register.get(sid).effective_to == "2026-01-01"
    service.answer, service.version_of = original_answer, original_version
    assert not given(ask(client), "PARCELBOOK-OLD")


def test_scope_h3b_round3_superseding_source_withdrawn_while_prepared_is_given(acme):
    """The answer rests on NEW (it replaces OLD); NEW is withdrawn while it is prepared. This answer is judged on its
    reading; the next has OLD back in force and not NEW. (Withdrawal at delivery for every answer is REF S19b #2137.)
    Restated for the door (REF S23, the Human's decision after round 7): the withdrawal is a job
    holding the workspace's lock, as its request would; the ask passes the door and does not wait."""
    client, core, add = acme
    old = add("PARCELBOOK-OLD", "Returns desk, old", "boxed")
    new = add("TOTELEDGER-NEW", "Returns desk, new", "crated")
    with writing(core):  # set-up is a job (REF S23, the door)
        core.state.register.update(new, supersedes=[old])

    def withdraw(_call):
        as_job(core, core.state.register.update, new, approval_status="pending")
    core.state.answer.generator = Echo(withdraw)
    body = ask(client)
    assert "PARCELBOOK-OLD" not in body.get("answer", "") and given(body, "TOTELEDGER-NEW")
    core.state.answer.generator = Echo()
    body = ask(client)
    assert given(body, "PARCELBOOK-OLD") and "TOTELEDGER-NEW" not in body.get("answer", "")


# ---- The details editor and scope's reader ---------------------------------------------------------------------------

def patch(client, sid: str, fields: dict):
    return client.patch(f"/api/content/documents/{sid}/details", json={"fields": fields}, headers=HEAD)


@pytest.mark.parametrize("value", [0, False, []], ids=["zero", "false", "empty-list"])
def test_scope_h3b_round3_editor_accepts_a_value_scope_cannot_read(acme, value):
    """P3: scope cannot read 0, false or [] (read_date gives UNREADABLE: left out), but the editor accepts each (its
    ``fields[key] or None`` turns it into 'no date') and clears the end date, bringing an expired source back."""
    from assistant.answer.scope import UNREADABLE, read_date
    client, core, add = acme
    sid = add("PARCELBOOK-OLD", "Returns desk", "boxed")
    assert patch(client, sid, {"effective_to": "2026-01-01"}).status_code == 200
    core.state.answer.generator = Echo()
    assert not given(ask(client), "PARCELBOOK-OLD")  # control: expired, left out
    assert read_date(value) is UNREADABLE  # control: scope cannot read it
    response = patch(client, sid, {"effective_to": value})
    assert response.status_code >= 400, f"the editor accepted {value!r}, which scope cannot read, and stored " \
                                        f"{core.state.register.get(sid).effective_to!r}"


def test_scope_h3b_round3_editor_end_before_start_in_two_edits(acme):
    """P1/P2: the editor refuses an end before the start only when both come in one edit. Set apart, it accepts them;
    scope then leaves the source out (start > end) although it is neither expired, replaced nor unreadable, and a
    source approved for a later date should be kept and say from when."""
    client, core, add = acme
    sid = add("PARCELBOOK-OLD", "Returns desk", "boxed")
    assert patch(client, sid, {"effective_from": "2027-06-01", "effective_to": "2027-01-01"}).status_code >= 400
    assert patch(client, sid, {"effective_from": "2027-06-01"}).status_code == 200
    second = patch(client, sid, {"effective_to": "2027-01-01"})
    core.state.answer.generator = Echo()
    body = ask(client)
    assert second.status_code >= 400 or ("In force from 1 June 2027" in body.get("answer", "")
                                         and given(body, "PARCELBOOK-OLD")), \
        "the editor stored an end before the start and scope silently left the source out"


def test_scope_h3b_round3_editor_sites_as_one_string(acme):
    """P2: a site list sent as one string ("Leeds") is split into letters by the editor, so the passage says
    'Applies to: L, e, e, d, s.' rather than its site."""
    client, core, add = acme
    sid = add("PARCELBOOK-OLD", "Returns desk", "boxed")
    response = patch(client, sid, {"applies_to": "Leeds"})
    core.state.answer.generator = Echo()
    body = ask(client)
    assert response.status_code >= 400 or "(Applies to: Leeds.)" in body.get("answer", ""), \
        f"stored {core.state.register.get(sid).applies_to!r}; the passage does not say its site"


def test_scope_h3b_round3_editor_drops_the_eleventh_site_silently(acme):
    """P2 (oversized input): the editor accepts eleven sites and keeps the first ten without saying so, so the passage
    of a source that applies to Zurich never says Zurich."""
    client, core, add = acme
    sid = add("PARCELBOOK-OLD", "Returns desk", "boxed")
    sites = ["Aberdeen", "Bristol", "Cardiff", "Derby", "Exeter", "Fife", "Glasgow", "Hull", "Ipswich", "Leeds", "Zurich"]
    response = patch(client, sid, {"applies_to": sites})
    core.state.answer.generator = Echo()
    body = ask(client)
    assert response.status_code >= 400 or "Zurich" in body.get("answer", "").split("QUESTION:")[0].split("Leeds", 1)[-1], \
        f"accepted {len(sites)} sites, stored {core.state.register.get(sid).applies_to!r}"
