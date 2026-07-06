# Enterprise Activity Model

Last updated: 2026-07-06

## Purpose

The Enterprise Activity Model (EAM) replaces the earlier Operating Model page
with a living, ontology-backed canvas. Its role is to show what operating
knowledge has been evidenced by approved sources, where that knowledge sits
across business domains and lifecycle stages, and where gaps, overlaps or
clashes need review.

The EAM is deterministic. It does not ask an LLM to invent an operating model.
It projects approved ontology objects and links into a visual analytics layer.

## Projection Pipeline

1. Approved source documents are ingested and synced into ontology objects.
2. Process objects are classified against the editable EAM taxonomy in
   `config/eam_taxonomy.json`.
3. `build_eam_model` projects process nodes into domain x lifecycle cells.
4. Role, system and control links are rolled up into entity registries.
5. Shared systems and controls create relationship edges.
6. Deterministic findings identify coverage gaps, overlaps and clashes.
7. SVG renderers produce four canvas views for the Control Panel.

## Four Views

| View | Purpose | Renderer |
|---|---|---|
| Activity | Domain x lifecycle map with clustered process nodes and shared evidence links. | `src/assistant/eam/render_activity.py` |
| Accountability | Role/owner swimlanes showing process accountability evidence. | `src/assistant/eam/render_accountability.py` |
| Risk Heat | Heat matrix combining coverage gaps with gap, overlap and clash signals. | `src/assistant/eam/render_risk_heat.py` |
| Relationship | Process nodes connected to role, system and control entities. | `src/assistant/eam/render_relationship.py` |

## Scale Controls

The 50+ process target is handled through bounded deterministic behaviour:

- per-cell Activity view clustering with `+N more`;
- capped relationship edges to avoid hairball renderings;
- explicit finding caps and pairwise-finding caps;
- ranked findings by severity, type, affected node breadth and entity breadth;
- a 60-process synthetic fixture in `tests/test_eam_scale.py`.

## Provenance

The page hero shows source count and generation time. Process-node SVG titles
include source references for hover provenance, and the process evidence table
shows the underlying process node classification, evidence score and linked
role/system/control counts.

The model is read-through. It is rebuilt from the current ontology state on
each API request, so newly approved/synced process evidence appears on the next
load without restarting the app.

## Validation

`VAL-EAM-001` covers the EAM validation method:

- deterministic projection over the governed ontology;
- coverage, gap, overlap and clash metrics;
- source provenance;
- 60-process render performance;
- dynamic update after ontology state changes.

The current test evidence is:

- `tests/test_eam_model.py`;
- `tests/test_eam_api.py`;
- `tests/test_eam_scale.py`;
- `tests/test_eam_dynamic_update.py`;
- renderer tests for all four SVG views.

## Boundaries

The EAM is evidence-breadth and visual analytics. It is not proof that the live
enterprise operating model is complete, compliant or risk-free. It is designed
to help an operator see where approved knowledge is strong, weak or missing.

The Process Stress Lab remains parked as a deterministic diagnostic. Its scores
are useful for scenario explanation, but they should not be treated as grounded
operating-model evidence in the final submission.
