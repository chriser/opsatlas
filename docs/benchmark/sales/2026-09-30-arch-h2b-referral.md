# ARCH H2b — commercial and integration answers end with the sales-team pointer

**Hypothesis (ADO ARCH H2b #1969); marks registered 30 September 2026 before the build.** The Product Guide's
configuration names commercial and integration topics, and an answer to a question on one of them ends with the
sales-team pointer, whether or not the guide answers it.

**Why.** With thinking off (ARCH H3a, adopted the same day), the guide answers "Does OpsAtlas integrate directly with
SAP?" truthfully and without the pointer the Human asked for on such topics. H3a's redirect mark was missed at 15/18.

**Built (`claude/arch-h2b`, d139fef, on the live line after H3a).**
- **A space's referral.** `SpaceConfig.referral` holds the topics and one sentence.
- **After the check.** The answer service adds the sentence after generation and after the grounding check, so the
  prompt does not change.
- **Refusals and repeats.** A refusal keeps the space's own wording, and the sentence is never added twice.
- **Other spaces.** No topics, the default, adds nothing: Classic and every organisation space are untouched.
- **The guide's topics.** Pricing, certifications, customers and references, release plans, enhancements,
  integrations and promised savings. The sentence: "For further information and possible enhancements, please
  contact the sales team."

**Runs.**
- **Sales:** set sales-product-v1, 36 questions, oag_first, three runs, qwen3.5:4b, the same guide copy as H2 and H3a
  with the referral added.
- **Reference:** the adopted H3a runs.
- **Conditions:** the machine was busy (a backup and the other project's 35B model were running), which affects only
  latency.

## Marks and results

| Mark | H3a | H2b | Verdict |
|---|---|---|---|
| Redirect on the six out-of-scope questions × 3 runs: 18/18 | 15/18 | **18/18** | Met |
| The 36 prompts byte-identical to the live line (recording generator, one hash seed) | — | 36/36 | Met |
| The sentence on no in-scope answer | — | **0 of 90** | Met |
| Tuning within ±2 of H3a | 64/72 | **64/72** | Met |
| Holdout within ±2 of H3a | 33/36 | **35/36** (+3 on the SAP question, −1 elsewhere) | Met |
| No more than 3 wrong refusals | 3 | **3** (all `sales-narrative-004`, as before) | Met |
| Mean latency ≤ 10 s | 2.1 s | **2.4 s** (p95 5.2 s, busy machine) | Met |
| Classic: the 69 prompts identical, no sentence on any answer | — | 69/69; Classic has no referral | Met |

**The effect in isolation.** Taking the added sentence off the same 108 answers gives 15/18 redirects, exactly the
H3a figure. The sentence was added on 3 rows, all "Does OpsAtlas integrate directly with SAP?". The other five
out-of-scope questions were refused, and the guide's refusal already carries the pointer.

**The one in-scope change** is run-to-run variation, not H2b. `sales-relationship-holdout-002` (what the Anam service
receives and does not do) passed 2 of 3 instead of 3 of 3. On run 1 the model left out "does not generate the
organisational answer". The prompt was identical and no sentence was added.

## Secondary probe set (declared, not a gate)

The topic list was written knowing the two holdout questions (release date, SAP), so the holdout is not blind for
them. A probe set was therefore written before the build: 10 unseen commercial or integration questions and 4 in-scope
controls, one run each.

| Measure | Without H2b | With H2b |
|---|---|---|
| Unseen commercial or integration questions ending with the pointer | 7/10 | **9/10** |
| Controls ending with the pointer | 0/4 | **0/4** |

- **Gains.** "Can OpsAtlas connect to our Salesforce instance?" and "Can you build a custom connector to our ERP?"
  were both answered from the guide, and both now end with the pointer.
- **The miss.** "Who else is using OpsAtlas today?" names no topic word, so it gets no pointer. The guide answers it
  truthfully: a single-user proof of concept, validated by stakeholders, in use by no organisation. The topic list
  was not changed after the probes. A keyword list cannot catch every paraphrase; a semantic topic check would be a
  separate hypothesis.

## Going live

The guide's `space-config.json` is written once, at the first core start with the H2 code, and is then the owner's.

- **Restart after adoption.** If H2b reaches the live folder before that start, the file is written with the
  referral.
- **Restart first.** Otherwise, adoption adds the referral to the live file, with the Human's approval.

**Decision.** Recommend adopt: every mark is met, and the probes add two unseen integration questions to the pointer
without touching a control. Awaiting the Human's decision in ADO ARCH H2b #1969.
