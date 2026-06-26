"""Schemas for the local process diagram service."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NodeType = Literal["lane", "who", "start", "end", "task", "gateway", "control", "system", "risk", "annotation"]
EdgeType = Literal["sequence", "message", "association", "control"]
DiagramStyle = Literal["plain", "executive"]
DiagramFormat = Literal["cross-functional-flowchart", "process-flow"]


class ProcessChartNodeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = ""
    type: NodeType = "task"
    label: str
    lane: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)


class ProcessChartEdgeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = ""
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    label: str = ""
    type: EdgeType = "sequence"


class ProcessModelInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = "Generated process"
    nodes: list[ProcessChartNodeInput] = Field(default_factory=list)
    edges: list[ProcessChartEdgeInput] = Field(default_factory=list)


class ProcessChartRenderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrative: str = Field(default="", max_length=12000)
    style: DiagramStyle = "plain"
    format: DiagramFormat = "cross-functional-flowchart"
    animation: bool = True
    process_model: ProcessModelInput | None = None


class DiagramPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: int
    y: int


class DiagramNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: NodeType
    label: str
    lane: str = ""
    x: int
    y: int
    width: int
    height: int
    metadata: dict[str, str] = Field(default_factory=dict)


class DiagramEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    label: str = ""
    type: EdgeType = "sequence"
    points: list[DiagramPoint]


class AnimationStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int
    action: Literal["draw_lane", "draw_node", "draw_edge", "highlight_node"]
    target_id: str
    label: str
    narration: str


class ProcessChartRenderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "process-chart.v1"
    chart_id: str
    title: str
    style: DiagramStyle
    format: DiagramFormat
    nodes: list[DiagramNode]
    edges: list[DiagramEdge]
    animation_steps: list[AnimationStep]
    narration_script: list[str]
    warnings: list[str] = Field(default_factory=list)
