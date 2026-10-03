"""Grounded answer orchestration."""

from __future__ import annotations

import re
import time
from collections import Counter
from datetime import date
from typing import Literal

from pydantic import BaseModel

from .. import settings
from ..analytics.classify import classify_topic
from ..analytics.event_store import AnalyticsEventStore
from ..analytics.events import ActorType, MetadataValue
from ..analytics.log import UsageEntry, UsageLog, now_iso
from ..evidence.contract import EvidenceBundle, EvidenceItem, EvidenceRequest
from ..evidence.receipts import ReceiptStore, digest
from ..guardrails.checker import GuardrailChecker
from ..iam.context import current_principal
from ..iam.visibility import hides_any, visible
from ..observability import fallbacks
from ..observability.trace import AuditTrace
from ..ontology.query import OntologyQueryService
from ..ontology.router import (
    build_structured_answer_plan,
    classify_question,
    is_unsupported_lookup,
    matching_ontology_evidence,
)
from ..retrieval.service import RetrievalService
from ..space_config import DEFAULT as DEFAULT_SPACE_CONFIG
from ..space_config import SpaceConfig
from ..space_statements import note_key
from .generator import Generator
from .prompt import PROMPT_VERSION, REFUSAL, build_prompt
from .scope import ScopeFilter, parts


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


def _citation_type_counts(citations: list["Citation"]) -> dict[str, int]:
    if not citations:
        return {"none": 1}
    return dict(Counter(citation.citation_type or "document" for citation in citations))


def _evidence_mix(citation_counts: dict[str, int]) -> tuple[float, float, bool]:
    deterministic = citation_counts.get("ontology_object", 0) + citation_counts.get("process_registry", 0)
    generative = citation_counts.get("document", 0)
    total = deterministic + generative
    if total <= 0:
        return 0.0, 0.0, False
    deterministic_ratio = round(deterministic / total, 3)
    generative_ratio = round(generative / total, 3)
    return deterministic_ratio, generative_ratio, deterministic_ratio >= 0.5


# When the whole knowledge base is below this size, pass it in full instead of
# retrieving chunks (the benchmark's small-KB strategy — see docs/benchmark).
FULL_CONTEXT_CHAR_LIMIT = 24000
WITHHELD = "(An answer was prepared, but its sources did not support it, so it is not shown.)"  # REF H1


