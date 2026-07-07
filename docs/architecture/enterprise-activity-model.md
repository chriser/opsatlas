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

## Entity Reconciliation

Ontology rebuild now applies a deterministic reconciliation step before role,
system and control entities are written to the graph. The intent is to prevent
approved packs from creating several objects for the same operating entity just
because the wording varies.

Current reconciliation is intentionally conservative:

- system aliases such as `POS`, `point-of-sale` and downstream retail
  point-of-sale wording resolve to the canonical `Point of Sale` entity;
- common system families such as operational master data, integration,
  replenishment, finance, reporting, article lists and payments/forecourt are
  normalised where the source wording clearly points at the same platform
  class;
- role labels with count suffixes such as `Compliance Manager (5)` and
  `Compliance Manager (2)` resolve to one canonical role while preserving the
  observed aliases;
- ordinary role distinctions such as `Finance approver` and `Finance owner`
  are not merged unless the wording is a clear alias.

The ontology stores the canonical display name and an `aliases` list so the
Control Panel can show one entity while retaining source provenance. This is a
deterministic production-safe baseline, not a free-form LLM merge. Future
entity reconciliation can add a human-approved review queue for uncertain
duplicates.

## Five Views

| View | Purpose | Renderer |
|---|---|---|
| Activity | Domain x value-chain map with clustered process nodes. Connections are hidden by default; selecting a card reveals only its active connections and connected elements, while the toolbar can reveal all shared-system/control links. | `src/assistant/eam/render_activity.py` |
| Accountability | Role/owner swimlanes showing process accountability evidence. | `src/assistant/eam/render_accountability.py` |
| Risk Heat | Heat matrix combining coverage gaps with gap, overlap and clash signals. | `src/assistant/eam/render_risk_heat.py` |
| Relationship | Process nodes connected to role, system and control entities so shared dependencies, ownership concentration and cross-process coupling are visible. It is not a process-flow view. | `src/assistant/eam/render_relationship.py` |
| Digital System Landscape | Process selector plus a vertical system-layer landscape. Systems are arranged left-to-right for the selected process, with numbered hand-off steps and one sequenced data-package animation. The toolbar can reveal all known process flows. | `src/assistant/eam/render_system_landscape.py` |

## Digital System Landscape

The Digital System Landscape is an EAM lens over the same ontology evidence. It
uses `process_uses_system` links, then deterministically classifies canonical
system names and process context into vertical system-layer rows:

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

The current layout keeps the process selector as an independent left rail.
System layers are stacked vertically, while systems are positioned left-to-right
according to the selected process sequence. This makes the selected path read
as a start-to-end operating flow rather than as a static matrix. The SVG is
rendered at native dimensions with layer rows above 120px high so the default
view opens as a scrollable large canvas rather than shrinking the full
landscape into a tiny preview.

When a canonical system maps to several adjacent layers, such as `Point of
Sale` spanning Sales Execution, Store Operations and Central Store
Administration, the renderer draws one vertical system segment across those
layer rows. When the matched layers are non-adjacent, such as a payment
contract touching Payments & Forecourt, Convenience Head Office and Finance,
the renderer draws separate same-column segments only in the evidenced layers
instead of bridging every row in between. A system therefore exists once as a
canonical system in the ordered flow, but its visual footprint does not imply
unsupported layer coverage.

Process rows are a selector rail: choosing a process filters the landscape to
the systems participating in that process and draws an ordered data-package
path through the system sequence. The selected flow shows numbered hand-off
steps and one moving packet that travels from start to end before repeating.
The packet label is inferred deterministically from process wording, such as
`Supplier setup data`, `Invoice matching data` or `Article master data`. Long
packet labels wrap inside their label box.

The `Reveal all connections` control shows all known process flows as faint
context lines without duplicating system nodes. `Clear focus` removes the
selected process from the System Landscape lens.

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

Digital System Landscape payload labels and sequence are deterministic
projections from current ontology evidence. They are useful operating prompts,
but they are not yet a governed integration specification. A future ontology
extension should add explicit `process_moves_data_object` and
`system_hands_off_to_system` relationships if the platform needs audited
payload names, source/target systems and exact sequence.

The Process Stress Lab remains parked as a deterministic diagnostic. Its scores
are useful for scenario explanation, but they should not be treated as grounded
operating-model evidence in the final submission.
