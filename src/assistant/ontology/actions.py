"""Governed ontology action execution.

Actions are the controlled mutation surface for the ontology-backed platform:
schema-declared parameters in, validation results and an audit record out.
Handlers remain ordinary Python callables so existing services can be wrapped
without duplicating their business logic.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ..iam.context import current_principal
from ..storage import write_json
from .schema import ActionTypeDef, ParamDef, SchemaRegistry
from .store import OntologyStore

ActionOutcome = Literal["ok", "rejected", "error"]
ActorType = Literal["operator", "agent"]


class ActionActor(BaseModel):
    """Who requested the governed action."""

    model_config = ConfigDict(extra="forbid")

    type: ActorType
    id: str = ""
    name: str = ""
    approved_by: str | None = None


def acting_person(fallback: str = "system", approved_by: str | None = None, agent_run: str | None = None) -> ActionActor:
    """Who acts in this request: the signed-in person, by stable id and name (REF S3). ``fallback`` names the actor
    when no person is signed in (a start-up rebuild, a host script, a call with the workspace's service key). With
    ``agent_run``, the agent is the actor and the person is who approved its proposal."""
    principal = current_principal()
    if agent_run is not None:
        return ActionActor(type="agent", id=agent_run, approved_by=principal.id if principal else approved_by)
    if principal is None:
        return ActionActor(type="operator", id=fallback)
    return ActionActor(type="operator", id=principal.id, name=principal.display_name)


class ValidationResult(BaseModel):
    """One rule/parameter validation outcome."""

    model_config = ConfigDict(extra="forbid")

    rule: str
    passed: bool
    message: str = ""


class ActionExecution(BaseModel):
    """Persisted audit record for one action attempt."""

    model_config = ConfigDict(extra="forbid")

    execution_id: str
    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    actor: ActionActor
    validation_results: list[ValidationResult] = Field(default_factory=list)
    outcome: ActionOutcome
    duration_ms: int
    timestamp: str
    failed_rule: str | None = None
    message: str = ""
    result: dict[str, Any] = Field(default_factory=dict)


class ActionExecutionResult(BaseModel):
    """Public result returned to callers after an action attempt."""

    model_config = ConfigDict(extra="forbid")

    execution_id: str
    action: str
    outcome: ActionOutcome
    validation_results: list[ValidationResult] = Field(default_factory=list)
    failed_rule: str | None = None
    message: str = ""
    result: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int
    timestamp: str


@dataclass(frozen=True)
class ActionContext:
    action: ActionTypeDef
    params: dict[str, Any]
    actor: ActionActor


ActionHandler = Callable[[ActionContext], dict[str, Any] | None]
ValidationRule = Callable[[ActionContext], ValidationResult]
SideEffect = Callable[[ActionContext, dict[str, Any]], dict[str, Any] | None]


class ActionLog:
    """Thread-safe JSON audit log for governed actions."""

    def __init__(self, base_dir: str | Path, filename: str = "action_log.json") -> None:
        self.path = Path(base_dir) / filename
        self._lock = threading.Lock()

    def append(self, execution: ActionExecution) -> ActionExecution:
        with self._lock:
            rows = self._read_unlocked()
            rows.append(execution.model_dump())
            self.path.parent.mkdir(parents=True, exist_ok=True)
            write_json(self.path, rows, indent=2)
        return execution

    def recent(self, limit: int = 50) -> list[ActionExecution]:
        safe_limit = max(1, min(limit, 500))
        rows = self._read()
        return [ActionExecution.model_validate(row) for row in reversed(rows[-safe_limit:])]

    def _read(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read_unlocked()

    def _read_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8") or "[]")


class ActionsEngine:
    """Execute schema-declared actions through one validated/audited path."""

    def __init__(
        self,
        store: OntologyStore,
        *,
        base_dir: str | Path | None = None,
        registry: SchemaRegistry | None = None,
        action_log: ActionLog | None = None,
    ) -> None:
        self.store = store
        self.registry = registry or store.registry
        self.action_log = action_log or ActionLog(base_dir or store.db_path.parent)
        self._handlers: dict[str, ActionHandler] = {}
        self._validation_rules: dict[str, ValidationRule] = {
            "auth_required": self._validate_auth_required,
        }
        self._side_effects: dict[str, SideEffect] = {}

    def register_handler(self, action_api_name: str, handler: ActionHandler) -> None:
        self.registry.require_action_type(action_api_name)
        self._handlers[action_api_name] = handler

    def register_validation_rule(self, name: str, rule: ValidationRule) -> None:
        self._validation_rules[name] = rule

    def register_side_effect(self, name: str, side_effect: SideEffect) -> None:
        self._side_effects[name] = side_effect

    def action_definitions(self) -> list[dict[str, Any]]:
        definitions: list[dict[str, Any]] = []
        for action in self.registry.schema.action_types:
            payload = action.model_dump()
            payload["handler_registered"] = action.api_name in self._handlers
            payload["side_effects_registered"] = {
                name: name in self._side_effects
                for name in action.side_effects
            }
            definitions.append(payload)
        return definitions

    def execute(self, action_api_name: str, params: dict[str, Any] | None, actor: ActionActor | dict[str, Any]) -> ActionExecutionResult:
        action = self.registry.require_action_type(action_api_name)
        action_actor = actor if isinstance(actor, ActionActor) else ActionActor.model_validate(actor)
        started = time.perf_counter()
        timestamp = _now()
        execution_id = f"act-{uuid4().hex}"
        validation_results: list[ValidationResult] = []
        clean_params: dict[str, Any] = {}
        outcome: ActionOutcome = "ok"
        message = "Action executed."
        failed_rule: str | None = None
        result: dict[str, Any] = {}

        try:
            clean_params, parameter_results = self._coerce_and_validate_params(action, params or {})
            validation_results.extend(parameter_results)
            if action.requires_human_approval and action_actor.type == "agent" and not action_actor.approved_by:
                validation_results.append(_failed("human_approval_required",
                                                  "This action changes knowledge: a person must approve it first."))
            if any(not item.passed for item in validation_results):
                outcome, failed_rule, message = _rejection(validation_results)
            else:
                context = ActionContext(action=action, params=clean_params, actor=action_actor)
                validation_results.extend(self._run_validation_rules(context))
                if any(not item.passed for item in validation_results):
                    outcome, failed_rule, message = _rejection(validation_results)
                else:
                    result = self._run_handler_and_side_effects(context)
                    if result.get("side_effects_failed"):  # the decision stands; the steps after it are noted (S5)
                        message = ("The action took effect; these steps after it did not complete: "
                                   + ", ".join(result["side_effects_failed"]))
        except Exception as exc:  # handler errors are audited instead of escaping.
            outcome = "error"
            message = str(exc)

        duration_ms = int((time.perf_counter() - started) * 1000)
        execution = ActionExecution(
            execution_id=execution_id,
            action=action.api_name,
            params=_truncate_params(clean_params or params or {}),
            actor=action_actor,
            validation_results=validation_results,
            outcome=outcome,
            duration_ms=duration_ms,
            timestamp=timestamp,
            failed_rule=failed_rule,
            message=message,
            result=result,
        )
        self.action_log.append(execution)
        return ActionExecutionResult(
            execution_id=execution.execution_id,
            action=execution.action,
            outcome=execution.outcome,
            validation_results=execution.validation_results,
            failed_rule=execution.failed_rule,
            message=execution.message,
            result=execution.result,
            duration_ms=execution.duration_ms,
            timestamp=execution.timestamp,
        )

    def _coerce_and_validate_params(
        self,
        action: ActionTypeDef,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], list[ValidationResult]]:
        expected = {param.name: param for param in action.parameters}
        results: list[ValidationResult] = []
        clean: dict[str, Any] = {}

        unknown = sorted(set(params) - set(expected))
        if unknown:
            results.append(_failed("parameters", f"Unknown parameter(s): {', '.join(unknown)}."))

        for param in action.parameters:
            if param.name not in params:
                if param.required:
                    results.append(_failed("parameters", f"Missing required parameter: {param.name}."))
                continue
            try:
                clean[param.name] = self._coerce_param(param, params[param.name])
            except ValueError as exc:
                results.append(_failed("parameters", str(exc)))

        if not results:
            results.append(ValidationResult(rule="parameters", passed=True, message="Parameters validated."))
        return clean, results

    def _coerce_param(self, param: ParamDef, value: Any) -> Any:
        if value is None and not param.required:
            return None
        if param.type in {"string", "date", "timestamp"}:
            if not isinstance(value, str):
                raise ValueError(f"Parameter {param.name} must be {param.type}.")
            return value
        if param.type == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"Parameter {param.name} must be integer.")
            return value
        if param.type == "double":
            if not isinstance(value, int | float) or isinstance(value, bool):
                raise ValueError(f"Parameter {param.name} must be double.")
            return float(value)
        if param.type == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"Parameter {param.name} must be boolean.")
            return value
        if param.type == "string_list":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"Parameter {param.name} must be a list of strings.")
            return value
        if param.type == "object":
            if not isinstance(value, str):
                raise ValueError(f"Parameter {param.name} must be an ontology object id.")
            found = self.store.get(value)
            if found is None:
                raise ValueError(f"Parameter {param.name} references unknown ontology object id {value}.")
            if param.object_type and found.object_type != param.object_type:
                raise ValueError(
                    f"Parameter {param.name} expects object type {param.object_type}, got {found.object_type}."
                )
            return found.id
        raise ValueError(f"Unsupported parameter type {param.type}.")

    def _run_validation_rules(self, context: ActionContext) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for rule_name in context.action.validation_rules:
            rule = self._validation_rules.get(rule_name)
            if rule is None:
                results.append(_failed(rule_name, f"Validation rule {rule_name} is not registered."))
                continue
            results.append(rule(context))
        return results

    def _run_handler_and_side_effects(self, context: ActionContext) -> dict[str, Any]:
        """The handler is the action's decision; its side effects are the steps after it (REF S23, S5, red team round
        11). Every side effect is known before the decision is taken; once it is taken, a side effect that fails is
        recorded and never turns the decision into a failure, so a caller is never told "refused" for a change made."""
        handler = self._handlers.get(context.action.api_name)
        if handler is None:
            raise RuntimeError(f"No handler registered for action {context.action.api_name}.")
        missing = [name for name in context.action.side_effects if name not in self._side_effects]
        if missing:
            raise RuntimeError(f"Side effect {missing[0]} is not registered.")
        payload: dict[str, Any] = {"handler": handler(context) or {}}
        side_effect_results: dict[str, Any] = {}
        failed: list[str] = []
        for name in context.action.side_effects:
            try:
                side_effect_results[name] = self._side_effects[name](context, payload["handler"]) or {}
            except Exception as exc:  # after the decision: noted, never undone or misreported
                side_effect_results[name] = {"error": str(exc)[:300]}
                failed.append(name)
        if side_effect_results:
            payload["side_effects"] = side_effect_results
        if failed:
            payload["side_effects_failed"] = failed
        return payload

    @staticmethod
    def _validate_auth_required(context: ActionContext) -> ValidationResult:
        if context.actor.id or context.actor.type in {"operator", "agent"}:
            return ValidationResult(rule="auth_required", passed=True, message="Actor present.")
        return _failed("auth_required", "Actor identity is required.")


def _failed(rule: str, message: str) -> ValidationResult:
    return ValidationResult(rule=rule, passed=False, message=message)


def _rejection(results: list[ValidationResult]) -> tuple[ActionOutcome, str | None, str]:
    failed = next((item for item in results if not item.passed), None)
    return "rejected", failed.rule if failed else None, failed.message if failed else "Action rejected."


def _truncate_params(params: dict[str, Any], max_length: int = 300) -> dict[str, Any]:
    return {key: _truncate_value(value, max_length=max_length) for key, value in params.items()}


def _truncate_value(value: Any, *, max_length: int) -> Any:
    if isinstance(value, str):
        if len(value) <= max_length:
            return value
        return f"{value[:max_length]}...[truncated {len(value) - max_length} chars]"
    if isinstance(value, list):
        return [_truncate_value(item, max_length=max_length) for item in value[:20]]
    if isinstance(value, dict):
        return {str(key): _truncate_value(item, max_length=max_length) for key, item in value.items()}
    return value


def _now() -> str:
    return datetime.now(UTC).isoformat()
