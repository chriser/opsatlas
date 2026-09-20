# Evaluation and delivery gates

**All performance and experience numbers below are proposed acceptance targets, not measured results.** The Human has accepted G0 and confirmed a Mac Studio M4 Max with 64 GB unified memory. Isolated synthetic E1 implementation is authorised; model/voice selection at G1 follows measured evidence. Real pilot participants and organisational process remain unconfirmed.

## Delivery sequence

| Gate / slice | Deliverable | Exit evidence and decision owner |
|---|---|---|
| E0 / G0 — research and agreement | This brief, current Atlas audit, source-based research, proposed contracts and linked backlog | Human records first channel, hardware envelope, synthetic process, service boundary, data policy and permission to start E1 |
| E1a / G1 — isolated speech audition | Repeatable local ASR/TTS/turn-control comparison and resource measurements | Human picks voice and acceptable latency/comfort trade-off; no Atlas mutation |
| E1b / G2 — interview proof | One browser interview, evidence-aware clarification, corrections and staged packet | Demonstration meets agreed conversation and factual criteria; disable flag and Atlas remains intact |
| E2 / G3 — governed knowledge loop | Deferred review, second-owner case, pending import, explicit approval and durable publication | No unapproved evidence leakage; idempotent recovery, source-change rejection and rebuild survival; Human accepts |
| E3 / G4 — pilot readiness | Identity/access, retention, real-data authority and load/recovery controls | Organisational owner approves deployment/data conditions; small pilot produces measured feedback |
| E4 / later decision | Meeting and hardware feasibility | Separate evidence/consent/platform approval and a new scope decision; not on E1 critical path |

Indicative focused engineering ranges after G0: 2–4 days for an isolated audition, 4–7 for the staged interview path, 4–8 for governed publication/review, then 3–5 for hardening plus participant scheduling. These are planning ranges with high uncertainty, not dates or commitments. Hardware setup, licensing review, weak model performance and Human review capacity can dominate. Stories carry relative estimates; discovery should replace these ranges with observed throughput.

The shortest useful demonstration is E1's staged capture. It must not be described as complete Atlas knowledge enrichment until E2 proves the approval and publication loop.

## G1.5 amendment — accepted 20 September 2026

The conversational core precedes Atlas embedding. Gate #1590 requires ten unscripted headset minutes without buttons or per-turn confirmation, median naturalness and pace ≥4/5, measured p50 ≤1.5 seconds, and zero fabricated spoken facts. S114 records browser milestones and distributions before optimisation; S119 adds development/holdout personas and a Human rating sheet. Every iteration reports sample counts, timing definitions, failure counts and rubric availability. Missing endpoints or holdout scores are reported as unmeasured, never as a pass. See [current delivery plan](19-conversational-core-delivery.md).

## Evaluation design

Create a versioned synthetic dataset before tuning: six process scenarios, with no-prior-evidence, consistent process, genuine same-scope conflict, valid regional/date variant, missing hand-off owner, and misleading/outdated source. Expand to at least 60 labelled claim pairs (including non-conflicts) and 30 scripted turn-control cases. Reserve at least one process scenario and 20 claim pairs as an untouched holdout. Include adversarial spoken/document instructions and negative cases where an existing source is wrong or out of date.

Labels must distinguish contradiction, duplicate, compatible variant, transcription ambiguity, unsupported account and insufficient evidence. Two reviewers label disputed cases independently and resolve their differences; model-generated labels alone are not a reference standard. Synthetic speech can support repeatability but cannot establish comfort or accent robustness. Use approved human voice trials after participant controls are ready.

For listening, start with three configurations and 20 common prompts each, shuffled and anonymised by configuration. Compare a held-out set containing acronyms, dates, numbers, negation, short acknowledgements and respectful challenge. Use at least five consenting evaluators for an initial preference check; report the small sample and individual variation rather than generalising to a population. The user's own audition may select an interim prototype voice but is not evidence of enterprise usability.

## Proposed measures and initial targets

