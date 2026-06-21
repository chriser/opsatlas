"""Grounded answer orchestration."""

from __future__ import annotations

import re

from pydantic import BaseModel

from ..retrieval.service import RetrievalService
from .generator import Generator
from .prompt import REFUSAL, build_prompt


def _cited_indices(text: str, n: int) -> list[int]:
    """1-based evidence indices the model referenced via [n] markers, in order."""
    out: list[int] = []
    for match in re.findall(r"\[(\d+)\]", text):
        i = int(match)
        if 1 <= i <= n and i not in out:
            out.append(i)
    return out


def _finalize(text: str) -> tuple[str, bool]:
    """Return (answer, refused). Strips a spuriously appended refusal sentence
    when the model also produced a real answer."""
    text = text.strip()
    if not text or text.lower() == REFUSAL.lower():
        return REFUSAL, True
    if REFUSAL.lower() in text.lower():
        without = re.sub(re.escape(REFUSAL), "", text, flags=re.IGNORECASE).strip()
        if without:
            return without, False
        return REFUSAL, True
    return text, False

# When the whole knowledge base is below this size, pass it in full instead of
# retrieving chunks (the benchmark's small-KB strategy — see docs/benchmark).
FULL_CONTEXT_CHAR_LIMIT = 24000


class Citation(BaseModel):
    source_id: str
    source_title: str
    heading: str
    ordinal: int


class AnswerResult(BaseModel):
    answer: str
    citations: list[Citation]
    mode: str
    refused: bool


class AnswerService:
    def __init__(
        self,
        retrieval: RetrievalService,
        generator: Generator,
        full_context_char_limit: int = FULL_CONTEXT_CHAR_LIMIT,
    ) -> None:
        self.retrieval = retrieval
        self.generator = generator
        self.full_context_char_limit = full_context_char_limit

    def _all_sections(self) -> list[tuple]:
        items = []
        for record in self.retrieval.register.list():
            for section in self.retrieval.section_store.list_for_source(record.id):
                items.append((record, section))
        return items

    @staticmethod
    def _evidence(record, section) -> dict:
        return {
            "source_id": record.id,
            "source_title": record.title,
            "heading": section.heading,
            "ordinal": section.ordinal,
            "text": section.text,
        }

    def answer(self, question: str, top_k: int = 5) -> AnswerResult:
        if not question.strip():
            return AnswerResult(answer=REFUSAL, citations=[], mode="empty", refused=True)

        items = self._all_sections()
        if not items:
            return AnswerResult(answer=REFUSAL, citations=[], mode="empty", refused=True)

        total_chars = sum(len(section.text) for _, section in items)
        if total_chars <= self.full_context_char_limit:
            evidence = [self._evidence(record, section) for record, section in items]
            mode = "full-context"
        else:
            results, _ = self.retrieval.search(question, top_k)
            if not results:
                return AnswerResult(answer=REFUSAL, citations=[], mode="retrieval", refused=True)
            evidence = [
                {
                    "source_id": r.source_id,
                    "source_title": r.source_title,
                    "heading": r.heading,
                    "ordinal": r.ordinal,
                    "text": r.text,
                }
                for r in results
            ]
            mode = "retrieval"

        answer_text, refused = _finalize(self.generator.generate(build_prompt(question, evidence)))
        # Cite only what the model explicitly referenced via [n] markers. Answers
        # that use no evidence (a decline or an off-topic reply) carry no citations.
        chosen = [] if refused else [evidence[i - 1] for i in _cited_indices(answer_text, len(evidence))]
        citations = [
            Citation(**{k: e[k] for k in ("source_id", "source_title", "heading", "ordinal")}) for e in chosen
        ]
        return AnswerResult(answer=answer_text, citations=citations, mode=mode, refused=refused)
