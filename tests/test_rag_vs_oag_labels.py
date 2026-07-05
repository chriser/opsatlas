"""RAG-vs-OAG evaluation label dataset tests."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DATASET = Path("tests/evaluation/rag_vs_oag_questions.json")

Category = Literal["structured_entity", "structured_relationship", "aggregate", "narrative", "out_of_scope", "mixed"]
ExpectedPath = Literal["oag", "rag", "either"]


class ExpectedFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    aliases: list[str] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def text_is_atomic(cls, value: str) -> str:
        assert value.strip(), "expected fact text must be non-empty"
        assert len(value.split()) <= 24, "expected facts should stay atomic enough for deterministic scoring"
        return value


class QuestionLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    category: Category
    question: str
    expected_path: ExpectedPath
    expected_answer_facts: list[ExpectedFact]
    notes: str

    @field_validator("expected_answer_facts")
    @classmethod
    def facts_are_present(cls, value: list[ExpectedFact]) -> list[ExpectedFact]:
        assert value, "each label needs at least one expected fact"
        return value


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version: str
    created_at: str
    source_corpus: str
    questions: list[QuestionLabel]


def test_rag_vs_oag_labels_are_valid_balanced_and_pre_registered() -> None:
    dataset = Dataset.model_validate(json.loads(DATASET.read_text(encoding="utf-8")))
    ids = [item.id for item in dataset.questions]
    counts = Counter(item.category for item in dataset.questions)

    assert dataset.dataset_version == "rag-vs-oag-v1"
    assert len(dataset.questions) == 45
    assert len(ids) == len(set(ids))
    assert counts == {
        "aggregate": 5,
        "mixed": 5,
        "narrative": 10,
        "out_of_scope": 5,
        "structured_entity": 10,
        "structured_relationship": 10,
    }
    assert all(
        item.expected_path == "oag"
        for item in dataset.questions
        if item.category in {"structured_entity", "structured_relationship", "aggregate"}
    )
    assert all(item.expected_path == "rag" for item in dataset.questions if item.category == "narrative")
    assert all(item.expected_path == "either" for item in dataset.questions if item.category in {"out_of_scope", "mixed"})
    assert all(alias.strip() for item in dataset.questions for fact in item.expected_answer_facts for alias in fact.aliases)
