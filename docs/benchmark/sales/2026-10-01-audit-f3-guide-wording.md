# AUDIT F3 — clearer guide wording on the two supporting services; label v3

**The Human's approval (ADO AUDIT F3 #1982), 1 October 2026.** The approval covers a clearer opening for the guide
document "Local operation, supporting services and the digital SME", and a new label for `sales-mixed-002`.

**Why.** ARCH H4c found a problem with the AUDIT F2 wording, published that morning. On "Which models do the two
supporting services use, and what can neither of them do?", the model sometimes said that the governance review "is
not part of this edition". It did so in 2 of 10 runs, and it is false. The question's label also still described the
old guide.

**The approved opening.**

> The principal knowledge-processing activities run locally. Two local supporting services assist in this edition: a
> process-diagram service, which draws the process maps, and a statement-level governance review, which checks the
> knowledge base for conflicts and duplicates with a local Qwen 2.5 14B Instruct judge and Qwen 3.5 35B-A3B as a second
> opinion on each conflict. Neither can approve sources or change organisational knowledge: a person decides every
> finding. The proof of concept used a compliance-reasoning service instead of the statement-level governance review,
> with Qwen 2.5 14B Instruct for Deep Audit and DeepSeek-R1 8B for bounded screening; it could not approve sources or
> change organisational knowledge either, and it is not part of this edition.

- **Repository.** The seed record in `services/opsatlas_sales/corpus/foundation.json` carries the same opening.
- **Live guide.** The opening is saved as a submitted draft of the live document, for the Human to publish.
- **Label, sales-product-v3.** `sales-mixed-002` expects Qwen 2.5 14B Instruct, Qwen 3.5 35B-A3B, and that neither
  service can approve sources. Before, it expected Qwen 2.5 14B Instruct, DeepSeek-R1 8B, and that neither can approve
  sources. v2 is in git history.

## Check (marks registered in ADO before the run)

Runs: a copy of the guide with the approved opening, the referral and the H4c note; labels v3; oag_first; three
runs; qwen3.5:4b. Baseline: the H4c runs rescored under v3.

| Mark | Baseline | AUDIT F3 | Verdict |
|---|---|---|---|
| `sales-mixed-002` passes on at least 2 of 3, never saying the governance review is not part of this edition | 0/3 | **3/3; 0 misstatements** | Met |
| The three compliance questions pass on at least 2 of 3 each | 3/3 each | **3/3 each** | Met |
| Every other question within ±2 per split | tuning 54/63, holdout 31/33 | **54/63, 33/33** | Met |
| Redirect 18/18; no more than 3 wrong refusals; mean latency ≤ 10 s | 18/18; 3 | **18/18; 3; 1.8 s** | Met |
| "Not part of this edition" applied to nothing but the compliance-reasoning service, across 108 answers | — | **none outside the note** | Met |

The holdout +2 is `sales-relationship-holdout-002` at 3/3 instead of 1/3. That question has varied from run to run
all along.

**Decision.** Go live: the Human publishes the draft in the panel.
