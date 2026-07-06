"""Grounded answer orchestration."""

from __future__ import annotations

import re
import time
from typing import Literal

from pydantic import BaseModel

from ..analytics.classify import classify_topic
from ..analytics.event_store import AnalyticsEventStore
from ..analytics.events import ActorType, MetadataValue
from ..analytics.log import UsageEntry, UsageLog, now_iso
from ..guardrails.checker import GuardrailChecker
from ..observability.trace import AuditTrace
from ..ontology.query import OntologyQueryService
from ..ontology.router import build_structured_answer_plan, classify_question, matching_ontology_evidence
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


_ACTION_REQUEST_RE = re.compile(
    r"\b(approve|approval|authorise|authorize|activate|change|update|create|delete|submit|accept|reject|onboard|decide)\b",
    re.IGNORECASE,
)
_DECLINE_RESPONSE_RE = re.compile(
    r"\b(cannot|can't|not able|unable|human review|human reviewer|human decision|approval decision)\b",
    re.IGNORECASE,
)


def _outcome(question: str, result: "AnswerResult") -> str:
    if result.refused and result.mode == "guardrail":
        return "blocked"
    if _ACTION_REQUEST_RE.search(question) and (result.refused or _DECLINE_RESPONSE_RE.search(result.answer)):
        return "declined"
    if result.refused:
        return "refused"
    return "answered"


# When the whole knowledge base is below this size, pass it in full instead of
# retrieving chunks (the benchmark's small-KB strategy — see docs/benchmark).
FULL_CONTEXT_CHAR_LIMIT = 24000


class Citation(BaseModel):
    source_id: str
    source_title: str
    heading: str
    ordinal: int
    citation_type: str = "document"


class AnswerResult(BaseModel):
    answer: str
    citations: list[Citation]
    mode: str
    answer_path: str = "rag"  # oag | rag | rag+ontology
    refused: bool
    category: str | None = None
    confidence: str = "none"  # grounded | unverified | none
    grounding: str = "n/a"  # supported | partial | unsupported | n/a
    grounding_score: float = 0.0
    faithfulness: str = "n/a"


