# Local Process Diagram Service

Independent FastAPI microservice for generating structured business process diagrams locally.

It does not call Lucid, Anam, the main assistant API or any external SaaS. The service takes a
process narrative or structured process model and returns validated diagram JSON, deterministic
layout positions, animation steps, narration script and optional SVG.

## Run Locally

From the repository root:

```bash
.venv/bin/python -m uvicorn services.process_diagram.app:app --host 127.0.0.1 --port 5300 --reload
```

Health check:

```bash
curl http://127.0.0.1:5300/health
```

## JSON Render

```bash
curl -X POST http://127.0.0.1:5300/process-chart/render \
  -H "Content-Type: application/json" \
  -d '{
    "narrative": "The category buyer completes the supplier setup form. Trading Support reviews the request. If details are complete, Finance creates the supplier record.",
    "style": "lucid-business-process",
    "format": "cross-functional-flowchart",
    "animation": true
  }'
```

## SVG Render

```bash
curl -X POST http://127.0.0.1:5300/process-chart/render.svg \
  -H "Content-Type: application/json" \
  -d '{
    "process_model": {
      "title": "Supplier setup",
      "nodes": [
        { "id": "buyer", "type": "lane", "label": "Category Buyer" },
        { "id": "support", "type": "lane", "label": "Trading Support" },
        { "id": "submit_form", "type": "task", "label": "Complete supplier setup form", "lane": "buyer" },
        { "id": "review", "type": "task", "label": "Review submitted form", "lane": "support" },
        { "id": "decision", "type": "gateway", "label": "Details complete?", "lane": "support" }
      ],
      "edges": [
        { "from": "submit_form", "to": "review", "label": "submit" },
        { "from": "review", "to": "decision", "label": "check" }
      ]
    }
  }'
```

## Design Boundary

This MVP is deterministic. A local LLM adapter can later sit before validation, but the validated
diagram JSON remains the source of truth. Rendering is downstream of model validation and layout.

