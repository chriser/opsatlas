# ARCH H2 — per-space configuration and the Product Guide's graceful redirect

**Hypothesis (ADO ARCH H2 #1943), marks registered 30 September 2026 before any code; the question set and the
direction approved by the Human the same day:** the router's cues, the guard lists and the refusal wording become
per-space configuration (today's literals as the default), and the Product Guide's configuration answers questions it
does not cover with a graceful redirect to the sales team, without loss on either corpus.

**Built (`claude/arch-h2`, e43e7a8, 4370ee1):** `assistant.space_config.SpaceConfig` loaded from each partition's
`space-config.json`; the router, the guardrails and the answer service read it; the Sales Product Guide's file is
written once at start ("That is not covered by the OpsAtlas product guide. For pricing, certifications, customer
references, release plans and possible enhancements, please contact the sales team, who can give you further
information."); an organisation's space keeps the plain refusal. The benchmark harness now survives a model
timeout (one failed row instead of a failed run) and the generation timeout is configurable (`KP_LLM_TIMEOUT`).

## Marks and results

| Mark (as registered) | Result | Verdict |
|---|---|---|
| Classic, default configuration: router outputs identical before and after | Class, unsupported-lookup, facts-map plan with evidence and templated answer, ontology evidence and guard category byte-identical on all 69 questions | Met |
| Classic: pass counts within ±2 of the H1b run, same route per question and run | Tuning 104/135 = 104/135; holdout 71/72 against 72/72; routes identical on every row | Met |
| Sales accuracy no lower than the same-session baseline minus two | Tuning 62/72 = 62/72; holdout 30/36 against 32/36 (−2, at the allowance) | Met, at the edge |
| No new wrong refusals | 13 against 12 | Missed by one |
| Out-of-scope 100 % refused or redirected | 17/18 (baseline 17/18) | Missed by one row |
| Graceful redirect on ≥ 90 % of out-of-scope answers | **17/18 (94 %), from 0/18** | Met |
| Mean latency within +0.3 s of the baseline | 57.3 s against 44.4 s | Missed as measured |

Runs (oag_first, three each; Sales: qwen3.5:4b, nomic-embed-text, rewrite and rerank off, generation timeout 600 s):

| Corpus | Split | Variant | Passed | Route | Stable | Mean | p95 |
|---|---|---|---|---|---|---|---|
| Classic | tuning | H1b run | 104/135 | 123/135 | 40/45 | 1.7 s | 6.2 s |
| Classic | tuning | H2, default configuration | 104/135 | 123/135 | 41/45 | 2.5 s | 9.0 s |
| Classic | holdout | H1b run | 72/72 | 72/72 | 24/24 | 1.5 s | 6.1 s |
| Classic | holdout | H2, default configuration | 71/72 | 72/72 | 23/24 | 1.7 s | 7.7 s |
| Sales | tuning | baseline | 62/72 | 72/72 | 17/24 | 41.1 s | 97.7 s |
| Sales | tuning | H2, Product Guide configuration | 62/72 | 72/72 | 18/24 | 56.5 s | 112.5 s |
| Sales | holdout | baseline | 32/36 | 36/36 | 9/12 | 51.1 s | 90.7 s |
| Sales | holdout | H2, Product Guide configuration | 30/36 | 36/36 | 8/12 | 59.0 s | 102.1 s |

## Reading the misses

**The model receives exactly the same input under both versions.** Every prompt the answer service sends for the 36
Sales questions (72 prompts: the answer and the grounding check) was captured with a recording generator under the
baseline code (1f3e7a2) and the candidate (4370ee1): all 72 are byte-identical, and so are the modes and routes. The
only behavioural difference H2 makes on the guide is the wording of a refusal. Every other difference in the table
is the 4b model's sampling and the machine's load:

- *Wrong refusals 13 against 12, holdout −2:* the questions that changed (entity-001/003/004, relationship-holdout-002,
  aggregate-003, narrative-001, narrative-holdout-002, mixed-002) moved both ways, on identical prompts.
- *Out-of-scope 17/18:* the same question failed in both runs, `sales-out-of-scope-003` ("Which customers already use
  OpsAtlas in production?"). The model answered it from the guide instead of declining: "a working local proof of
  concept and not a production enterprise deployment … a real deployment … is planned but not delivered". That is a
  true answer the label does not accept; the label is reviewed below, not changed after the fact.
- *Latency:* the baseline's own three runs averaged 56.0, 40.1 and 37.3 s with the same code; the candidate's
  58.8, 58.9 and 54.2 s, while the audit's agents and another project's model server shared the machine. A +0.3 s
  mark was copied from the Classic scale (answers of about 1.5 s) and cannot be measured on answers of 40–60 s with a
  run-to-run spread of 19 s. On identical prompts, H2 has no mechanism to change latency; the prompt identity is the
  evidence for that, not the timing.

**The real finding is the latency itself.** Every guide answer takes 40–60 s (median 37–50 s, maximum 164 s): the
guide fits the full-context limit (24,000 characters), so all 19 sections go to `qwen3.5:4b` on every question, and
the model's output length varies widely. That is H3's subject.

## Decision trail

- Recommendation: **adopt**. The effect the Human asked for is delivered (0/18 → 17/18 graceful redirects); the
  refactor provably changes nothing else on either corpus; the misses are noise or one label.
- Label review for the next version of the set (declared, not applied to this result): `sales-out-of-scope-003`
  should also accept "not a production deployment" / "no customers", because the guide answers it.
- Awaiting the Human's decision in ADO ARCH H2.
