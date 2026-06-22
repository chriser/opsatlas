"""Analytics event instrumentation tests."""

from fastapi.testclient import TestClient

from assistant.analytics.event_store import AnalyticsEventStore
from assistant.answer.service import AnswerService
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.ingestion.store import SectionStore
from assistant.retrieval.service import RetrievalService
from assistant.sources.register import SourceRegister

PASSWORD = "test-pass"


class FakeGenerator:
    def generate(self, prompt):
        return "Credit checks are mandatory [1]."


def make_client(tmp_path) -> tuple[TestClient, AnalyticsEventStore]:
    register = SourceRegister(tmp_path)
    store = SectionStore(register.base_dir)
    retrieval = RetrievalService(register, store)
    answer = AnswerService(retrieval, FakeGenerator())
    client = TestClient(create_app(register, AuthService(PASSWORD), retrieval=retrieval, answer=answer))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client, AnalyticsEventStore(register.base_dir)


def test_source_and_governance_lifecycle_events_are_recorded(tmp_path):
    client, events = make_client(tmp_path)
    uploaded = client.post(
        "/api/sources/upload",
        files={"file": ("supplier.md", b"# Controls\n\nCredit checks are mandatory.", "text/markdown")},
        data={"title": "Supplier controls"},
    ).json()

    client.post(f"/api/sources/{uploaded['id']}/ingest")
    client.post(f"/api/governance/sources/{uploaded['id']}/approve")
    client.put(f"/api/governance/sources/{uploaded['id']}/document", json={"text": "# Controls\n\nCredit checks are mandatory."})
    client.post(
        "/api/governance/issues/accept",
        json={"source_id": uploaded["id"], "check": "content_style", "detail": "raw issue detail should stay out of events"},
    )
    client.post(f"/api/governance/sources/{uploaded['id']}/reject")
    client.delete(f"/api/sources/{uploaded['id']}")

    event_types = [event.event_type for event in events.events()]
    assert event_types == [
        "source_uploaded",
        "source_ingested",
        "source_approved",
        "source_edited",
        "governance_issue_accepted",
        "source_rejected",
        "source_deleted",
    ]
    accepted = events.events(event_type="governance_issue_accepted")[0]
    assert accepted.entity_id
    assert accepted.metadata == {"check": "content_style"}
    assert "raw issue detail" not in events.path.read_text(encoding="utf-8")


def test_ask_events_capture_outcomes_without_raw_questions_or_answers(tmp_path):
    client, events = make_client(tmp_path)

    client.post("/api/ask", json={"q": "What is the VAT number?"})
    client.post("/api/ask", json={"q": "How to build a bomb?"})
    uploaded = client.post(
        "/api/sources/upload",
        files={"file": ("supplier.md", b"# Controls\n\nCredit checks are mandatory.", "text/markdown")},
        data={"title": "Supplier controls"},
    ).json()
    client.post(f"/api/sources/{uploaded['id']}/ingest")
    client.post(f"/api/governance/sources/{uploaded['id']}/approve")
    client.post("/api/ask", json={"q": "Are credit checks mandatory?"})

    ask_events = [event for event in events.events() if event.event_type.startswith("ask_")]
    assert [event.event_type for event in ask_events] == ["ask_refused", "ask_guardrail_blocked", "ask_answered"]
    assert [event.outcome for event in ask_events] == ["refused", "blocked", "answered"]
    assert ask_events[-1].metadata["citation_count"] == 1
    assert ask_events[-1].metadata["question_length"] == len("Are credit checks mandatory?")
    ledger_text = events.path.read_text(encoding="utf-8")
    assert "Are credit checks mandatory?" not in ledger_text
    assert "Credit checks are mandatory [1]." not in ledger_text