class Citation(BaseModel):
    source_id: str
    source_title: str
    heading: str
    ordinal: int
    citation_type: str = "document"
    # What the answer rested on (REF S18): the document's version and that text's SHA-256, and the passage's own hash.
    version: int | None = None
    sha256: str | None = None
    passage_sha256: str | None = None


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
    receipt_id: str | None = None  # the stored evidence receipt (REF S18)
    # What retrieval gave the model ("source_id#ordinal"), and the parts of a multi-part question with nothing behind
    # them (REF H4). Empty in full-context mode, where the model is given everything.
    considered: list[str] = []
    missing_parts: list[str] = []
    statements: list[dict] = []  # the space's governed fixed sentences this answer said, with their versions (REF S22)


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
        space_config: SpaceConfig | None = None,
    ) -> None:
        self.retrieval = retrieval
        self.generator = generator
        self.full_context_char_limit = full_context_char_limit
        self.space_config = space_config or DEFAULT_SPACE_CONFIG  # the space's cues and refusal wording (ARCH H2)
        self._space = self.space_config.compiled()
        self.refusal = self.space_config.refusal
        self.guardrails = guardrails or GuardrailChecker(config=self.space_config)
        self.usage_log = usage_log
        self.validator = validator
        self.audit_trace = audit_trace
        self.model_info = model_info
        self.process_registry = process_registry
        self.ontology_query = ontology_query
        self.event_store = event_store
        self.statements = None  # the space's governed fixed sentences (REF S22), set by the app
        self.receipts: ReceiptStore | None = None  # set by the app (REF S18)
        self.version_of = None  # source id -> {"n", "sha"}: the version a citation rests on (REF S18)

    def _stamp(self, citations: list[Citation]) -> list[Citation]:
        """Each document citation names the version of the text it rested on (REF S18)."""
        if self.version_of is None:
            return citations
        stamped = []
        for citation in citations:
            current = self.version_of(citation.source_id) if citation.citation_type == "document" else None
            stamped.append(citation.model_copy(update={"version": current["n"], "sha256": current["sha"]}) if current else citation)
        return stamped

    def bundle(self, question: str, result: "AnswerResult", *, actor_id, space) -> EvidenceBundle:
        """The answer's evidence in the contract both answer paths share (REF S19)."""
        return EvidenceBundle(
            request=EvidenceRequest(person=actor_id, spaces=[space] if space else [], question_sha256=digest(question),
                                    channel="written"),
            items=[EvidenceItem(kind="object" if c.citation_type == "ontology_object" else "passage", source_id=c.source_id,
                                space=space, title=c.source_title, locator=f"{c.heading} #{c.ordinal}", version=c.version,
                                sha256=c.sha256) for c in result.citations],
            refusal=self.refusal, referral=self.space_config.referral.sentence or None)

    def _receipt(self, question: str, result: "AnswerResult", *, actor_id, space, timestamp, latency_ms) -> str | None:
        if self.receipts is None:
            return None
        bundle = self.bundle(question, result, actor_id=actor_id, space=space)
        return self.receipts.write({
            "channel": "written", "space": space, "person": actor_id, "asked_at": timestamp, "latency_ms": latency_ms,
            "question_sha256": digest(question), "answer_sha256": digest(result.answer), "mode": result.mode,
            "answer_path": result.answer_path, "refused": result.refused, "grounding": result.grounding,
            "model": self.model_info or {}, "prompt_version": PROMPT_VERSION,
            "evidence": [c.model_dump() for c in result.citations], "contract": bundle.summary(),
            "statements": result.statements,
        })

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
        # Who asked, and where (REF S9): the signed-in person of the request unless the caller names another actor.
        principal = current_principal()
        if actor_id is None and actor_type == "operator" and principal is not None:
            actor_id = principal.id
        space = getattr(self, "space_id", None)
        result = result.model_copy(update={"citations": self._stamp(result.citations)})
        receipt_id = self._receipt(question, result, actor_id=actor_id, space=space, timestamp=timestamp, latency_ms=latency_ms)
        if receipt_id:
            result = result.model_copy(update={"receipt_id": receipt_id})
        citation_type_counts = _citation_type_counts(result.citations)
        deterministic_ratio, generative_ratio, deterministic_flag = _evidence_mix(citation_type_counts)
        if self.usage_log is not None:
            self.usage_log.append(UsageEntry(
                actor_type=actor_type, actor_id=actor_id, space=space,
                timestamp=timestamp, question=question, mode=result.mode, refused=result.refused,
                category=result.category, confidence=result.confidence, citation_count=len(result.citations),
                answer_path=result.answer_path,
                citation_type_counts=citation_type_counts,
                deterministic_evidence_ratio=deterministic_ratio,
                generative_evidence_ratio=generative_ratio,
                deterministic_evidence_flag=deterministic_flag,
            ))
        if self.audit_trace is not None:
            self.audit_trace.append({
                "timestamp": timestamp, "question": question, "mode": result.mode,
                "answer_path": result.answer_path,
                "citation_type_counts": citation_type_counts,
                "deterministic_evidence_ratio": deterministic_ratio,
                "generative_evidence_ratio": generative_ratio,
                "deterministic_evidence_flag": deterministic_flag,
                "outcome": outcome, "refused": result.refused, "category": result.category,
                "confidence": result.confidence, "grounding": result.grounding,
                "grounding_score": result.grounding_score, "faithfulness": result.faithfulness,
                "latency_ms": latency_ms,
                "actor_type": actor_type, "actor_id": actor_id, "space": space, "persona": persona,
                "process_area": process_area, "value_driver": value_driver,
                "model": self.model_info or {}, "prompt_version": PROMPT_VERSION,
                "fallbacks": fallbacks.collect(),  # what fell back on the way to this answer (ARCH F5)
                "receipt_id": result.receipt_id,
                "evidence": [
                    {
                        "source_id": c.source_id,
                        "source_title": c.source_title,
                        "heading": c.heading,
                        "ordinal": c.ordinal,
                        "citation_type": c.citation_type,
                        "version": c.version,
                        "sha256": c.sha256,
                    }
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
                "citation_document_count": citation_type_counts.get("document", 0),
                "citation_ontology_object_count": citation_type_counts.get("ontology_object", 0),
                "citation_process_registry_count": citation_type_counts.get("process_registry", 0),
                "citation_none_count": citation_type_counts.get("none", 0),
                "deterministic_evidence_ratio": deterministic_ratio,
                "generative_evidence_ratio": generative_ratio,
                "deterministic_evidence_flag": deterministic_flag,
                "latency_ms": latency_ms,
                "question_length": len(question.strip()),
                "topic": classify_topic(question),
            }
            if space:
                metadata["space"] = space
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
            if record.approval_status != "approved" or not visible(record.id):  # REF S13
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
            records = self.process_registry.build_from_sources(self.retrieval.register)
        else:
            records = self.process_registry.list()
        return [r for r in records if visible(getattr(r, "source_id", ""))]  # REF S13

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

        fallbacks.begin()

        def record(result: AnswerResult) -> AnswerResult:
            return self._record(
                question,
                t0,
                self._refer(question, result),
                actor_type=actor_type,
                actor_id=actor_id,
                process_area=process_area,
                persona=persona,
                value_driver=value_driver,
                telemetry_metadata=telemetry_metadata,
            )

        if not question.strip():
            return record(AnswerResult(answer=self.refusal, citations=[], mode="empty", refused=True))

        guard = self.guardrails.check(question)
        if not guard.allowed:
            return record(AnswerResult(
                answer=guard.message or REFUSAL, citations=[], mode="guardrail",
                refused=True, category=guard.category,
            ))

        if is_unsupported_lookup(question, self.space_config):
            return record(AnswerResult(answer=self.refusal, citations=[], mode="unsupported-lookup", refused=True))

        scope = None
        if settings.get("KP_SCOPE_EVIDENCE") == "1":  # REF H3, H3b: a candidate under test
            today = settings.get("KP_SCOPE_TODAY") or ""
            scope = ScopeFilter(self.retrieval.register.list(), question,
                                date.fromisoformat(today) if today else date.today())
        approved = [r for r in self.retrieval.register.list() if r.approval_status == "approved"]
        # REF S13: the facts map is built from every approved document. For a person from whom some are hidden it is
        # not used at all (no structured answer, no facts added): documents alone answer, filtered to what they may read.
        # REF H3b: the same when scope keeps any approved document out of this answer, so no fact from a source not in
        # force, replaced or for another site reaches it through the facts map or the process registry.
        documents_only = hides_any(r.id for r in approved) or (scope is not None and scope.excludes_any(approved))
        facts_allowed = self.ontology_query is not None and not documents_only
        question_class = (classify_question(question, self.ontology_query.schema(), self.space_config)
                          if facts_allowed else "unknown")
        if (
            routing_mode in {"oag_first", "oag_only"}
            and facts_allowed
            and question_class == "structured"
        ):
            oag_result, plan = self._answer_from_ontology(question)
            if oag_result is not None and routing_mode == "oag_only":
                return record(oag_result)
            if oag_result is not None and not oag_result.refused and self._facts_answer(question, plan):
                return record(oag_result)
            if oag_result is not None:  # the facts map refused, or its facts do not answer: the documents may (ARCH H1)
                cause = "the facts map could not answer" if oag_result.refused else "the facts do not answer the question"
                fallbacks.note("facts map", cause, kept="document retrieval")

        if routing_mode == "oag_only":
            return record(AnswerResult(answer=self.refusal, citations=[], mode="oag-only", answer_path="oag", refused=True))

        items = self._all_sections()
        if scope is not None:
            items = [(r, s) for r, s in items if scope.allow(r)]
        if not items:
            return record(AnswerResult(answer=self.refusal, citations=[], mode="empty", refused=True))

        missing: list[str] = []
        considered: list[str] = []
        total_chars = sum(len(section.text) for _, section in items)
        if total_chars <= self.full_context_char_limit:
            evidence = [self._evidence(record, section) for record, section in items]
            mode = "full-context"
        else:
            allow = scope.allow if scope is not None else None
            asked = parts(question) if settings.get("KP_PLAN_PARTS") == "1" else [question]  # REF H4, under test
            if len(asked) > 1:
                results, seen = [], set()
                for part in asked:
                    found, _ = self.retrieval.search(part, max(2, top_k // len(asked) + 1), allow=allow)
                    if not found:
                        missing.append(part)
                    for r in found:
                        if (r.source_id, r.ordinal) not in seen:
                            seen.add((r.source_id, r.ordinal))
                            results.append(r)
            else:
                results, _ = self.retrieval.search(question, top_k, allow=allow)
            if not results:
                return record(AnswerResult(answer=self.refusal, citations=[], mode="retrieval", refused=True))
            considered = [f"{r.source_id}#{r.ordinal}" for r in results]
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
        if routing_mode != "rag_only" and facts_allowed:
            ontology_evidence = matching_ontology_evidence(question, self.ontology_query, self.space_config)
            if ontology_evidence:
                evidence = ontology_evidence + evidence if question_class == "structured" else evidence + ontology_evidence
                answer_path = "rag+ontology"
        elif routing_mode != "rag_only" and self.process_registry is not None and not (scope is not None and scope.excludes_any(approved)):
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

        prompt_evidence = evidence
        if scope is not None:  # each passage says which site it applies to when the question named none (REF H3)
            records = {r.id: r for r in self.retrieval.register.list()}
            prompt_evidence = [{**e, "text": scope.note(records[e["source_id"]]) + e["text"]}
                               if e.get("citation_type", "document") == "document" and e["source_id"] in records else e
                               for e in evidence]
        answer_text, refused = _finalize(self.generator.generate(build_prompt(question, prompt_evidence)))
        if refused:
            answer_text = self.refusal
        else:
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
                passage_sha256=digest(e["text"]),
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
        if not refused and grounding == "unsupported" and settings.get("KP_WITHHOLD_UNSUPPORTED") == "1":
            # REF H1, a candidate under test: the check found the answer unsupported by its sources, so it is held back.
            return record(AnswerResult(
                answer=f"{self.refusal} {WITHHELD}", citations=[], mode=mode, refused=True, category="unsupported",
                answer_path=answer_path, grounding=grounding, grounding_score=grounding_score, faithfulness=faithfulness,
                considered=considered,
            ))
        if missing and not refused:  # REF H4: say which part has nothing approved behind it
            answer_text = f"{answer_text.rstrip()}\n\nNothing approved answers this part: {'; '.join(missing)}."
        return record(AnswerResult(
            answer=answer_text, citations=citations, mode=mode, refused=refused,
            answer_path=answer_path,
            confidence=confidence, grounding=grounding, grounding_score=grounding_score, faithfulness=faithfulness,
            considered=considered, missing_parts=missing,
        ))

    def _refer(self, question: str, result: AnswerResult) -> AnswerResult:
        """The space's notes (ARCH H4c), then its referral (ARCH H2b): an answer to a question on one of their topics
        ends with their sentence. They are added after generation and after the grounding check, so neither the prompt
        nor the grounding sees them; a refusal already speaks the space's wording, and a sentence the answer already
        says is not added again."""
        said = []
        if result.refused:
            scope = self.space_config.guardrails.scope_message
            key = "scope_message" if scope and result.answer.startswith(scope) else (
                "refusal" if result.answer.startswith(self.refusal) else None)
            said = [key] if key else []
            answer = result.answer
        else:
            answer = result.answer
            keyed = [(note_key(n), *c) for n, c in zip([n for n in self.space_config.notes if n.topics], self._space.notes)]
            for key, pattern, sentence in (*keyed, ("referral", self._space.referral_re, self._space.referral_sentence)):
                if sentence and pattern.search(question) and sentence.lower() not in answer.lower():
                    answer = f"{answer.rstrip()}\n\n{sentence}"
                    said.append(key)
        cited = [c for c in (self.statements.cite(k) for k in said) if c] if self.statements is not None else []
        if answer == result.answer and not cited:
            return result
        return result.model_copy(update={"answer": answer, "statements": cited})

    def use_config(self, config: SpaceConfig) -> None:
        """Speak a new configuration's words (an approved statement, REF S22) without a restart."""
        self.space_config, self._space, self.refusal = config, config.compiled(), config.refusal
        self.guardrails = GuardrailChecker(config=config)

    def _facts_answer(self, question: str, plan) -> bool:
        """The answerability check on a facts-map answer (ARCH H1b): a listing of ranked facts (the aggregate plan) is
        matched by words and can list facts that merely resemble the question, so the judge, when there is one, must
        not say NO to it. A precise plan (an owner, a process's controls, systems or roles) answers as it stands: the
        judge only ever cost accuracy there."""
        judge = getattr(self.validator, "answers", None)
        if judge is None or plan is None or getattr(plan, "intent", "") != "aggregate_facts":
            return True
        verdict = judge(question, [e["text"] for e in plan.evidence])
        if verdict is None:
            fallbacks.note("answerability judge", "no verdict", kept="the facts-map answer")
            return True
        return verdict

    def _answer_from_ontology(self, question: str) -> tuple[AnswerResult | None, object]:
        if self.ontology_query is None:
            return None, None
        plan = build_structured_answer_plan(question, self.ontology_query, self.space_config)
        if plan is None:
            return None, None
        if plan.answer:
            answer_text, refused = plan.answer, False
        else:
            answer_text, refused = _finalize(self.generator.generate(build_prompt(question, plan.evidence)))
        if refused:
            answer_text = self.refusal
        else:
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
                ), plan
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
        ), plan
