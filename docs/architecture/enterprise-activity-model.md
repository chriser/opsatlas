# Enterprise Activity Model

Last updated: 2026-07-07

## Purpose

The Enterprise Activity Model (EAM) replaces the earlier Operating Model page
with a living, ontology-backed canvas. Its role is to show what operating
knowledge has been evidenced by approved sources, where that knowledge sits
across business domains and value-chain stages, and where gaps, overlaps or
clashes need review.

The EAM is deterministic. It does not ask an LLM to invent an operating model.
It projects approved ontology objects and links into a visual analytics layer.

## Projection Pipeline

1. Approved source documents are ingested and synced into ontology objects.
2. Process objects are classified against the editable EAM taxonomy in
   `config/eam_taxonomy.json`.
3. `build_eam_model` projects process nodes into domain x value-chain cells.
4. Role, system and control links are rolled up into entity registries.
5. Shared systems and controls create relationship edges.
6. Deterministic findings identify coverage gaps, overlaps and clashes.
7. SVG renderers produce five canvas views for the Control Panel.

## Five Views

| View | Purpose | Renderer |
|---|---|---|
| Activity | Domain x value-chain map with clustered process nodes and shared evidence links. | `src/assistant/eam/render_activity.py` |
| Accountability | Role/owner swimlanes showing process accountability evidence. | `src/assistant/eam/render_accountability.py` |
| Risk Heat | Heat matrix combining coverage gaps with gap, overlap and clash signals. | `src/assistant/eam/render_risk_heat.py` |
| Relationship | Process nodes connected to role, system and control entities so shared dependencies, ownership concentration and cross-process coupling are visible. It is not a process-flow view. | `src/assistant/eam/render_relationship.py` |
| Digital System Landscape | Process rows projected across business system-layer columns. Selecting a process highlights its named systems and animates the populated layer sequence. | `src/assistant/eam/render_system_landscape.py` |

## Digital System Landscape

The Digital System Landscape is an EAM lens over the same ontology evidence. It
uses `process_uses_system` links, then deterministically classifies system names
and process context into system-layer columns:

1. Payments & Forecourt
2. Sales Execution
3. Store Operations
4. Central Store Administration
5. Store Inventory Management
6. Convenience Head Office
7. Invoice Matching
8. Finance
9. Forecasting & Replenishment
10. Ranging & Category Management
11. Data & Analytics
12. Integration & Operational Reports

This is deliberately a visual operating-landscape view rather than a new source
of truth. If a process appears thin or empty in a layer, that means the approved
ontology evidence does not yet contain enough named system links for that area.

## Scale Controls

The 50+ process target is handled through bounded deterministic behaviour:

- per-cell Activity view clustering with `+N more`;
- capped relationship edges to avoid hairball renderings;
- explicit finding caps and pairwise-finding caps;
- ranked findings by severity, type, affected node breadth and entity breadth;
- a 60-process synthetic fixture in `tests/test_eam_scale.py`.

## Provenance

The page hero shows source count and generation time. Process-node SVG titles
include source references for hover provenance. The Control Panel keeps the
Activity canvas as the primary evidence surface and retains the entity registry
below it so users can see the breadth of roles, systems and controls without
duplicating the same node counts in separate summary panels.

The model is read-through. It is rebuilt from the current ontology state on
each API request, so newly approved/synced process evidence appears on the next
load without restarting the app.

## Value-Chain Taxonomy

The EAM column taxonomy is derived from APQC Retail Process Classification
Framework and SCOR value-chain concepts. The active column set is:

1. Plan & Govern
2. Configure
3. Source & Replenish
4. Receive & Control
5. Sell & Operate
6. Reconcile & Close
7. Assure & Improve

The ontology store schema is unaffected by this taxonomy change. The store
continues to hold governed objects and links; only the projection layer
re-derives which EAM cell each process node lands in. Because `/api/eam/model`
is read-through rather than cached, taxonomy changes invalidate the projection
implicitly on the next API request.

Domain rows remain capability nouns, while columns are value-chain verbs. Three
current domain rows overlap with the new value-chain columns and should be
reviewed with the product owner before any domain deletion: Forecasting and
Replenishment, GRIR and Invoice Reconciliation, and Receiving, Returns and
Recalls. They are retained for now so existing evidence remains visible.

## Validation

`VAL-EAM-001` covers the EAM validation method:

- deterministic projection over the governed ontology;
- coverage, gap, overlap and clash metrics;
- source provenance;
- compact and expanded Activity-card rendering;
- 60-process render performance;
- dynamic update after ontology state changes.

The current test evidence is:

- `tests/test_eam_model.py`;
- `tests/test_eam_api.py`;
- `tests/test_eam_scale.py`;
- `tests/test_eam_dynamic_update.py`;
- renderer tests for all five SVG views.

## Boundaries

The EAM is evidence-breadth and visual analytics. It is not proof that the live
enterprise operating model is complete, compliant or risk-free. It is designed
to help an operator see where approved knowledge is strong, weak or missing.

The Process Stress Lab remains parked as a deterministic diagnostic. Its scores
are useful for scenario explanation, but they should not be treated as grounded
operating-model evidence in the final submission.
