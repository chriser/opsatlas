"""FastAPI entrypoint for the independent local process diagram service."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response

from .engine import DiagramValidationError, render_process_chart, render_svg
from .models import ProcessChartRenderRequest, ProcessChartRenderResponse

app = FastAPI(
    title="Local Process Diagram Service",
    version="0.1.0",
    description="API-driven structured process diagram generator with deterministic local layout.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "process-diagram"}


@app.post("/process-chart/render", response_model=ProcessChartRenderResponse)
def render_chart(body: ProcessChartRenderRequest) -> ProcessChartRenderResponse:
    try:
        return render_process_chart(body)
    except DiagramValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/process-chart/render.svg")
def render_chart_svg(body: ProcessChartRenderRequest) -> Response:
    try:
        chart = render_process_chart(body)
    except DiagramValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(content=render_svg(chart), media_type="image/svg+xml")

