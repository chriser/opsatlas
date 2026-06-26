"""HTTP integration with the independent local process diagram service."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

from .maps import ProcessMapDraft, build_process_map
from .models import ProcessRecord
from .router import match_process


def _int_env(name: str, default: int) -> int:
    """Parse an int env var, falling back to default on a missing/invalid value
    (so a bad config value cannot crash app startup)."""
    try:
        return int(os.environ.get(name, "").strip() or default)
    except (TypeError, ValueError):
        return default


_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", ""}


def _ensure_local(base_url: str) -> None:
    """The diagram service is a local sidecar; refuse to call non-loopback hosts so a
    misconfigured/attacker-influenced base URL cannot be used for SSRF."""
    host = (urlparse(base_url).hostname or "").lower()
    if host not in _LOCAL_HOSTS:
        raise ProcessDiagramServiceError(f"Diagram service host '{host}' is not a local address.")


def _truncate(text: str, limit: int = 500) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "…(truncated)"


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


class ProcessDiagramServiceStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_url: str
    running: bool
    started: bool = False
    startable: bool = True
    pid: int | None = None
    message: str
    health: dict[str, Any] = Field(default_factory=dict)
    start_command: list[str] = Field(default_factory=list)
    log_path: str = ""


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
            timeout=_int_env("PROCESS_DIAGRAM_TIMEOUT_SECONDS", 4),
        )

    def render(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json("/process-chart/render", payload)

    def render_svg(self, payload: dict[str, Any]) -> str:
        return self._post_text("/process-chart/render.svg", payload)

    def health(self) -> dict[str, Any]:
        raw = self._get("/health", accept="application/json")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProcessDiagramServiceError("Diagram service health returned invalid JSON.") from exc

    def _get(self, path: str, *, accept: str) -> str:
        _ensure_local(self.base_url)
        req = request.Request(f"{self.base_url}{path}", method="GET", headers={"Accept": accept})
        try:
            with self.opener(req, timeout=self.timeout) as response:
                return response.read().decode("utf-8")
        except HTTPError as exc:
            detail = _truncate(exc.read().decode("utf-8", "replace"))
            raise ProcessDiagramServiceError(f"Diagram service failed ({exc.code}): {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ProcessDiagramServiceError(f"Diagram service unavailable: {exc}") from exc

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        raw = self._post(path, payload, accept="application/json")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProcessDiagramServiceError("Diagram service returned invalid JSON.") from exc

    def _post_text(self, path: str, payload: dict[str, Any]) -> str:
        return self._post(path, payload, accept="image/svg+xml")

    def _post(self, path: str, payload: dict[str, Any], *, accept: str) -> str:
        _ensure_local(self.base_url)
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
            detail = _truncate(exc.read().decode("utf-8", "replace"))
            raise ProcessDiagramServiceError(f"Diagram service failed ({exc.code}): {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ProcessDiagramServiceError(f"Diagram service unavailable: {exc}") from exc


@dataclass
class ProcessDiagramServiceManager:
    client: ProcessDiagramClient
    repo_root: Path
    popen: Callable = subprocess.Popen
    sleeper: Callable[[float], None] = time.sleep

    @classmethod
    def from_env(cls) -> "ProcessDiagramServiceManager":
        return cls(client=ProcessDiagramClient.from_env(), repo_root=_repo_root())

    def status(self) -> ProcessDiagramServiceStatus:
        command, log_path, startable, message = self._start_details()
        try:
            health = self.client.health()
        except ProcessDiagramServiceError as exc:
            return ProcessDiagramServiceStatus(
                service_url=self.client.base_url,
                running=False,
                startable=startable,
                message=message or str(exc),
                start_command=command,
                log_path=str(log_path),
            )
        return ProcessDiagramServiceStatus(
            service_url=self.client.base_url,
            running=True,
            startable=startable,
            message="Diagram service is running.",
            health=health,
            start_command=command,
            log_path=str(log_path),
        )

    def start(self) -> ProcessDiagramServiceStatus:
        current = self.status()
        if current.running:
            return current.model_copy(update={"message": "Diagram service is already running."})
        if not current.startable:
            return current

        log_path = Path(current.log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("ab") as log_file:
            process = self.popen(
                current.start_command,
                cwd=self.repo_root,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

        for _ in range(12):
            self.sleeper(0.35)
            status = self.status()
            if status.running:
                return status.model_copy(
                    update={"started": True, "pid": getattr(process, "pid", None), "message": "Diagram service started."}
                )
        return ProcessDiagramServiceStatus(
            service_url=self.client.base_url,
            running=False,
            started=True,
            pid=getattr(process, "pid", None),
            message="Diagram service start was triggered but health check did not become ready yet.",
            start_command=current.start_command,
            log_path=current.log_path,
        )

    def _start_details(self) -> tuple[list[str], Path, bool, str]:
        parsed = urlparse(self.client.base_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 5300
        if parsed.scheme not in {"http", "https"}:
            return [], self._log_path(), False, "Diagram service URL must use http or https."
        if host not in {"127.0.0.1", "localhost", "::1"}:
            return [], self._log_path(), False, "Only local diagram service URLs can be started from Settings."

        python = os.environ.get("PROCESS_DIAGRAM_PYTHON", sys.executable)
        command = [
            python,
            "-m",
            "uvicorn",
            "services.process_diagram.app:app",
            "--host",
            host,
            "--port",
            str(port),
        ]
        if os.environ.get("PROCESS_DIAGRAM_RELOAD", "0") == "1":
            command.append("--reload")
        return command, self._log_path(), True, "Diagram service is not running."

    def _log_path(self) -> Path:
        return Path(os.environ.get("PROCESS_DIAGRAM_LOG_PATH", str(self.repo_root / "data" / "process-diagram-service.log")))


def process_diagram_service_status() -> ProcessDiagramServiceStatus:
    return ProcessDiagramServiceManager.from_env().status()


def start_process_diagram_service() -> ProcessDiagramServiceStatus:
    return ProcessDiagramServiceManager.from_env().start()


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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
