# Indicative value hypothesis

This is an **assumption-led, illustrative** value case for the AI Knowledge & Analytics
Assistant — **not verified ROI**. The proof of concept uses synthetic/anonymised data and
local open-source models, so figures below are planning estimates that a future enterprise
deployment with live telemetry would confirm or revise. They show how value *would be
measured*, and how the analytics scorecard supplies the evidence.

## Value drivers

| Driver | What it means | Scorecard signal that evidences it |
|---|---|---|
| **Reduced delivery delay** (largest) | Less time lost when teams/vendors can't get clear, consistent, approved process knowledge | Answer rate, grounded rate, retrieval success — high values mean questions are resolved without waiting on SMEs |
| **Reduced SME clarification** | Fewer interruptions of subject-matter experts for routine questions | Volume of answered questions; "Questions by topic" showing demand absorbed by the assistant |
| **Reduced rework / change requests** | Fewer downstream failures from acting on wrong/missing knowledge | Conflict & duplicate detection (governance); knowledge-gap list shrinking over time |
| **Faster onboarding / vendor alignment** | New joiners and partners reach a consistent understanding faster | Repeated/topic-clustered questions; coverage of onboarding-related topics |

## Indicative P50 portfolio model (illustrative)

Framed as a portfolio year — the assistant reused across a small set of relevant digital
workstreams, not one isolated project. Deliberately cautious about attribution (credited
only with the portion of cost plausibly linked to inconsistent/missing/hard-to-access
knowledge; human validation still required, so SME cost is reduced and redirected, not
eliminated).

| Assumption | P50 value |
|---|---|
| Relevant annual workstreams | ~5 |
| Share materially affected by knowledge friction | ~30% |
| Delay reduced for affected workstreams | ~1 month |
| Gross value / year | ~£714k |
| One-off enterprise capex | ~£1.25m |
| Annual opex | ~£350k |
| Net benefit / year (after opex) | ~£364k |
| Simple payback | ~3.4 years |
| Indicative NPV @ 8% (5y) | ~£200k |
| Indicative IRR | ~14% |

## How the platform substantiates this

The **analytics scorecard** (answer/refusal/grounded rates, average citations, knowledge
gaps, questions-by-topic) and the **governance Knowledge Intelligence** (duplicates,
conflicts, metadata, outdated) are the telemetry that, in a real deployment, would turn
these assumptions into measured outcomes. The **knowledge-gap feedback loop** in particular
quantifies where documentation is missing or weak — the root cause of the delay and rework
the value case targets.

## Implemented value ledger

The current platform now exposes the value case as a governed assumptions ledger at
`src/assistant/value/default_assumptions.json`, with conservative, P50 base and stretch
scenarios. The Analytics page reads those assumptions through `/api/analytics/value` and
calculates gross annual benefit, net annual benefit, simple payback, five-year NPV and IRR.

Operator-entered value observations are recorded as `value_event_recorded` facts in the
append-only analytics event ledger via `/api/analytics/value/events`. These events capture
safe aggregate fields only: driver, process area, scenario, confidence and GBP-equivalent
estimate. They do not store raw prompts, generated answers or source text.

## Caveats
- Illustrative only; no live financial data, contract rates or enterprise telemetry used.
- A production case would add licences, integration, security review, hosting, support,
  SME validation, model evaluation and ongoing governance.
- The PoC demonstrates the **value-calculation method and drivers**, not a final investment case.
