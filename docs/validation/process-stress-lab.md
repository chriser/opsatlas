# Process Stress Lab Learning Overview

Date: 2026-06-26

This overview translates the Process Stress Lab stories and delivered UI into plain-language learning content. It is based on ADO items #797, #798, #802, #805, #924-#929, #938-#940, #953, #1008 and #1009, plus the implemented `/api/process/stress-test` page behaviour.

Related item #955 covers process gap, overlap and clash visualisation. That is adjacent process-analytics functionality, but it is not part of the dedicated Process Stress Lab page described here.

## Page Purpose

The Process Stress Lab is a scenario-planning page. Its job is to take documented process records and ask: "What parts of this process might come under pressure if volume increases, exceptions rise, or staffing is constrained?"

It does not predict the future. It does not calculate real staffing levels. It does not replace process-owner judgement. It gives a structured way to spot likely pressure points before a process is piloted, expanded or changed.

In layman terms, it is like a flight simulator for business process records. It lets the team apply a few controlled "what if" conditions and see which roles, hand-offs, dependencies or validation steps look most fragile.

## What The Page Uses

The page uses approved Process Registry records. These records are derived from approved sources and contain structured signals such as:

- roles involved in the process
- systems touched by the process
- dependencies between steps or teams
- controls and checks
- business rules
- hand-offs between roles
- exception, manual handling or validation wording

The stress lab turns those signals into a deterministic simulation. "Deterministic" means the same input records produce the same output scores each time. That is useful for review and UAT because people can compare results without random variation.

## What The Page Is Not

The page is not:

- a production forecast
- a staffing calculator
- a queueing model based on live operational volumes
- proof that a process will fail
- proof that a recommended change will save money

The safest wording is: "This is a scenario-planning indicator from documented process records. It highlights areas to review with process owners."

## Top Summary Cards

The first row gives a quick read of the whole stress-test run.

| Box | What It Means | Example Interpretation |
|---|---|---|
| Processes | Number of approved process records included in the stress test. | "3" means the lab found three process records to test. |
| Scenarios | Number of what-if scenarios applied to each process. | Usually "4": baseline, volume spike, exception spike and staff constraint. |
| High-risk rows | Number of process-scenario combinations where queue or rework risk is 70 or higher. | If this says "5", five rows need review because either waiting pressure or rework pressure looks elevated. |
| Average queue | Average queue-pressure score across all result rows. | A score of 42 means moderate overall waiting pressure; 75 means queueing needs attention. |
| Average rework | Average rework-risk score across all result rows. | A score of 80 means the records contain enough exception, validation or dependency signals to suggest rework risk under stress. |

The threshold used by the UI is simple: scores below 70 are shown as generally stable, while scores of 70 or above are flagged for review.

## Highest-Risk Signal

This panel shows the strongest pressure point found across every process and scenario.

It answers: "If we only had time to discuss one risk first, which one should it be?"

The box shows:

- the process name
- the scenario that caused the strongest signal
- the bottleneck reason
- queue score
- rework score
- cycle index
- recommended actions

Example:

> Supplier setup under Staff constraint shows Queue 91, Rework 82 and Cycle index 132.4. The bottleneck reason says staffing constraint magnifies the support team and hand-off load.

In plain English, this means the process may be manageable normally, but if staffing drops while work continues to arrive, the support team or dominant role could become a choke point.

## Metric Guide

The Metric Guide explains the scoring language used across the page.

### Cycle Time Index

This is a relative pressure number, not minutes or hours.

It increases when the process has more roles, systems, dependencies, hand-offs, validation gates, rules, higher demand, higher exception rate or lower staffing.

Useful explanation:

> Cycle index is a relative measure of how heavy the process looks under a scenario. A higher number means the process has more structural pressure, but it is not a real elapsed-time forecast.

Example:

- Cycle index 45: comparatively light process under the scenario.
- Cycle index 120: heavier process that may need process-owner review.

### Queue Pressure Score

This is a 0-100 indicator of waiting or backlog pressure.

