# AUDIT F2 — the Product Guide's record of the compliance-reasoning service

**The Human's decision (ADO AUDIT F2 #1970).** On 30 September 2026 the Human decided that the guide should be
corrected. On 1 October 2026 the Human approved the wording and the label additions. AUDIT F1 had removed the
compliance-reasoning service from Sales; OpsAtlas Classic keeps it. One guide document still named it as a running
service: "Local operation, supporting services and the digital SME" (record `deployment`).

## The change

The document's opening, before:

> The principal knowledge-processing activities run locally. Two local supporting services assist: a
> compliance-reasoning service for internal and external governance reviews, using Qwen 2.5 14B Instruct for Deep
> Audit and DeepSeek-R1 8B for bounded screening, and a process-diagram service. Neither can approve sources or change
> organisational knowledge.

After:

> The principal knowledge-processing activities run locally. A local process-diagram service draws the process maps,
> and the governance review checks the knowledge base statement by statement for conflicts and duplicates, with a
> local Qwen 2.5 14B Instruct judge and Qwen 3.5 35B-A3B as a second opinion on each conflict. Neither can approve
> sources or change organisational knowledge: a person decides every finding. In the proof of concept, governance
> reviews used a separate compliance-reasoning service, with Qwen 2.5 14B Instruct for Deep Audit and DeepSeek-R1 8B
> for bounded screening. That service could not approve sources or change organisational knowledge either, and it is
> not part of this edition.

The rest of the document is unchanged.

- **Repository.** The seed record in `services/opsatlas_sales/corpus/foundation.json` carries the same change, so a
  new workspace starts with it. Seeding never rewrites an existing record.
- **Live guide.** The wording is saved as a submitted draft of the live document. It becomes live when the Human
  approves and publishes it in the panel, which also updates the record Tibi speaks from.
- **Benchmark labels, sales-product-v1 to v2.** `sales-entity-002` (Deep Audit) and `sales-entity-holdout-002`
  (bounded screening) keep their model facts. Each also expects the proof-of-concept framing: "proof of concept",
  with aliases "not part of this edition" and "DT603". `sales-relationship-002` is unchanged. v1 stays in git history.

## Check (marks registered in ADO before the run)

Runs: a copy of the guide with the corrected document published and the referral on, labels sales-product-v2,
oag_first, three runs, qwen3.5:4b. Baseline: the H2b runs of the guide before the correction, rescored under v2. In
full-context mode every prompt holds the whole guide, so every prompt changes; a full prompt before and after
differs only in the corrected passage.

| Mark | Before | After | Verdict |
|---|---|---|---|
| `sales-entity-002` and `sales-entity-holdout-002` pass on at least 2 of 3, with the proof-of-concept framing | 0/3 and 0/3 | **0/3 and 0/3** | **Missed** |
| `sales-relationship-002` still passes on at least 2 of 3 | 3/3 | **3/3** | Met |
| Every other question within run-to-run variation (±2 per split) | tuning 58/66, holdout 32/33 | **59/66, 31/33** | Met |
| Redirect 18/18; no new wrong refusals | 18/18; 3 | **18/18; 3** (all `sales-narrative-004`) | Met |

**Reading the miss.** The model names stay right on every run, but the answers drop the context. The answer is
"The compliance-reasoning service uses Qwen 2.5 14B Instruct for Deep Audit [18]." in the present tense. The cited
document now says that the service belonged to the proof of concept and is not part of this edition.

An exploratory test, not registered, tried a tighter wording in a copy: "The compliance-reasoning service is not part
of this edition: it belonged to the proof of concept, where it used…". It gave the same answers, 0/3 on both
questions. The wording is therefore not the cause: asked which model a service uses, the 4B model extracts the name
and leaves the framing out.

## Decision

- **Publish the approved wording.** The guide no longer presents the service as running, and nothing else regresses.
- **Keep the v2 labels.** They measure what the answers still omit, so v2 scores sit three below v1 on each split, by
  design. Compare v2 runs only with v2 runs.
- **Follow-up candidate, not registered.** Answers should keep a source's own framing when it marks something as
  belonging to the proof of concept or not part of this edition. That is a prompt-level hypothesis, with its own marks,
  for the Human to pick.
