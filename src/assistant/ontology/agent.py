"""Bounded ontology-agent loop.

The agent can only read ontology objects/links or propose a governed action.
It never receives raw document chunks and never executes mutations.
"""

from __future__ import annotations

import json
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ..observability.trace import AuditTrace
from .query import OntologyQueryService
from .schema import SchemaRegistry


class AgentGenerator(Protocol):
    def generate(self, prompt: str) -> str: ...


class AgentStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    result_summary: str
    latency_ms: int


class ProposedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    rationale: str
    status: str = "pending"


class AgentRunTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    question: str
    steps: list[AgentStep] = Field(default_factory=list)
    final_answer: str
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    total_latency_ms: int
    created_at: str
    stopped_reason: str = "final_answer"


class AgentRunStore:
    """Thread-safe JSON store for ontology-agent traces."""

    def __init__(self, base_dir: str | Path, filename: str = "agent_runs.json") -> None:
        self.path = Path(base_dir) / filename
        self._lock = threading.Lock()

    def append(self, trace: AgentRunTrace) -> AgentRunTrace:
        with self._lock:
            rows = self._read_unlocked()
            rows.append(trace.model_dump())
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        return trace

    def recent(self, limit: int = 50) -> list[AgentRunTrace]:
        safe_limit = max(1, min(limit, 500))
        with self._lock:
            rows = self._read_unlocked()
        return [AgentRunTrace.model_validate(row) for row in reversed(rows[-safe_limit:])]

    def _read_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8") or "[]")


