"""Audit-trace tests (hermetic)."""

from fastapi.testclient import TestClient

from assistant.answer.service import AnswerService
from assistant.answer.validation import GroundednessValidator
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.ingestion.store import SectionStore
from assistant.observability.trace import AuditTrace
from assistant.retrieval.service import RetrievalService
from assistant.sources.register import SourceRegister

PASSWORD = "test-pass"
DOC = "# Controls\n\nDue diligence and credit checks are mandatory gates."


class Gen:
    def generate(self, prompt):
        return "Credit checks are mandatory [1]."


class VerdictGen:
    def generate(self, prompt):
        return "SUPPORTED"


def test_audit_trace_recent_order(tmp_path):
    trace = AuditTrace(tmp_path)
    trace.append({"question": "a"})
    trace.append({"question": "b"})
    assert [r["question"] for r in trace.recent()] == ["b", "a"]  # newest first


def test_ask_writes_an_audit_trace(tmp_path):
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    retrieval = RetrievalService(reg, store)
    answer = AnswerService(
        retrieval,
        Gen(),
        audit_trace=AuditTrace(reg.base_dir),
        model_info={"llm": "test", "embed": "test"},
        validator=GroundednessValidator(VerdictGen()),
    )
    client = TestClient(create_app(reg, AuthService(PASSWORD), retrieval=retrieval, answer=answer))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    rec = client.post(
        "/api/sources/upload",
        files={"file": ("c.md", DOC.encode(), "text/markdown")},
        data={"title": "Controls"},
    ).json()
    client.post(f"/api/sources/{rec['id']}/ingest")
    client.post(f"/api/governance/sources/{rec['id']}/approve")
    client.post("/api/ask", json={"q": "are credit checks mandatory?"})

    traces = client.get("/api/observability/traces").json()
    assert len(traces) == 1
    t = traces[0]
    assert t["mode"] == "full-context"
    assert t["model"] == {"llm": "test", "embed": "test"}
    assert t["prompt_version"] == "v2"
    assert t["grounding"] == "supported"
    assert t["grounding_score"] == 1.0
    assert t["faithfulness"] == "faithful"
    assert "latency_ms" in t
    assert t["evidence"] and t["evidence"][0]["heading"] == "Controls"
