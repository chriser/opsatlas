"""Analytics tests — scorecard math and usage logging (hermetic)."""

from fastapi.testclient import TestClient

from assistant.analytics.classify import classify_topic
from assistant.analytics.log import UsageEntry, UsageLog, build_scorecard
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


def test_build_scorecard_counts_and_gaps():
    entries = [
        UsageEntry(timestamp="t", question="a", mode="full-context", refused=False, confidence="grounded", citation_count=1),
        UsageEntry(timestamp="t", question="VAT number?", mode="empty", refused=True),
        UsageEntry(timestamp="t", question="weather?", mode="guardrail", refused=True, category="off_topic"),
    ]
    sc = build_scorecard(entries)
    assert sc["total_queries"] == 3
    assert sc["answered"] == 1 and sc["refused"] == 2 and sc["guardrail_blocks"] == 1
    assert "VAT number?" in sc["knowledge_gaps"]
    assert "weather?" not in sc["knowledge_gaps"]  # guardrail block is not a knowledge gap


def test_classify_topic():
    assert classify_topic("Are credit checks mandatory?") == "checks"
    assert classify_topic("Why is supplier ID mapping required?") == "finance_mapping"
    assert classify_topic("Who starts the process?") == "roles"
    assert classify_topic("Tell me about pandas") == "general"


def test_scorecard_includes_topic_breakdown():
    entries = [
        UsageEntry(timestamp="t", question="Are credit checks mandatory?", mode="full-context", refused=False),
        UsageEntry(timestamp="t", question="Why is finance mapping needed?", mode="full-context", refused=False),
        UsageEntry(timestamp="t", question="Is a credit check required?", mode="full-context", refused=False),
    ]
    by_topic = build_scorecard(entries)["by_topic"]
    assert by_topic["checks"] == 2
    assert by_topic["finance_mapping"] == 1


def make_client(tmp_path) -> TestClient:
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    retrieval = RetrievalService(reg, store)
    answer = AnswerService(retrieval, FakeGenerator(), usage_log=UsageLog(reg.base_dir))
    client = TestClient(create_app(reg, AuthService(PASSWORD), retrieval=retrieval, answer=answer))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_scorecard_endpoint_logs_asks(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/ask", json={"q": "What is the VAT number?"})  # empty KB -> refused gap

    rec = client.post(
        "/api/sources/upload",
        files={"file": ("c.md", b"# Controls\n\nCredit checks are mandatory.", "text/markdown")},
        data={"title": "Controls"},
    ).json()
    client.post(f"/api/sources/{rec['id']}/ingest")
    client.post(f"/api/governance/sources/{rec['id']}/approve")
    client.post("/api/ask", json={"q": "are credit checks mandatory?"})  # answered

    sc = client.get("/api/analytics/scorecard").json()
    assert sc["total_queries"] == 2
    assert sc["refused"] == 1 and sc["answered"] == 1
    assert "What is the VAT number?" in sc["knowledge_gaps"]
