"""Heuristic guardrail classifier."""

from __future__ import annotations

import re

from pydantic import BaseModel

# Category -> (compiled patterns, decline message). Order is priority order:
# manipulation and self-harm are checked first.
_SCOPE = "I can only answer questions about the approved process knowledge."

_DEFS: list[tuple[str, list[str], str]] = [
    (
        "manipulation",
        [r"ignore (all |the |your |previous |prior |above )+(instruction|prompt|rule)",
         r"disregard (the|your|all|previous|above)", r"system prompt", r"developer mode",
         r"jailbreak", r"you are now", r"pretend (you|to be)", r"reveal (your|the).*(prompt|instruction)",
         r"override (your|the|system)"],
        f"I cannot change or ignore my instructions. {_SCOPE}",
    ),
    (
        "self_harm",
        [r"\b(suicide|suicidal|kill myself|killing myself|end my life|self[- ]?harm|harm myself|hurt myself)\b"],
        "I cannot help with this, but please consider reaching out to a qualified professional "
        "or a local support service. " + _SCOPE,
    ),
    ("sexual", [r"\b(sexual|erotic|pornograph|explicit sex|nude|nudes)\b"],
     f"I cannot engage with that. {_SCOPE}"),
    ("violence", [r"\b(how to (make|build).*(bomb|weapon)|kill (someone|people)|murder|terroris)\b"],
     f"I cannot help with that. {_SCOPE}"),
    ("abuse", [r"\b(i hate you|shut up|you('?re| are) (stupid|useless|an idiot))\b"],
     f"Let's keep this respectful. {_SCOPE}"),
    ("vulgar", [r"\bf+u+c+k|\bs+h+i+t\b|\bbitch\b|\basshole\b"],
     f"Let's keep the language clean. {_SCOPE}"),
    ("political_religious",
     [r"\b(politic|election|democrat|republican|religion|religious|which god)\b"],
     f"I do not discuss political or religious topics. {_SCOPE}"),
    ("medical_legal",
     [r"\b(medical advice|medical|diagnos|symptom|prescription|legal advice|lawsuit|\bsue\b|attorney|lawyer)\b"],
     f"That is outside my scope; I cannot give medical or legal advice. {_SCOPE}"),
    ("off_topic",
     [r"\b(weather|forecast|temperature|football|sport|recipe|cook|tell me a joke|horoscope|"
      r"bitcoin|stock price|who won)\b"],
     f"That is outside my scope as a process-knowledge assistant. {_SCOPE}"),
]

_COMPILED = [(name, [re.compile(p, re.IGNORECASE) for p in pats], msg) for name, pats, msg in _DEFS]

# Categories worth scanning on generated OUTPUT (harmful content the model might
# echo). Intent categories like off_topic/political are input-only.
_OUTPUT_CATEGORIES = {"self_harm", "sexual", "violence", "abuse", "vulgar"}


class GuardrailResult(BaseModel):
    allowed: bool
    category: str | None = None
    message: str | None = None


class GuardrailChecker:
    def __init__(self, disabled: set[str] | None = None) -> None:
        self.disabled = disabled or set()

    def check(self, text: str) -> GuardrailResult:
        for name, patterns, message in _COMPILED:
            if name in self.disabled:
                continue
            if any(p.search(text) for p in patterns):
                return GuardrailResult(allowed=False, category=name, message=message)
        return GuardrailResult(allowed=True)

    def check_output(self, text: str) -> GuardrailResult:
        """Scan generated output for harmful content (defense-in-depth)."""
        for name, patterns, message in _COMPILED:
            if name not in _OUTPUT_CATEGORIES or name in self.disabled:
                continue
            if any(p.search(text) for p in patterns):
                return GuardrailResult(allowed=False, category=name, message=message)
        return GuardrailResult(allowed=True)
