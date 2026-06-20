# Effort Sizing

Every **new** work item is sized at creation. (Do **not** size Closed tickets.) ADO's estimation fields are numeric, so we use the **Fibonacci sequence** mapped to S/M/L/XL shirt sizes.

## Field to use per work-item type
- **User Story / Bug** → `Story Points`
- **Feature / Epic** → `Effort` (rough roll-up of children)
- **Task** → `Original Estimate` (hours)

## Size scale

| Shirt | Points | Rough scope | ~Focused time | ~Token load (one agent) |
|-------|:------:|-------------|:-------------:|:-----------------------:|
| **XS** | 1 | one-line fix, copy/config tweak | ~15 min | very low |
| **S** | 2 | small fn / one endpoint / UI tweak + tests | ~30–45 min | low |
| **M** | 3 | one module or component + tests | ~1 h | moderate |
| **L** | 5 | self-contained feature slice (backend+tests, or full UI + browser verify) | ~1–1.5 h | notable |
| **XL** | 8 | multi-part; **prefer to split** into stories | ~2–3 h | high |
| **XXL** | 13 | epic-ish; **must** be broken into stories before work | — | — |

## Capacity (the ~5h token window per agent)
A focused ~5-hour agent window is roughly **~25 points** of throughput, i.e. about:
- **~5 L** tickets, or **~8 M**, or **~12 S** — minus overhead for UAT fixes, reviews and coordination.

Treat this as a planning yardstick, not a guarantee: verification-heavy UI work and anything needing a live model, integration or approved-environment access runs slower; pure offline backend modules run faster. Re-estimate if a ticket grows past **L** — split it.

## Rules
1. Size at creation; an unsized New ticket is not ready to start.
2. Anything **XL or larger** should be decomposed into L-or-smaller stories.
3. Sizes are relative effort, not a commitment — adjust if scope changes (note why).

_Linked: [Definition of Done](/Ways-of-Working/Definition-of-Done) · [Agent Collaboration](/Ways-of-Working/Agent-Collaboration)_