class OntologyAgent:
    """Small deterministic tool loop over the ontology query service."""

    def __init__(
        self,
        query: OntologyQueryService,
        generator: AgentGenerator,
        *,
        registry: SchemaRegistry | None = None,
        store: AgentRunStore | None = None,
        audit_trace: AuditTrace | None = None,
        max_steps: int = 6,
    ) -> None:
        self.query = query
        self.registry = registry or query.registry
        self.generator = generator
        self.store = store
        self.audit_trace = audit_trace
        self.max_steps = max(1, max_steps)

    def run(self, question: str) -> AgentRunTrace:
        started = time.perf_counter()
        run_id = f"agent-{uuid4().hex}"
        steps: list[AgentStep] = []
        proposed_actions: list[ProposedAction] = []
        observations: list[str] = []
        malformed_retry_used = False
        final_answer = ""
        stopped_reason = "final_answer"

        for _ in range(self.max_steps):
            prompt = self._build_prompt(question, observations)
            response = self.generator.generate(prompt)
            command = _parse_json_object(response)
            if command is None:
                if not malformed_retry_used:
                    malformed_retry_used = True
                    observations.append("Tool protocol error: response was not valid JSON. Retry with strict JSON only.")
                    continue
                final_answer = "I could not complete the ontology investigation because the model did not return valid tool JSON."
                stopped_reason = "malformed_json"
                break

            if "final_answer" in command:
                final_answer = str(command.get("final_answer") or "").strip()
                if not final_answer:
                    final_answer = "I could not derive a final answer from the ontology trace."
                break

            tool = str(command.get("tool", "")).strip()
            args = command.get("args") if isinstance(command.get("args"), dict) else {}
            step_started = time.perf_counter()
            result, summary, proposal = self._call_tool(tool, args)
            latency_ms = int((time.perf_counter() - step_started) * 1000)
            if proposal is not None:
                proposed_actions.append(proposal)
            steps.append(AgentStep(tool=tool or "unknown", args=args, result_summary=summary, latency_ms=latency_ms))
            observations.append(json.dumps({"tool": tool, "result": result}, sort_keys=True))
        else:
            final_answer = "I could not complete the ontology investigation within the configured step limit."
            stopped_reason = "step_cap"

        total_latency_ms = int((time.perf_counter() - started) * 1000)
        trace = AgentRunTrace(
            run_id=run_id,
            question=question,
            steps=steps,
            final_answer=final_answer,
            proposed_actions=proposed_actions,
            total_latency_ms=total_latency_ms,
            created_at=_now(),
            stopped_reason=stopped_reason,
        )
        if self.store is not None:
            self.store.append(trace)
        if self.audit_trace is not None:
            self.audit_trace.append({
                "timestamp": trace.created_at,
                "question": question,
                "mode": "ontology_agent",
                "answer_path": "oag_agent",
                "outcome": "answered" if stopped_reason == "final_answer" else "declined",
                "steps": [step.model_dump() for step in steps],
                "proposed_actions": [item.model_dump() for item in proposed_actions],
                "latency_ms": total_latency_ms,
                "run_id": run_id,
            })
        return trace

    def _build_prompt(self, question: str, observations: list[str]) -> str:
        observation_text = "\n".join(f"- {item}" for item in observations[-self.max_steps:]) or "- none yet"
        return "\n".join([
            "You are a local ontology agent. Use only the tools listed here.",
            "Never ask for raw document text. Never execute an action.",
            self.registry.describe_for_llm(),
            "Return strict JSON only. Use exactly one of:",
            '{"tool":"search_objects","args":{"type":"process|role|system|control|source|obligation|internal_claim|compliance_finding","query":"text"}}',
            '{"tool":"get_object","args":{"id":"ontology-object-id"}}',
            '{"tool":"traverse_links","args":{"from_id":"ontology-object-id","link_type":"process_uses_system","direction":"out|in"}}',
            '{"tool":"propose_action","args":{"action":"action_api_name","params":{},"rationale":"why"}}',
            '{"final_answer":"answer grounded in the ontology trace"}',
            f"Question: {question}",
            "Observations:",
            observation_text,
        ])

    def _call_tool(self, tool: str, args: dict[str, Any]) -> tuple[dict[str, Any], str, ProposedAction | None]:
        if tool == "search_objects":
            object_type = str(args.get("type") or args.get("object_type") or "")
            query_text = str(args.get("query") or "")
            if not object_type:
                return {"error": "type is required"}, "search_objects rejected: type is required.", None
            try:
                objects = self.query.find_objects(object_type, query=query_text)
            except (KeyError, ValueError) as exc:
                return {"error": str(exc)}, f"search_objects failed: {exc}", None
            slim = [_slim_object(item) for item in objects[:10]]
            return {"objects": slim, "count": len(objects)}, f"Found {len(objects)} {object_type} object(s).", None

        if tool == "get_object":
            object_id = str(args.get("id") or "")
            found = self.query.get_object(object_id) if object_id else None
            if found is None:
                return {"error": "object not found"}, "get_object found no object.", None
            return {"object": _slim_object(found, include_neighbors=True)}, f"Loaded {found['citation']}.", None

        if tool == "traverse_links":
            from_id = str(args.get("from_id") or "")
            link_type = str(args.get("link_type") or args.get("link") or "")
            direction = str(args.get("direction") or "out")
            if direction not in {"out", "in"}:
                return {"error": "direction must be out or in"}, "traverse_links rejected: bad direction.", None
            try:
                objects = self.query.traverse(from_id, link_type, direction=direction)  # type: ignore[arg-type]
            except (KeyError, ValueError) as exc:
                return {"error": str(exc)}, f"traverse_links failed: {exc}", None
            slim = [_slim_object(item) for item in objects[:10]]
            return {"objects": slim, "count": len(objects)}, f"Traversed {len(objects)} linked object(s).", None

        if tool == "propose_action":
            action = str(args.get("action") or "")
            params = args.get("params") if isinstance(args.get("params"), dict) else {}
            rationale = str(args.get("rationale") or "").strip()
            proposal = ProposedAction(
                proposal_id=f"proposal-{uuid4().hex}",
                action=action,
                params=params,
                rationale=rationale,
            )
            return proposal.model_dump(), f"Proposed action {action}; awaiting human approval.", proposal

        return {"error": f"unknown tool {tool}"}, f"Unknown tool: {tool}.", None


def _slim_object(item: dict[str, Any], *, include_neighbors: bool = False) -> dict[str, Any]:
    slim = {
        "id": item["id"],
        "object_type": item["object_type"],
        "primary_key_value": item["primary_key_value"],
        "properties": _safe_properties(item.get("properties", {})),
        "citation": item["citation"],
    }
    if include_neighbors:
        slim["neighbors"] = _neighbor_summary(item.get("neighbors", {}))
    return slim


def _safe_properties(properties: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in properties.items():
        if isinstance(value, str):
            safe[key] = value[:300]
        elif isinstance(value, list):
            safe[key] = [str(item)[:200] for item in value[:20]]
        elif isinstance(value, int | float | bool) or value is None:
            safe[key] = value
        else:
            safe[key] = str(value)[:200]
    return safe


def _neighbor_summary(neighbors: Any) -> dict[str, dict[str, list[str]]]:
    if not isinstance(neighbors, dict):
        return {}
    summary: dict[str, dict[str, list[str]]] = {}
    for link_type, grouped in neighbors.items():
        if not isinstance(grouped, dict):
            continue
        summary[str(link_type)] = {}
        for direction, objects in grouped.items():
            if isinstance(objects, list):
                summary[str(link_type)][str(direction)] = [str(item.get("id", "")) for item in objects[:20] if isinstance(item, dict)]
    return summary


def _parse_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if match is None:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _now() -> str:
    return datetime.now(UTC).isoformat()
