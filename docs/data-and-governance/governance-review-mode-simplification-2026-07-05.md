# Governance Review Mode Simplification - 2026-07-05

## Decision

OpsAtlas now presents two Governance review modes in the Control Panel:

| Operator mode | API depth | Purpose |
| --- | --- | --- |
| Quick Scan | `fast` | Deterministic hygiene and triage checks. No local LLM adjudication. |
| Full Governance Review | `deep` | Full pairwise reasoning review using deterministic extraction, the internal same-obligation screen and the benchmark-selected adjudicator. |

The previous `Balanced` option is no longer a primary operator mode. It remains
available as an explicit API and benchmark depth for compatibility, and as the
internal same-obligation screening profile used by Full Governance Review.

## Rationale

The model-comparison and holdout benchmark work selected
`qwen2.5:14b-instruct` as the practical Full Governance Review adjudicator, with
`deepseek-r1:8b` retained as the cheaper same-obligation screen. Keeping
Balanced as a visible operator choice created the wrong mental model: it looked
like a separate business decision, but it is now mainly an internal reasoning
stage.

The simplified UI makes the operator decision clearer:

- use Quick Scan for cheap deterministic checks
- use Full Governance Review when the result matters

## Resource Load

The per-section `Throttle Deep` toggles were removed from Internal Source Review
and External Source Review. Reduced-load operation is now treated as runtime
configuration through `KP_COMPLIANCE_DEEP_THROTTLE=1` and the
`KP_COMPLIANCE_DEEP_THROTTLED_LLM_*` environment variables.

This keeps Governance review mode focused on quality level rather than machine
resource management. If a persistent product setting is later required, it
should be implemented as a System-level runtime preference rather than two
separate review-panel toggles.

## Compatibility

The backend still accepts `fast`, `balanced` and `deep` because benchmark scripts
and historical review records depend on those values. New Control Panel runs
only send `fast` or `deep`.

Historical jobs may still display `Balanced (internal)` in status/export output.
That is intentional and avoids misrepresenting the audit trail.

## Branding

The product/platform brand is now OpsAtlas. The Control Panel wordmark displays
`Ops` in white and `Atlas` in magenta. Domain terms such as Knowledge Sources,
knowledge gaps and knowledge intelligence remain unchanged because they describe
specific capabilities rather than the platform brand.
