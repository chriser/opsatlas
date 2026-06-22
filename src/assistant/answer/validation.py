"""Groundedness validation — does the answer follow from the cited evidence?

An LLM-as-judge check applied after generation. Used to downgrade a cited-but-
unsupported answer from "grounded" to "unverified" (a hallucination signal).
Falls back to "n/a" on any failure.
"""

from __future__ import annotations

from pydantic import BaseModel

from .generator import Generator

_PROMPT = (
    "Is the ANSWER fully supported by the EVIDENCE below? Judge only on support, not "
    "style. Reply with ONE word: SUPPORTED, PARTIAL, or UNSUPPORTED.\n\n"
    "EVIDENCE:\n{evidence}\n\nANSWER: {answer}"
)
_MAX_CHARS = 600


class GroundingAssessment(BaseModel):
    label: str
    score: float
    faithfulness: str
    reason: str


_RUBRIC = {
    "supported": GroundingAssessment(
        label="supported",
        score=1.0,
        faithfulness="faithful",
        reason="The answer is fully supported by the cited evidence.",
    ),
    "partial": GroundingAssessment(
        label="partial",
        score=0.5,
        faithfulness="partially_faithful",
        reason="The answer is only partially supported by the cited evidence.",
    ),
    "unsupported": GroundingAssessment(
        label="unsupported",
        score=0.0,
        faithfulness="unfaithful",
        reason="The answer is not supported by the cited evidence.",
    ),
    "n/a": GroundingAssessment(
        label="n/a",
        score=0.0,
        faithfulness="n/a",
        reason="No cited evidence was available for groundedness scoring.",
    ),
}


class GroundednessValidator:
    def __init__(self, generator: Generator) -> None:
        self.generator = generator

    def validate(self, answer: str, evidence_texts: list[str]) -> str:
        return self.assess(answer, evidence_texts).label

    def assess(self, answer: str, evidence_texts: list[str]) -> GroundingAssessment:
        if not evidence_texts:
            return _RUBRIC["n/a"]
        evidence = "\n".join(f"- {t[:_MAX_CHARS]}" for t in evidence_texts)
        try:
            out = self.generator.generate(_PROMPT.format(evidence=evidence, answer=answer)).strip().upper()
        except Exception:
            return _RUBRIC["n/a"].model_copy(update={"reason": "Groundedness judge failed, so no score was assigned."})
        if "UNSUPPORTED" in out:  # checked first ("UNSUPPORTED" contains "SUPPORTED")
            return _RUBRIC["unsupported"]
        if "PARTIAL" in out:
            return _RUBRIC["partial"]
        if "SUPPORTED" in out:
            return _RUBRIC["supported"]
        return _RUBRIC["n/a"].model_copy(update={"reason": "Groundedness judge returned an unrecognised verdict."})
