"""ARCH H1b: a facts-map *listing* stands only when the judge finds its facts answer the question; a precise facts-map
answer stands as it is; when the facts map refuses, the documents are searched. Verdicts are faked here; the benchmark
measures the real judge."""
from fastapi.testclient import TestClient
from test_answer import PASSWORD, STRUCTURED_DOC, FakeGenerator

from assistant.answer.prompt import REFUSAL
from assistant.answer.service import AnswerService
from assistant.answer.validation import GroundednessValidator
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.ingestion.store import SectionStore
from assistant.observability.trace import AuditTrace
from assistant.retrieval.service import RetrievalService
from assistant.sources.register import SourceRegister


class Judge:
    """A validator whose answerability verdict is scripted: True, False or None (could not say)."""

    def __init__(self, verdict):
        self.verdict, self.asked = verdict, []

    def answers(self, question, evidence_texts):
        self.asked.append((question, len(evidence_texts)))
        return self.verdict

    def validate(self, answer, evidence_texts):  # the document path's grounding check: always supported here
        return "supported"


class RefusesOnFacts(FakeGenerator):
    """Refuses when prompted with the facts map's evidence, answers from documents."""

    def generate(self, prompt):
        self.last_prompt = prompt
        documents = "This raw document paragraph" in prompt
        return "From the documents [1], the finance approver approves readiness." if documents else REFUSAL


def make(tmp_path, generator=None, validator=None):
    register = SourceRegister(tmp_path)
    store = SectionStore(register.base_dir)
    retrieval = RetrievalService(register, store)
    gen = generator or FakeGenerator(reply="Finance approver owns Supplier Setup [2].")
    trace = AuditTrace(tmp_path)
    answer = AnswerService(retrieval, gen, validator=validator, audit_trace=trace)
    client = TestClient(create_app(register, AuthService(PASSWORD), retrieval=retrieval, answer=answer))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    record = client.post("/api/sources/upload", files={"file": ("supplier-structured.md", STRUCTURED_DOC.encode(), "text/markdown")},
                         data={"title": "Supplier Setup"}).json()
    client.post(f"/api/sources/{record['id']}/ingest")
    client.post(f"/api/governance/sources/{record['id']}/approve", json={"sha": record["content_sha256"]})
    return client, gen, trace


class Plan:
    def __init__(self, intent, evidence=({"text": "Ontology fact: the finance approver approves readiness"},)):
        self.intent, self.evidence, self.answer = intent, list(evidence), None


def test_a_precise_facts_map_answer_stands_without_asking_the_judge(tmp_path):
    judge = Judge(False)
    client, _, trace = make(tmp_path, validator=judge)
    body = client.post("/api/ask", json={"q": "Who owns Supplier Setup?"}).json()  # an owner_fact plan: precise
    assert body["mode"] == "oag" and body["answer_path"] == "oag"
    assert judge.asked == [] and trace.recent(1)[0]["fallbacks"] == []


def test_only_an_aggregate_listing_is_put_to_the_judge_and_a_no_sends_it_to_the_documents(tmp_path):
    client, _, _ = make(tmp_path, validator=Judge(False))
    service = client.app.state.answer
    for intent in ("owner_fact", "process_controls", "process_systems", "process_roles", "system_processes"):
        assert service._facts_answer("q", Plan(intent)) is True
    assert service._facts_answer("q", Plan("aggregate_facts")) is False
    assert service._facts_answer("q", None) is True
    client.app.state.answer.validator = Judge(True)
    assert service._facts_answer("q", Plan("aggregate_facts")) is True


def test_a_facts_map_refusal_falls_back_to_the_documents(tmp_path):
    client, gen, trace = make(tmp_path, generator=RefusesOnFacts(), validator=Judge(True))
    body = client.post("/api/ask", json={"q": "Who owns Supplier Setup?"}).json()
    assert body["refused"] is False and body["answer_path"] in {"rag", "rag+ontology"}
    assert "finance approver approves readiness" in body["answer"]
    assert trace.recent(1)[0]["fallbacks"][0]["cause"] == "the facts map could not answer"


def test_a_judge_that_cannot_say_keeps_the_listing_and_says_so(tmp_path):
    client, _, trace = make(tmp_path, validator=Judge(None))
    service = client.app.state.answer
    from assistant.observability import fallbacks
    fallbacks.begin()
    assert service._facts_answer("q", Plan("aggregate_facts")) is True
    assert fallbacks.collect() == [{"step": "answerability judge", "cause": "no verdict", "kept": "the facts-map answer"}]
    assert trace.recent(1) == []


def test_without_a_judge_the_facts_map_answers_as_before(tmp_path):
    client, _, trace = make(tmp_path, validator=None)
    assert client.post("/api/ask", json={"q": "Who owns Supplier Setup?"}).json()["mode"] == "oag"
    assert trace.recent(1)[0]["fallbacks"] == []


def test_oag_only_keeps_the_facts_map_answer_whatever_the_judge_says(tmp_path):
    client, _, _ = make(tmp_path, validator=Judge(False))
    service = client.app.state.answer
    original = service._facts_answer
    service._facts_answer = lambda question, plan: False  # as if every plan were a listing the judge rejects
    try:
        result = service.answer("Who owns Supplier Setup?", routing_mode="oag_only")
    finally:
        service._facts_answer = original
    assert result.answer_path == "oag" and result.mode == "oag"


def test_the_real_judge_reads_yes_and_no_and_nothing_else():
    class Says:
        def __init__(self, reply):
            self.reply = reply

        def generate(self, prompt):
            if isinstance(self.reply, Exception):
                raise self.reply
            return self.reply
    assert GroundednessValidator(Says("YES")).answers("q", ["fact"]) is True
    assert GroundednessValidator(Says("Yes.")).answers("q", ["fact"]) is True
    assert GroundednessValidator(Says("NO")).answers("q", ["fact"]) is False
    assert GroundednessValidator(Says("No, the facts do not state it.")).answers("q", ["fact"]) is False
    assert GroundednessValidator(Says("Maybe")).answers("q", ["fact"]) is None
    assert GroundednessValidator(Says(RuntimeError("down"))).answers("q", ["fact"]) is None
    assert GroundednessValidator(Says("YES")).answers("q", []) is None
