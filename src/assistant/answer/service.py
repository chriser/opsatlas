"""Grounded answer orchestration."""

from __future__ import annotations

import re
import time

from pydantic import BaseModel

from ..analytics.log import UsageEntry, UsageLog, now_iso
from ..guardrails.checker import GuardrailChecker
from ..observability.trace import AuditTrace
from ..retrieval.service import RetrievalService
from .generator import Generator
from .prompt import PROMPT_VERSION, REFUSAL, build_prompt


def _normalize_markers(text: str) -> str:
    """Tidy citation markers to the canonical [n] form. Models sometimes emit
    '[3, n4]' (a section plus a record id) or '[1, 2]' (a list); rewrite the first
    to '[3]' and the second to '[1][2]', dropping any non-numeric tokens. Brackets
    with no integer (not citations) are left untouched."""
    def repl(match: "re.Match[str]") -> str:
        nums = [t.strip() for t in match.group(1).split(",") if t.strip().isdigit()]
        return "".join(f"[{n}]" for n in dict.fromkeys(nums)) if nums else match.group(0)

    return re.sub(r"\[([^\]]+)\]", repl, text)


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
    category: str | None = None
    confidence: str = "none"  # grounded | unverified | none
    grounding: str = "n/a"  # supported | partial | unsupported | n/a


class AnswerService:
    def __init__(
        self,
        retrieval: RetrievalService,
        generator: Generator,
        full_context_char_limit: int = FULL_CONTEXT_CHAR_LIMIT,
        guardrails: GuardrailChecker | None = None,
        usage_log: UsageLog | None = None,
        validator=None,
        audit_trace: AuditTrace | None = None,
        model_info: dict | None = None,
    ) -> None:
        self.retrieval = retrieval
        self.generator = generator
        self.full_context_char_limit = full_context_char_limit
        self.guardrails = guardrails or GuardrailChecker()
        self.usage_log = usage_log
        self.validator = validator
        self.audit_trace = audit_trace
        self.model_info = model_info

    def _record(self, question: str, t0: float, result: "AnswerResult") -> "AnswerResult":
        if self.usage_log is not None:
            self.usage_log.append(UsageEntry(
                timestamp=now_iso(), question=question, mode=result.mode, refused=result.refused,
                category=result.category, confidence=result.confidence, citation_count=len(result.citations),
            ))
        if self.audit_trace is not None:
            self.audit_trace.append({
                "timestamp": now_iso(), "question": question, "mode": result.mode,
                "refused": result.refused, "category": result.category,
                "confidence": result.confidence, "grounding": result.grounding,
                "latency_ms": int((time.time() - t0) * 1000),
                "model": self.model_info or {}, "prompt_version": PROMPT_VERSION,
                "evidence": [
                    {"source_title": c.source_title, "heading": c.heading, "ordinal": c.ordinal}
                    for c in result.citations
                ],
            })
        return result

    def _all_sections(self) -> list[tuple]:
        # Only approved sources are queryable (human-in-the-loop governance gate).
        items = []
        for record in self.retrieval.register.list():
            if record.approval_status != "approved":
                continue
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
        t0 = time.time()
        if not question.strip():
            return self._record(question, t0, AnswerResult(answer=REFUSAL, citations=[], mode="empty", refused=True))

        guard = self.guardrails.check(question)
        if not guard.allowed:
            return self._record(question, t0, AnswerResult(
                answer=guard.message or REFUSAL, citations=[], mode="guardrail",
                refused=True, category=guard.category,
            ))

        items = self._all_sections()
        if not items:
            return self._record(question, t0, AnswerResult(answer=REFUSAL, citations=[], mode="empty", refused=True))

        total_chars = sum(len(section.text) for _, section in items)
        if total_chars <= self.full_context_char_limit:
            evidence = [self._evidence(record, section) for record, section in items]
            mode = "full-context"
        else:
            results, _ = self.retrieval.search(question, top_k)
            if not results:
                return self._record(question, t0, AnswerResult(answer=REFUSAL, citations=[], mode="retrieval", refused=True))
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
        if not refused:
            answer_text = _normalize_markers(answer_text)

        # Output guardrail: block harmful content the model may have produced.
        if not refused:
            out_guard = self.guardrails.check_output(answer_text)
            if not out_guard.allowed:
                return self._record(question, t0, AnswerResult(
                    answer=out_guard.message or REFUSAL, citations=[], mode="guardrail",
                    refused=True, category=out_guard.category,
                ))

        # Cite only what the model explicitly referenced via [n] markers. Answers
        # that use no evidence (a decline or an off-topic reply) carry no citations.
        chosen = [] if refused else [evidence[i - 1] for i in _cited_indices(answer_text, len(evidence))]
        # Retrieval-mode fallback: every retrieved passage was selected as relevant to
        # this question (relevance threshold + rerank), so when the model answers but
        # omits its [n] markers, attribute the answer to the passages it was given
        # rather than showing an answer with no source. (Not applied in full-context
        # mode, where the evidence is the whole KB and is not question-specific.)
        if not refused and not chosen and mode == "retrieval":
            chosen = evidence
        citations = [
            Citation(**{k: e[k] for k in ("source_id", "source_title", "heading", "ordinal")}) for e in chosen
        ]
        # Validate that the answer is actually supported by its cited evidence.
        grounding = "n/a"
        if chosen and self.validator is not None:
            grounding = self.validator.validate(answer_text, [e["text"] for e in chosen])
        # "grounded" requires citations AND that validation did not find it unsupported;
        # otherwise "unverified" (a cited-but-unsupported answer is a hallucination signal).
        if refused:
            confidence = "none"
        elif chosen and grounding != "unsupported":
            confidence = "grounded"
        else:
            confidence = "unverified"
        return self._record(question, t0, AnswerResult(
            answer=answer_text, citations=citations, mode=mode, refused=refused,
            confidence=confidence, grounding=grounding,
        ))
