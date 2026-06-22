"""Groundedness validation tests (hermetic)."""

from fastapi.testclient import TestClient

from assistant.answer.service import AnswerService
from assistant.answer.validation import GroundednessValidator
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.ingestion.store import SectionStore
from assistant.retrieval.service import RetrievalService
from assistant.sources.register import SourceRegister

PASSWORD = "test-pass"
DOC = "# Controls\n\nDue diligence and credit checks are mandatory gates."


class Gen:
    def generate(self, prompt):
        return "Credit checks are mandatory [1]."


def verdict_gen(word):
    class G:
        def generate(self, prompt):
            return word
    return G()


def test_validator_parses_verdicts():
    assert GroundednessValidator(verdict_gen("SUPPORTED")).validate("a", ["e"]) == "supported"
    assert GroundednessValidator(verdict_gen("This is UNSUPPORTED")).validate("a", ["e"]) == "unsupported"
    assert GroundednessValidator(verdict_gen("PARTIAL")).validate("a", ["e"]) == "partial"
    assert GroundednessValidator(verdict_gen("SUPPORTED")).validate("a", []) == "n/a"  # no evidence
    assessment = GroundednessValidator(verdict_gen("SUPPORTED")).assess("a", ["e"])
    assert assessment.score == 1.0 and assessment.faithfulness == "faithful"


def make_client(tmp_path, validator) -> TestClient:
    reg = SourceRegister(tmp_path)
    store = SectionStore(reg.base_dir)
    retrieval = RetrievalService(reg, store)
    answer = AnswerService(retrieval, Gen(), validator=validator)
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
    return client


def test_supported_answer_stays_grounded(tmp_path):
    body = make_client(tmp_path, GroundednessValidator(verdict_gen("SUPPORTED"))).post(
        "/api/ask", json={"q": "are credit checks mandatory?"}
    ).json()
    assert body["grounding"] == "supported"
    assert body["grounding_score"] == 1.0
    assert body["faithfulness"] == "faithful"
    assert body["confidence"] == "grounded"
    assert body["citations"]


def test_unsupported_answer_is_downgraded(tmp_path):
    body = make_client(tmp_path, GroundednessValidator(verdict_gen("UNSUPPORTED"))).post(
        "/api/ask", json={"q": "are credit checks mandatory?"}
    ).json()
    assert body["grounding"] == "unsupported"
    assert body["grounding_score"] == 0.0
    assert body["faithfulness"] == "unfaithful"
    assert body["confidence"] == "unverified"  # cited but not supported -> downgraded
