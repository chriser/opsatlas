"""FastAPI entrypoint for the independent local process diagram service."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import HTMLResponse

from .engine import DiagramValidationError, render_process_chart, render_svg
from .examples import example_request, examples_gallery_html, get_example, list_examples
from .models import ProcessChartRenderRequest, ProcessChartRenderResponse

app = FastAPI(
    title="Local Process Diagram Service",
    version="0.1.0",
    description="API-driven structured process diagram generator with deterministic local layout.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "process-diagram"}


@app.get("/examples")
def example_gallery() -> HTMLResponse:
    return HTMLResponse(examples_gallery_html())


@app.get("/examples/index")
def example_index() -> list[dict[str, str]]:
    return [
        {"id": example.id, "title": example.title, "summary": example.summary}
        for example in list_examples()
    ]


@app.get("/examples/{example_id}/payload")
def example_payload(example_id: str) -> dict[str, Any]:
    example = get_example(example_id)
    if example is None:
        raise HTTPException(status_code=404, detail=f"Unknown diagram example: {example_id}.")
    return example.payload


@app.get("/examples/{example_id}/json", response_model=ProcessChartRenderResponse)
def example_json(example_id: str) -> ProcessChartRenderResponse:
    example = get_example(example_id)
    if example is None:
        raise HTTPException(status_code=404, detail=f"Unknown diagram example: {example_id}.")
    try:
        return render_process_chart(example_request(example))
    except DiagramValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/examples/{example_id}/svg")
def example_svg(example_id: str) -> Response:
    example = get_example(example_id)
    if example is None:
        raise HTTPException(status_code=404, detail=f"Unknown diagram example: {example_id}.")
    try:
        chart = render_process_chart(example_request(example))
    except DiagramValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(content=render_svg(chart), media_type="image/svg+xml")


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