| Measure | Definition / target | Gate |
|---|---|---|
| Meaningful response latency | Acoustic end of SME turn to first audible substantive response; warm p50 ≤1.5 s, p95 ≤3 s over ≥100 turns; separately report cold start | G1/G2 |
| Acknowledgement latency | First audible acknowledgement; report separately, never count filler as substantive response | G1/G2 |
| Barge-in response | Confirmed user speech onset to cessation of played output; p95 ≤250 ms, with no stale queued response | G1/G2 |
| Turn completion | Premature turn-cut rate ≤5% in labelled cases; distinguish hesitant speech, silence and completed thought | G2 |
| Speech/content fidelity | No altered numbers, dates, negation or policy meaning in held-out spoken output; flag all observed failures | G1/G2 |
| ASR quality | Report WER and critical-term error rate by accent/noise condition; every detected high-impact ambiguity is confirmed | G1/G2 |
| Live challenge precision | ≥95% of raised discrepancies are relevant on labelled cases; report recall separately and do not improve precision by hiding all conflicts | G2 |
| Conflict recall | ≥85% on the predefined same-scope conflict set; async review covers missed/live-deferred cases or reports incompleteness | G2/G3 |
| Claim provenance | 100% of candidate claims retain transcript revision; 100% of evidence assertions cite eligible source/version | G2/G3 |
| Approval separation | Zero unapproved/disputed/withdrawn claims exposed as approved answering facts in negative tests | G3 |
| Revision and replay | Stale approvals rejected; duplicate retries produce one logical source; approved contribution survives two rebuilds | G3 |
| Failure recovery | Restart/disconnect/model timeout/source revocation produce explicit recoverable states without false publication success | G2/G3 |
| Experience | Median ≥4/5 for comfort, clarity and usefulness; capture fatigue and “felt judged” responses separately | G2/G4 |
| Atlas resource impact | On the same controlled workload, target ≤10% increase in warm Ask p95 under one interview; quantify memory, CPU/GPU and failures | G3/G4 |
| Local runtime | After provisioning, egress-disabled interview succeeds; no hosted inference fallback; evidence/audio/transcripts stay in allowed stores | G1/G3 |

Where sample sizes are small, publish numerator/denominator and uncertainty. Zero observed failures is not proof of zero risk. Recall and precision need a fixed labelled denominator. Tune on the development set only and record prompt/model/data versions; do not optimise around holdout misses and still call the holdout untouched.

Illustrative warm latency budget: endpoint decision 350 ms, final ASR 250 ms, bounded retrieval/check 350 ms, question planning/check 800 ms, synthesis 450 ms, delivery/playback 100 ms: 2.3 s total. Work may overlap, and stage p95 values do not mathematically sum to end-to-end p95. Instrument actual timestamps rather than presenting this budget as a measurement or guarantee.

## Non-regression rulebook

1. Baseline is `c7e6ff7` and the accepted corpus/benchmark evidence; document any later baseline change explicitly. Do not restore the reverted Ask changes as part of interviewer work.
2. First implementation edits are limited to `services/sme_interviewer/`, its own dependency/runtime files, interview fixtures/tests and the new UI component. `frontend/src/App.tsx` and an isolated API client may be changed only for an approved feature-flagged entry point. These are proposed paths, not existing files.
3. Atlas core edits require a separate integration story specifying allowed files, interface compatibility, data migration and rollback. Existing Ask, source approval, ontology sync, EAM and compliance behaviour are protected surfaces.
4. Use separate interview data, model environments and dependency locks. Do not run destructive data resets or re-ingest the accepted corpus for experimentation. Use an isolated Atlas copy with synthetic fixtures for publication tests.
5. New service disabled or stopped must leave established Atlas routes, navigation and startup usable. No mandatory TTS/ASR dependency enters the core application environment.
6. Before code merge, run focused contract/lifecycle tests and the existing full pytest/Ruff gate; run the frontend build and browser checks when UI changes. Exercise affected source/ontology/process/EAM cases when publication is touched.
7. Compare real-model output and latency on an unchanged reference workload before changing model/routing behavior. Existing offline tests alone do not prove voice or semantic quality.
8. Back up before any approved migration, support additive schema versions and test restoration. Keep a disable switch and reverse publication by governance status/supersession, not silent deletion of history.
9. Preserve unrelated working-tree files. Use item-scoped commits, report exact checks, update the wiki and handover, and let the Human accept/close work.

## Acceptance without Azure Test Plans

No new ADO Test Plans, Test Suites or Test Case work items will be created. Automated tests belong in the repository where they verify substantive behavior. An ordinary Story records a concise demonstration outcome, relevant evidence artifact and Human acceptance note; no separate UAT script is imposed on the user. Existing historical test artifacts remain unchanged.

Documentation-only delivery is verified through link/manifest consistency, source review, publication read-back, a secret scan and repository status. The existing baseline suite was run once as part of this audit; no new tests mirror the prose.

## Cost and access plan

No paid service is needed for discovery. First use existing hardware, existing Atlas fixtures and open local models. Model downloads and package provisioning are separate from offline runtime operation. If the machine fails the agreed resource gate, compare a smaller configuration, queued deep review and an already available local GPU host before requesting a purchase.

Human inputs are the host specification, preferred channel, pilot process/owner, preferred voice style and accepted participant/retention policy. Later Teams/Webex work needs an approved development tenant/account and administrator involvement; later hardware work needs a spending limit and exact device variant. Perlego reading is optional. No access request is a commitment to buy or grant broader permissions.
