# Process Stress-Test Simulation Method

The process stress-test lab is a deterministic scenario-planning spike over the Process
Registry. It is designed to reveal likely bottlenecks and optimisation themes before a
process is piloted or expanded.

## Inputs

- Structured process records from approved sources.
- Roles, systems, controls, dependencies and business rules.
- Extracted rule ownership and validation/exception wording.

## Scenarios

| Scenario | Purpose |
|---|---|
| Baseline | Reference case for current extracted process structure |
| Volume spike | Higher demand with normal staffing |
| Exception spike | Higher exception/manual handling pressure |
| Staff constraint | Reduced staffing capacity under moderate demand |

## Outputs

- Cycle-time index.
- Queue-pressure score.
- Rework-risk score.
- Bottleneck role and reason.
- Optimisation actions.
- Extracted stress factors.

## Boundary

This is not a production forecast, queueing model or staffing calculator. It is a
scenario-planning indicator from structured registry fields. Any operational decision
requires live volumes, real processing times and process-owner validation.
