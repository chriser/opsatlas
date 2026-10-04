# ARCH H4 — answers keep the evidence's own time and scope

**Hypothesis (ADO ARCH H4 #1973); marks registered 1 October 2026 before the build.** One rule added to the core's
answer prompt (v2 to v3) makes answers keep the evidence's own time and scope, without costing accuracy elsewhere.

> Keep the evidence's own time and scope. If the evidence says something belonged to the proof of concept or an
> earlier version, was retired, is only planned, or is not part of this edition, say so in your answer, and do not
> describe it as current.

**Why.** After AUDIT F2 the guide says the compliance-reasoning service belonged to the proof of concept and is not
part of this edition. Yet qwen3.5:4b answered "The compliance-reasoning service uses Qwen 2.5 14B Instruct for Deep
Audit [18].": present tense, framing dropped, 0/3 on both questions. A tighter guide wording changed nothing.

**Built (`claude/arch-h4`, ddd9890, on the live line after AUDIT F2; not merged).**
- **The rule.** It is added to the answer prompt's rules, after the rule on open design decisions.
- **Version.** `PROMPT_VERSION` moves to v3, and the audit trace records it.
- **Unchanged.** Nothing else changes: retrieval, routing, the referral and the guardrails are as they were.

**Runs.**
- **Sales:** set sales-product-v2, oag_first, three runs, qwen3.5:4b, on a copy of the corrected guide with the
  referral. Baseline: the AUDIT F2 runs, the same guide with prompt v2.
- **Classic:** holdout, oag_first, three runs, qwen2.5:7b-instruct, with the settings of the H3a run. Baseline: H3a.
- **Probes:** the secondary probe set, one run each, prompt v2 and v3.

## Marks and results

| Mark | Baseline | H4 | Verdict |
|---|---|---|---|
| `sales-entity-002` and `sales-entity-holdout-002` pass on at least 2 of 3 each | 0/3 and 0/3 | **3/3 and 3/3** | Met |
| Every other Sales question within ±2 per split | tuning 62/69, holdout 31/33 | **63/69, 31/33** | Met |
| Redirect 18/18; no more than 3 wrong refusals; mean latency ≤ 10 s | 18/18; 3 | **18/18; 3; 2.7 s** | Met |
| Classic holdout at least 70/72 | 72/72 (H3a) | **69/72** | **Missed** |

| Probe (secondary) | Prompt v2 | Prompt v3 |
|---|---|---|
| Qualifier kept, of 5 | 2 | **4** |
| A strong qualifier invented on a control, of 3 | 0 | **1** |

**The target is fixed.** Every answer to the two questions now begins with the framing, for example "The
compliance-reasoning service used in the proof of concept uses Qwen 2.5 14B Instruct for Deep Audit [18]."

**The Classic miss is a scoring miss.** One question, `narrative-holdout-001` ("Why should new article attributes
have a clear business purpose?"), went from 3/3 to 0/3. The answers still say it, for example "This ensures that
the platform does not turn into a data graveyard", but in words the fact matcher does not accept. No qualifier was
added to them.

**The new rule invents a false scope.** The probe "What does the Digital SME do?" answered: "The Digital SME is not
part of this edition of the proof of concept; it is planned for real deployment". That is false. The main set shows
the same thing once in 108 answers: asked what the Anam service receives and does not do, one run listed "It is not
part of this edition [18]." In both cases the model moved the qualifier of the compliance-reasoning service onto
another item described in the same guide document.

Across the 108 Sales answers, strong qualifiers ("not part of this edition", "retired", "planned", "no longer") rose
from 1 to 5. Three are correct, about the compliance-reasoning service. One is the false statement about Anam. One
is a loose "planned but not yet delivered" about production controls.

## Decision

**Not recommended.** It fixes the two questions but tells a customer, now and then, that a delivered part of the
product is not part of this edition. In a sales guide that is worse than the original present-tense answer.

This rule did not keep a qualifier on its own subject with a 4B model. A reworded rule might, but any general
wording carries the same risk and needs its own run. The fix goes to ARCH H4c instead: a sentence the guide's configuration adds to answers on the retired service's own topics, after
generation. It works like the H2b referral, so no other answer and no prompt changes.