It is influenced by structural complexity, dependencies, hand-offs and scenario pressure. A high queue score suggests work might pile up, wait for another role, or get delayed by dependent steps.

Useful explanation:

> Queue pressure tells us where work might start waiting. It is a review signal for hand-offs, sequencing and dependencies.

Example:

If supplier setup has several hand-offs and depends on finance validation and supplier data, a volume spike may produce a high queue score because more work is entering a process with several waiting points.

### Rework Risk Score

This is a 0-100 indicator of likely correction, rechecking or exception handling pressure.

It is influenced by wording such as manual, exception, missing, unclear, fail, reject or requires validation, plus validation gates, dependencies and staffing pressure.

Useful explanation:

> Rework risk tells us where the process might need things to be corrected, repeated, clarified or manually handled.

Example:

If a process says "manual exceptions require approval" and "requests fail closed until validation is complete", the rework score may rise because the record contains exception and validation signals.

### Boundary

The boundary statement is part of the page on purpose. It keeps the lab honest.

Useful explanation:

> These results are scenario-planning indicators only. They help us decide what to review, not what will definitely happen.

## Scenario Controls

The Scenario Controls let the user filter the result matrix by one what-if case or view all scenarios together.

Each scenario card shows three parameters:

- demand multiplier
- exception rate
- staffing factor

### Baseline

Baseline is the reference case.

- Demand: x1.0
- Exception rate: 8%
- Staffing: x1.0

Plain-language meaning:

> This is the normal comparison point. It shows how the process looks using the current extracted structure without applying extra stress.

### Volume Spike

Volume spike tests higher demand with normal staffing.

- Demand: x1.6
- Exception rate: 10%
- Staffing: x1.0

Plain-language meaning:

> What if more work arrives, but the same people and structure handle it?

Example:

If onboarding requests increase after a supplier campaign, the process might still have the same approval gates and hand-offs, so waiting pressure may rise.

### Exception Spike

Exception spike tests more manual or unusual cases.

- Demand: x1.1
- Exception rate: 25%
- Staffing: x1.0

Plain-language meaning:

> What if the process receives more messy, incomplete or non-standard cases?

Example:

If many supplier requests arrive with missing evidence or unusual payment setup, the team may spend more time clarifying and rechecking.

### Staff Constraint

Staff constraint tests reduced staffing capacity under moderate demand.

- Demand: x1.2
- Exception rate: 12%
- Staffing: x0.7

Plain-language meaning:

> What if work is slightly higher than normal, but available capacity is lower?

Example:

If one reviewer is unavailable and volume is still elevated, the dominant role may become a bottleneck.

## Stress Result Matrix

The matrix is the detailed table. It is sorted so the highest combined queue, rework and cycle-time pressure appears first.

| Column | What It Means | How To Explain It |
|---|---|---|
| Process | The documented process being tested. | "This row is about supplier setup." |
| Scenario | The what-if condition applied. | "This is the staff constraint version of the supplier setup process." |
| Cycle | Relative cycle-time pressure. | "This is heavier than the baseline, but it is not minutes or hours." |
| Queue | Waiting/backlog pressure score from 0-100. | "High queue means work may wait between steps or roles." |
| Rework | Correction or exception-handling pressure score from 0-100. | "High rework means the process may need more clarification, checking or manual handling." |
| Bottleneck | The role most likely to become the pressure point. | "The support team appears most exposed because it owns several rules." |
| Recommended action | Practical review prompt generated from the signals. | "Review hand-offs and dependency sequencing before increasing volume." |

## Recommended Actions

Recommended actions are prompts, not instructions.

The system generates them from the shape of the process record and the scenario scores. Common examples include:

- Review hand-offs and dependency sequencing before increasing volume.
- Clarify exception handling and validation ownership before go-live.
- Check whether system touchpoints can be consolidated or automated.
- Define explicit validation entry/exit criteria and evidence retention.
- Monitor during pilot when no elevated optimisation action is detected.

Good stakeholder wording:

> The stress lab is not telling us exactly what to change. It is telling us which conversation to have first.

## Rule-Set Diagnostics

