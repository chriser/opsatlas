"""Groundedness validation — does the answer follow from the cited evidence?

An LLM-as-judge check applied after generation. Used to downgrade a cited-but-
unsupported answer from "grounded" to "unverified" (a hallucination signal).
Falls back to "n/a" on any failure.
"""

from __future__ import annotations

from .generator import Generator

_PROMPT = (
    "Is the ANSWER fully supported by the EVIDENCE below? Judge only on support, not "
    "style. Reply with ONE word: SUPPORTED, PARTIAL, or UNSUPPORTED.\n\n"
    "EVIDENCE:\n{evidence}\n\nANSWER: {answer}"
)
_MAX_CHARS = 600


class GroundednessValidator:
    def __init__(self, generator: Generator) -> None:
        self.generator = generator

    def validate(self, answer: str, evidence_texts: list[str]) -> str:
        if not evidence_texts:
            return "n/a"
        evidence = "\n".join(f"- {t[:_MAX_CHARS]}" for t in evidence_texts)
        try:
            out = self.generator.generate(_PROMPT.format(evidence=evidence, answer=answer)).strip().upper()
        except Exception:
            return "n/a"
        if "UNSUPPORTED" in out:  # checked first ("UNSUPPORTED" contains "SUPPORTED")
            return "unsupported"
        if "PARTIAL" in out:
            return "partial"
        if "SUPPORTED" in out:
            return "supported"
        return "n/a"
