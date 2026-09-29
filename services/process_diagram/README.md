# Local Process Diagram Service

Independent FastAPI microservice for generating structured business process diagrams locally.

It does not call external diagram tools, Anam, the main assistant API or any SaaS. The service takes a
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

Visual example gallery:

```text
http://127.0.0.1:5300/examples
```

Direct sample outputs:

```text
http://127.0.0.1:5300/examples/supplier-setup/svg
http://127.0.0.1:5300/examples/article-tax-handling/svg
http://127.0.0.1:5300/examples/knowledge-governance/svg
```

## The process map notation

Every process map uses one notation, the organisation's shape legend (an event-driven process chain). This was the
Human's decision on 29 September 2026. The service applies it to every model it draws (`layout.py`).

Everything but a connector is a rounded box in its legend colour; connectors are circles. The Human chose the
simpler boxes of the earlier maps, in the legend's colours, on 29 September 2026.

| Outline | Node type | Meaning |
|---|---|---|
| Pink | `start`, `end`, `event` | A trigger for, or outcome of, a process step. Each path after a split starts with its condition as an event |
| Green | `task` | A process step |
| Dark blue | `automated` | A step a system does on its own |
| Grey | `interface` | Another process this one hands over to; `metadata.reference` is written above it |
| Yellow | `who` | A role performing the step. Several may attach to one step; someone outside the organisation (a customer, a supplier, or `metadata.external = "true"`) is dashed |
| Light blue | `system` | The application system supporting the step. A manual step shows "Non-system activity" |
| Red | `control` | A control performed at the step |
| Circle | `gateway` | `metadata.gateway`: `xor` (only one path followed, a cross), `and` (all paths, ∧) or `or` (shown as ANY: any number of paths, ∨) |

Rules the service applies:
- A split's labelled paths each start with an event carrying the label.
- Where paths meet, a join of the same kind as their split is added.
- A task with no system gets "Non-system activity".
- Roles and systems attach to a step through any edge between them.
- Each path has its own column: a split's paths sit side by side under it and meet at the join below them.
- A path that goes straight from a split to its join keeps a column of its own.
- A link back to an earlier step leaves from the bottom and runs up beside everything it passes, never across a box.
- A connector (`gateway`) needs no label.

The gallery's `age-restricted-sale` example shows all of it, on a made-up shop sale.

## JSON Render

```bash
curl -X POST http://127.0.0.1:5300/process-chart/render \
  -H "Content-Type: application/json" \
  -d '{
    "narrative": "The category buyer completes the supplier setup form. Trading Support reviews the request. If details are complete, Finance creates the supplier record.",
    "style": "plain",
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
