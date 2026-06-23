"""HTTP integration with the independent local process diagram service."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib import request
from urllib.error import HTTPError, URLError

from pydantic import BaseModel, ConfigDict, Field

from .maps import ProcessMapDraft, build_process_map
from .models import ProcessRecord
from .router import match_process


class DiagramCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_title: str = ""
    heading: str = ""
    ordinal: int = 0


class ProcessDiagramResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(default="", max_length=1200)
    citations: list[DiagramCitation] = Field(default_factory=list)


class ProcessDiagramContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    message: str
    process_id: str = ""
    process_name: str = ""
    source_title: str = ""
    service_url: str = ""
    chart: dict[str, Any] | None = None
    svg: str = ""


class ProcessDiagramServiceError(RuntimeError):
    """Raised when the local diagram service cannot render a chart."""


@dataclass
class ProcessDiagramClient:
    base_url: str = "http://127.0.0.1:5300"
    timeout: int = 4
    opener: Callable = request.urlopen

    @classmethod
    def from_env(cls) -> "ProcessDiagramClient":
        return cls(
            base_url=os.environ.get("PROCESS_DIAGRAM_SERVICE_URL", "http://127.0.0.1:5300").rstrip("/"),
            timeout=int(os.environ.get("PROCESS_DIAGRAM_TIMEOUT_SECONDS", "4")),
        )

    def render(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json("/process-chart/render", payload)

    def render_svg(self, payload: dict[str, Any]) -> str:
        return self._post_text("/process-chart/render.svg", payload)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        raw = self._post(path, payload, accept="application/json")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProcessDiagramServiceError("Diagram service returned invalid JSON.") from exc

    def _post_text(self, path: str, payload: dict[str, Any]) -> str:
        return self._post(path, payload, accept="image/svg+xml")

    def _post(self, path: str, payload: dict[str, Any], *, accept: str) -> str:
        req = request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "Accept": accept},
        )
        try:
            with self.opener(req, timeout=self.timeout) as response:
                return response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise ProcessDiagramServiceError(f"Diagram service failed ({exc.code}): {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ProcessDiagramServiceError(f"Diagram service unavailable: {exc}") from exc


def resolve_process_diagram(
    body: ProcessDiagramResolveRequest,
    records: list[ProcessRecord],
    client: ProcessDiagramClient,
) -> ProcessDiagramContext:
    record = _match_record(body, records)
    if record is None:
        return ProcessDiagramContext(
            status="empty",
            message="No related process map was identified for this answer.",
            service_url=client.base_url,
        )

    draft = build_process_map(record)
    payload = build_diagram_payload(draft)
    try:
        chart = client.render(payload)
        svg = client.render_svg(payload)
    except ProcessDiagramServiceError as exc:
        return ProcessDiagramContext(
            status="unavailable",
            message=str(exc),
            process_id=record.id,
            process_name=record.name,
            source_title=record.source_title,
            service_url=client.base_url,
        )
    return ProcessDiagramContext(
        status="available",
        message="Related process diagram rendered by the local diagram service.",
        process_id=record.id,
        process_name=record.name,
        source_title=record.source_title,
        service_url=client.base_url,
        chart=chart,
        svg=svg,
    )


def build_diagram_payload(draft: ProcessMapDraft) -> dict[str, Any]:
    lanes = _lanes_for(draft)
    nodes: list[dict[str, Any]] = [
        {"id": lane_id, "type": "lane", "label": label}
        for lane_id, label in lanes
    ]
    step_lane_by_id: dict[str, str] = {}
    default_lane = lanes[0][0] if lanes else "process"
    for step in draft.steps:
        lane = _safe_id(step.owner) if step.owner else default_lane
        if lane not in {item[0] for item in lanes}:
            lane = default_lane
        step_lane_by_id[step.id] = lane
        nodes.append({
            "id": step.id,
            "type": "gateway" if _looks_like_gateway(step.label) else "task",
            "label": step.label,
            "lane": lane,
            "metadata": {
                "topic": step.topic,
                "confidence": step.confidence,
            },
        })

    edges = [
        {"from": edge.source, "to": edge.target, "label": edge.label or "next"}
        for edge in draft.edges
    ]
    anchor = draft.steps[0].id if draft.steps else ""
    if draft.controls:
        nodes.append({"id": "controls", "type": "lane", "label": "Controls"})
        for index, control in enumerate(draft.controls[:4], start=1):
            node_id = f"control_{index}"
            nodes.append({"id": node_id, "type": "control", "label": control, "lane": "controls"})
            if anchor:
                edges.append({"from": node_id, "to": anchor, "label": "governs", "type": "control"})
    if draft.systems:
        nodes.append({"id": "systems", "type": "lane", "label": "Systems"})
        for index, system in enumerate(draft.systems[:4], start=1):
            node_id = f"system_{index}"
            nodes.append({"id": node_id, "type": "system", "label": system, "lane": "systems"})
            if anchor:
                edges.append({"from": node_id, "to": anchor, "label": "supports", "type": "association"})

    return {
        "style": "lucid-business-process",
        "format": "cross-functional-flowchart",
        "animation": True,
        "process_model": {
            "title": draft.name,
            "nodes": nodes,
            "edges": edges,
        },
    }


def _match_record(body: ProcessDiagramResolveRequest, records: list[ProcessRecord]) -> ProcessRecord | None:
    citation_text = " ".join(
        " ".join([citation.source_title, citation.heading])
        for citation in body.citations
    )
    query = " ".join([body.question, citation_text]).strip()
    matched = match_process(query, records)
    if matched is not None:
        return matched
    source_ids = {citation.source_id for citation in body.citations}
    return next((record for record in records if record.id in source_ids or record.source_id in source_ids), None)


def _lanes_for(draft: ProcessMapDraft) -> list[tuple[str, str]]:
    owners = []
    for step in draft.steps:
        if step.owner and step.owner not in owners:
            owners.append(step.owner)
    if not owners:
        owners = draft.roles[:4] or ["Process"]
    return [(_safe_id(owner), owner) for owner in owners]


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "process"


def _looks_like_gateway(label: str) -> bool:
    return bool(re.search(r"\?|\bif\b|\bwhether\b|\bcomplete\b|\bvalid\b|\bpass\b", label, re.IGNORECASE))

