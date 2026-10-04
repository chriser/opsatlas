"""A space's referral (ARCH H2b): an answer to a question on a topic the space hands to people ends with the space's
sentence, once, after the answer is generated; refusals and other topics are untouched, and so is every space without
a referral."""
import json

import pytest
from fastapi.testclient import TestClient

from assistant.answer.service import AnswerService
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.ingestion.store import SectionStore
from assistant.retrieval.service import RetrievalService
from assistant.sources.register import SourceRegister
from assistant.space_config import DEFAULT_COMPILED, SpaceConfig
from services.opsatlas_sales.spaces import PRODUCT_GUIDE_CONFIG

PASSWORD = "test-pass"
SENTENCE = "For further information and possible enhancements, please contact the sales team."
REFERRAL = SpaceConfig(referral={"topics": ["integrate", "integration", "price"], "sentence": SENTENCE})
DOC = """# Integrations

The proof of concept does not integrate directly with live organisational systems.

# Citations

Every answer cites the approved sources it used.
"""


class Echo:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.reply


def client_with(tmp_path, reply: str, config: SpaceConfig | None, *, seeded: bool = True) -> tuple[TestClient, Echo]:
    register = SourceRegister(tmp_path)
    retrieval = RetrievalService(register, SectionStore(register.base_dir))
    generator = Echo(reply)
    answer = AnswerService(retrieval, generator, space_config=config)
    client = TestClient(create_app(register, AuthService(PASSWORD), retrieval=retrieval, answer=answer))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    if seeded:
        record = client.post("/api/sources/upload", files={"file": ("guide.md", DOC.encode(), "text/markdown")},
                             data={"title": "Guide"}).json()
        client.post(f"/api/sources/{record['id']}/ingest")
        client.post(f"/api/governance/sources/{record['id']}/approve", json={"sha": record["content_sha256"]})
    return client, generator


def test_an_answer_on_a_referred_topic_ends_with_the_sentence_and_the_prompt_never_sees_it(tmp_path):
    client, generator = client_with(tmp_path, "No, it does not integrate directly with live systems [1].", REFERRAL)
    body = client.post("/api/ask", json={"q": "Does OpsAtlas integrate directly with SAP?"}).json()
    assert body["refused"] is False
    assert body["answer"] == f"No, it does not integrate directly with live systems [1].\n\n{SENTENCE}"
    assert SENTENCE not in generator.prompts[-1]
    other = client.post("/api/ask", json={"q": "How does OpsAtlas cite its sources?"}).json()
    assert SENTENCE not in other["answer"]  # not a referred topic


def test_the_sentence_is_never_added_twice(tmp_path):
    client, _ = client_with(tmp_path, f"It does not integrate directly [1]. {SENTENCE}", REFERRAL)
    body = client.post("/api/ask", json={"q": "Which integrations are there?"}).json()
    assert body["answer"].count(SENTENCE) == 1


def test_a_refusal_keeps_the_spaces_own_wording(tmp_path):
    config = SpaceConfig(refusal="Not in the guide; please contact the sales team.", referral=REFERRAL.referral)
    client, _ = client_with(tmp_path, "unused", config, seeded=False)
    body = client.post("/api/ask", json={"q": "What is the price per user?"}).json()
    assert body["refused"] is True and body["answer"] == "Not in the guide; please contact the sales team."


def test_a_space_without_a_referral_is_untouched(tmp_path):
    client, _ = client_with(tmp_path, "No, it does not integrate directly with live systems [1].", None)
    body = client.post("/api/ask", json={"q": "Does OpsAtlas integrate directly with SAP?"}).json()
    assert body["answer"] == "No, it does not integrate directly with live systems [1]."
    assert DEFAULT_COMPILED.referral_sentence == "" and not DEFAULT_COMPILED.referral_re.search("integrate price")


def test_a_referral_needs_its_sentence_and_valid_topics():
    with pytest.raises(ValueError):
        SpaceConfig(referral={"topics": ["price"], "sentence": "  "})
    with pytest.raises(ValueError):
        SpaceConfig(referral={"topics": ["pric(e"], "sentence": SENTENCE})
    assert SpaceConfig(referral={"sentence": "Unused without topics."}).compiled().referral_re.search("price") is None


def test_the_product_guide_refers_exactly_the_approved_out_of_scope_questions():
    """The approved Sales set (sales-product-v1): its six out-of-scope questions are referred topics, and none of the 30
    questions the guide answers is."""
    compiled = SpaceConfig.model_validate(PRODUCT_GUIDE_CONFIG).compiled()
    questions = json.load(open("evaluation/sets/sales_product_questions.json"))["questions"]
    referred = {q["id"] for q in questions if compiled.referral_re.search(q["question"])}
    assert referred == {q["id"] for q in questions if q["category"] == "out_of_scope"} and len(referred) == 6
    assert "contact the sales team" in compiled.referral_sentence


NOTE = "The compliance-reasoning service belonged to the proof of concept and is not part of this edition."
NOTED = SpaceConfig(notes=[{"topics": ["compliance[- ]reasoning", "deep audit"], "sentence": NOTE}],
                    referral={"topics": ["integrate"], "sentence": SENTENCE})


def test_a_note_ends_an_answer_on_its_topic_before_the_referral_and_never_twice(tmp_path):
    """ARCH H4c: a space states what it knows about a topic, whatever the model's wording."""
    client, generator = client_with(tmp_path, "It uses Qwen 2.5 14B Instruct for Deep Audit [1].", NOTED)
    body = client.post("/api/ask", json={"q": "Which model does the compliance-reasoning service use for Deep Audit?"}).json()
    assert body["answer"] == f"It uses Qwen 2.5 14B Instruct for Deep Audit [1].\n\n{NOTE}"
    assert NOTE not in generator.prompts[-1]
    both = client.post("/api/ask", json={"q": "Did the compliance reasoning service integrate with SAP?"}).json()
    assert both["answer"].endswith(f"\n\n{NOTE}\n\n{SENTENCE}")
    other = client.post("/api/ask", json={"q": "How does OpsAtlas cite its sources?"}).json()
    assert NOTE not in other["answer"] and SENTENCE not in other["answer"]


def test_a_note_the_answer_already_says_is_not_added(tmp_path):
    client, _ = client_with(tmp_path, f"It used Qwen 2.5 14B Instruct [1]. {NOTE}", NOTED)
    body = client.post("/api/ask", json={"q": "Which model did the Deep Audit use?"}).json()
    assert body["answer"].count(NOTE) == 1


def test_notes_need_their_sentence_and_default_to_none():
    with pytest.raises(ValueError):
        SpaceConfig(notes=[{"topics": ["deep audit"], "sentence": ""}])
    assert DEFAULT_COMPILED.notes == ()


def test_the_product_guide_notes_the_retired_service_on_exactly_its_three_questions():
    """The set sales-product-v2: the guide's note on the compliance-reasoning service matches its three questions and
    no other."""
    compiled = SpaceConfig.model_validate(PRODUCT_GUIDE_CONFIG).compiled()
    questions = json.load(open("evaluation/sets/sales_product_questions.json"))["questions"]
    (pattern, sentence), = compiled.notes
    noted = {q["id"] for q in questions if pattern.search(q["question"])}
    assert noted == {"sales-entity-002", "sales-entity-holdout-002", "sales-relationship-002"}
    assert "proof of concept" in sentence and "not part of this edition" in sentence
