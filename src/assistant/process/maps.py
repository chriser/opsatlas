"""Process-map draft export from structured process records."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from .models import ProcessRecord


class ProcessMapStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    owner: str = ""
    topic: str = ""
    confidence: str = ""


class ProcessMapEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    label: str = ""


class ProcessMapDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process_id: str
    name: str
    source_title: str
    domain: str = ""
    process: str = ""
    roles: list[str]
    systems: list[str]
    controls: list[str]
    dependencies: list[str]
    open_decisions: list[str]
    steps: list[ProcessMapStep]
    edges: list[ProcessMapEdge]
    mermaid: str


def build_process_map(record: ProcessRecord) -> ProcessMapDraft:
    steps = _steps(record)
    edges = [
        ProcessMapEdge(source=steps[i].id, target=steps[i + 1].id, label="next")
        for i in range(len(steps) - 1)
    ]
    draft = ProcessMapDraft(
        process_id=record.id,
        name=record.name,
        source_title=record.source_title,
        domain=record.domain,
        process=record.process,
        roles=record.roles,
        systems=record.systems,
        controls=record.controls,
        dependencies=record.dependencies,
        open_decisions=[rule for rule in record.business_rules if "requires validation" in rule.lower()],
        steps=steps,
        edges=edges,
        mermaid="",
    )
    draft.mermaid = _mermaid(draft)
    return draft


def build_process_maps(records: list[ProcessRecord]) -> list[ProcessMapDraft]:
    return [build_process_map(record) for record in records]


def _steps(record: ProcessRecord) -> list[ProcessMapStep]:
    if record.rules:
        return [
            ProcessMapStep(
                id=f"step_{idx}",
                label=rule.rule or rule.topic or f"Rule {idx}",
                owner=rule.role.replace("_", " "),
                topic=rule.topic.replace("_", " "),
                confidence=rule.confidence.replace("_", " "),
            )
            for idx, rule in enumerate(record.rules, start=1)
        ]
    if record.business_rules:
        return [
            ProcessMapStep(id=f"step_{idx}", label=rule)
            for idx, rule in enumerate(record.business_rules, start=1)
        ]
    return [ProcessMapStep(id="step_1", label=record.name)]


def _mermaid(draft: ProcessMapDraft) -> str:
    lines = ["flowchart TD", f'  start["{_label("Process: " + draft.name)}"]']
    previous = "start"
    for step in draft.steps:
        label = step.label
        if step.owner:
            label = f"{step.owner}: {label}"
        lines.append(f'  {step.id}["{_label(label)}"]')
        lines.append(f"  {previous} --> {step.id}")
        previous = step.id
    for idx, control in enumerate(draft.controls, start=1):
        node = f"control_{idx}"
        lines.append(f'  {node}{{"{_label("Control: " + control)}"}}')
        lines.append(f"  {node} -. governs .-> start")
    for idx, system in enumerate(draft.systems, start=1):
        node = f"system_{idx}"
        lines.append(f'  {node}[("{_label("System: " + system)}")]')
        lines.append(f"  start -. uses .-> {node}")
    for idx, dependency in enumerate(draft.dependencies, start=1):
        node = f"dependency_{idx}"
        lines.append(f'  {node}[/"{_label("Dependency: " + dependency)}"/]')
        lines.append(f"  start -. depends on .-> {node}")
    for idx, decision in enumerate(draft.open_decisions, start=1):
        node = f"decision_{idx}"
        lines.append(f'  {node}["{_label("Open: " + decision)}"]')
        lines.append(f"  {previous} -. validate .-> {node}")
    return "\n".join(lines)


def _label(value: str) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    return compact.replace('"', "'")