Rule-set diagnostics explain why a process received its scores before scenario pressure was applied.

Each card represents one process and shows the extracted signals used by the simulator.

### Source Title

This shows the approved source or process record behind the diagnostic card.

Plain-language meaning:

> This tells us where the process information came from.

### Roles

Number of roles found in the process.

Plain-language meaning:

> More roles can mean more coordination and more potential waiting points.

Example:

Requester, support team, finance owner and approver equals four roles.

### Systems

Number of systems touched by the process.

Plain-language meaning:

> More systems can mean more switching, rekeying, integration risk or manual checking.

Example:

A request portal, document repository and finance system equals three systems.

### Dependencies

Number of dependent items or conditions.

Plain-language meaning:

> Dependencies are things the process needs before it can move forward.

Example:

Supplier data and finance validation are dependencies. If either is missing, work may wait.

### Controls

Number of controls or checks.

Plain-language meaning:

> Controls are safeguards, but each one can also add a gate that work must pass through.

Example:

Credit check and approval gate are controls.

### Validation Gates

Number of rules or business rules mentioning checks, approvals, validation or gates.

Plain-language meaning:

> Validation gates are formal points where someone or something must confirm the work is acceptable.

Example:

"Support validates mandatory evidence" and "manual exception requires approval" both contribute validation pressure.

### Hand-Offs

Number of role changes implied by the process.

Plain-language meaning:

> Hand-offs are places where work moves from one role or team to another. More hand-offs can create more waiting and coordination risk.

Example:

Requester to support team to finance owner to approver creates several hand-offs.

### Bottleneck Candidate

The role that appears most often in the structured rules.

Plain-language meaning:

> This is the role most likely to feel pressure first because the documented process gives it the largest share of work or responsibility.

### Stress Factor Chips

These chips are plain-language reasons the process may be vulnerable. The current factors include:

- Multiple role hand-offs
- Multiple systems
- Several dependencies
- Exception/manual wording
- Multiple validation gates
- Rules without clear owner
- No elevated stress factor from registry fields

Example:

If a process shows "Multiple systems", "Several dependencies" and "Exception/manual wording", the learning takeaway is:

> This process may need review because it crosses systems, depends on other information, and contains manual or exception handling language.

## Example Walkthrough

Imagine the Process Stress Lab is showing a Supplier Setup process.

The Rule-Set Diagnostics might show:

- four roles: requester, support team, finance owner, approver
- three systems: request portal, document repository, finance system
- two dependencies: finance validation and supplier data
- two controls: credit check and approval gate
- three hand-offs
- exception wording around manual exceptions and validation

Under Baseline, the process might look manageable. Under Volume Spike, queue pressure may increase because more supplier requests are entering the same hand-off chain. Under Exception Spike, rework risk may increase because more requests are incomplete or unusual. Under Staff Constraint, both queue and rework may rise because fewer people are available to handle validation, exceptions and hand-offs.

A useful explanation to a non-technical stakeholder would be:

> The lab is showing that supplier setup is not necessarily broken, but it has several points that could come under pressure: multiple roles, multiple systems, validation gates and exception handling. Before increasing volume, we should review ownership, hand-offs and evidence requirements with the process owner.

## How To Read The Page In A Review Session

1. Start with the top cards to understand the size of the run.
2. Check Highest-risk signal to decide the first process/scenario to discuss.
3. Use Metric Guide to explain what the numbers mean and what they do not mean.
4. Use Scenario Controls to compare normal pressure with volume, exception and staffing stress.
5. Use the Stress Result Matrix to see which process rows need review.
6. Use Rule-Set Diagnostics to explain why the page flagged a process.
7. End with recommended actions as review prompts, not automatic decisions.

## Simple Stakeholder Script

> The Process Stress Lab takes approved process records and runs a few controlled what-if scenarios. It looks for pressure from hand-offs, roles, systems, dependencies, validation gates and exception wording. The scores are not forecasts; they are indicators that help us decide where to review the process first. A high queue score means work may wait. A high rework score means cases may need correction, clarification or manual handling. The recommended actions are prompts for process-owner discussion.