RoutingMode = Literal["oag_first", "rag_only", "oag_only"]


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
        process_registry=None,
        ontology_query: OntologyQueryService | None = None,
        event_store: AnalyticsEventStore | None = None,
    ) -> None:
        self.retrieval = retrieval
        self.generator = generator
        self.full_context_char_limit = full_context_char_limit
        self.guardrails = guardrails or GuardrailChecker()
        self.usage_log = usage_log
        self.validator = validator
        self.audit_trace = audit_trace
        self.model_info = model_info
        self.process_registry = process_registry
        self.ontology_query = ontology_query
        self.event_store = event_store

    def _record(
        self,
        question: str,
        t0: float,
        result: "AnswerResult",
        *,
        actor_type: ActorType = "operator",
        actor_id: str | None = None,
        process_area: str | None = None,
        persona: str | None = None,
        value_driver: str | None = None,
        telemetry_metadata: dict[str, MetadataValue] | None = None,
    ) -> "AnswerResult":
        timestamp = now_iso()
        latency_ms = int((time.time() - t0) * 1000)
        outcome = _outcome(question, result)
        if self.usage_log is not None:
            self.usage_log.append(UsageEntry(
                timestamp=timestamp, question=question, mode=result.mode, refused=result.refused,
                category=result.category, confidence=result.confidence, citation_count=len(result.citations),
                answer_path=result.answer_path,
            ))
        if self.audit_trace is not None:
            self.audit_trace.append({
                "timestamp": timestamp, "question": question, "mode": result.mode,
                "answer_path": result.answer_path,
                "outcome": outcome, "refused": result.refused, "category": result.category,
                "confidence": result.confidence, "grounding": result.grounding,
                "grounding_score": result.grounding_score, "faithfulness": result.faithfulness,
                "latency_ms": latency_ms,
                "actor_type": actor_type, "actor_id": actor_id, "persona": persona,
                "process_area": process_area, "value_driver": value_driver,
                "model": self.model_info or {}, "prompt_version": PROMPT_VERSION,
                "evidence": [
                    {"source_title": c.source_title, "heading": c.heading, "ordinal": c.ordinal}
                    for c in result.citations
                ],
            })
        if self.event_store is not None:
            if result.refused and result.mode == "guardrail":
                event_type = "ask_guardrail_blocked"
            elif result.refused:
                event_type = "ask_refused"
            else:
                event_type = "ask_answered"
            metadata: dict[str, MetadataValue] = {
                "outcome": outcome,
                "mode": result.mode,
                "answer_path": result.answer_path,
                "category": result.category,
                "confidence": result.confidence,
                "grounding": result.grounding,
                "grounding_score": result.grounding_score,
                "faithfulness": result.faithfulness,
                "citation_count": len(result.citations),
                "latency_ms": latency_ms,
                "question_length": len(question.strip()),
                "topic": classify_topic(question),
            }
            if telemetry_metadata:
                metadata.update(telemetry_metadata)
            self.event_store.record(
                event_type,
                timestamp=timestamp,
                actor_type=actor_type,
                actor_id=actor_id,
                entity_type="ask",
                outcome=outcome,
                process_area=process_area,
                persona=persona,
                value_driver=value_driver,
                metadata=metadata,
            )
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

    def _process_records(self) -> list:
        """Return process records for currently approved sources.

        The process registry is persisted for inspection, but Ask should not depend on
        an operator opening the registry page before process evidence becomes usable.
        """
        if self.process_registry is None:
            return []
        if hasattr(self.process_registry, "build_from_sources"):
            return self.process_registry.build_from_sources(self.retrieval.register)
        return self.process_registry.list()

    @staticmethod
    def _evidence(record, section) -> dict:
        return {
            "source_id": record.id,
            "source_title": record.title,
            "heading": section.heading,
            "ordinal": section.ordinal,
            "text": section.text,
        }

    def answer(
        self,
        question: str,
        top_k: int = 5,
        *,
        routing_mode: RoutingMode = "oag_first",
        actor_type: ActorType = "operator",
        actor_id: str | None = None,
        process_area: str | None = None,
        persona: str | None = None,
        value_driver: str | None = None,
        telemetry_metadata: dict[str, MetadataValue] | None = None,
    ) -> AnswerResult:
        t0 = time.time()
        if routing_mode not in {"oag_first", "rag_only", "oag_only"}:
            raise ValueError("routing_mode must be 'oag_first', 'rag_only' or 'oag_only'.")

        def record(result: AnswerResult) -> AnswerResult:
            return self._record(
                question,
                t0,
                result,
                actor_type=actor_type,
                actor_id=actor_id,
                process_area=process_area,
                persona=persona,
                value_driver=value_driver,
                telemetry_metadata=telemetry_metadata,
            )

        if not question.strip():
            return record(AnswerResult(answer=REFUSAL, citations=[], mode="empty", refused=True))

        guard = self.guardrails.check(question)
        if not guard.allowed:
            return record(AnswerResult(
                answer=guard.message or REFUSAL, citations=[], mode="guardrail",
                refused=True, category=guard.category,
            ))

        if (
            routing_mode in {"oag_first", "oag_only"}
            and self.ontology_query is not None
            and classify_question(question, self.ontology_query.schema()) == "structured"
        ):
            oag_result = self._answer_from_ontology(question)
            if oag_result is not None:
                return record(oag_result)

        if routing_mode == "oag_only":
            return record(AnswerResult(answer=REFUSAL, citations=[], mode="oag-only", answer_path="oag", refused=True))

        items = self._all_sections()
        if not items:
            return record(AnswerResult(answer=REFUSAL, citations=[], mode="empty", refused=True))

        total_chars = sum(len(section.text) for _, section in items)
        if total_chars <= self.full_context_char_limit:
            evidence = [self._evidence(record, section) for record, section in items]
            mode = "full-context"
        else:
            results, _ = self.retrieval.search(question, top_k)
            if not results:
                return record(AnswerResult(answer=REFUSAL, citations=[], mode="retrieval", refused=True))
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

        answer_path = "rag"
        if routing_mode != "rag_only" and self.ontology_query is not None:
            ontology_evidence = matching_ontology_evidence(question, self.ontology_query)
            if ontology_evidence:
                evidence = evidence + ontology_evidence
                answer_path = "rag+ontology"
        elif routing_mode != "rag_only" and self.process_registry is not None:
            # Legacy fallback for tests or embedded services not yet wired to the ontology.
            from ..process.router import match_process
            proc = match_process(question, self._process_records())
            if proc is not None:
                evidence = evidence + [{
                    "source_id": proc.id,
                    "source_title": f"Process registry: {proc.name}",
                    "heading": "structured facts",
                    "ordinal": 0,
                    "text": proc.as_evidence_text(),
                    "citation_type": "process_registry",
                }]
                answer_path = "rag+ontology"

        answer_text, refused = _finalize(self.generator.generate(build_prompt(question, evidence)))
        if not refused:
            answer_text = _normalize_markers(answer_text)

        # Output guardrail: block harmful content the model may have produced.
        if not refused:
            out_guard = self.guardrails.check_output(answer_text)
            if not out_guard.allowed:
                return record(AnswerResult(
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
            Citation(
                **{k: e[k] for k in ("source_id", "source_title", "heading", "ordinal")},
                citation_type=e.get("citation_type", "document"),
            )
            for e in chosen
        ]
        # Validate that the answer is actually supported by its cited evidence.
        grounding = "n/a"
        grounding_score = 0.0
        faithfulness = "n/a"
        if chosen and self.validator is not None:
            if hasattr(self.validator, "assess"):
                assessment = self.validator.assess(answer_text, [e["text"] for e in chosen])
                grounding = assessment.label
                grounding_score = assessment.score
                faithfulness = assessment.faithfulness
            else:
                grounding = self.validator.validate(answer_text, [e["text"] for e in chosen])
                grounding_score = {"supported": 1.0, "partial": 0.5, "unsupported": 0.0}.get(grounding, 0.0)
                faithfulness = {"supported": "faithful", "partial": "partially_faithful", "unsupported": "unfaithful"}.get(
                    grounding, "n/a"
                )
        # "grounded" requires citations AND that validation did not find it unsupported;
        # otherwise "unverified" (a cited-but-unsupported answer is a hallucination signal).
        if refused:
            confidence = "none"
        elif chosen and grounding != "unsupported":
            confidence = "grounded"
        else:
            confidence = "unverified"
        return record(AnswerResult(
            answer=answer_text, citations=citations, mode=mode, refused=refused,
            answer_path=answer_path,
            confidence=confidence, grounding=grounding, grounding_score=grounding_score, faithfulness=faithfulness,
        ))

    def _answer_from_ontology(self, question: str) -> AnswerResult | None:
        if self.ontology_query is None:
            return None
        plan = build_structured_answer_plan(question, self.ontology_query)
        if plan is None:
            return None
        answer_text, refused = _finalize(self.generator.generate(build_prompt(question, plan.evidence)))
        if not refused:
            answer_text = _normalize_markers(answer_text)
            out_guard = self.guardrails.check_output(answer_text)
            if not out_guard.allowed:
                return AnswerResult(
                    answer=out_guard.message or REFUSAL,
                    citations=[],
                    mode="guardrail",
                    answer_path="oag",
                    refused=True,
                    category=out_guard.category,
                )
        chosen = [] if refused else [plan.evidence[i - 1] for i in _cited_indices(answer_text, len(plan.evidence))]
        if not refused and not chosen:
            chosen = plan.evidence
        citations = [
            Citation(
                **{k: item[k] for k in ("source_id", "source_title", "heading", "ordinal")},
                citation_type=item.get("citation_type", "ontology_object"),
            )
            for item in chosen
        ]
        return AnswerResult(
            answer=answer_text,
            citations=citations,
            mode="oag",
            answer_path="oag",
            refused=refused,
            confidence="none" if refused else "grounded",
        )
