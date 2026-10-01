# ARCH H4c — a configured note on the retired compliance-reasoning service

**Hypothesis (ADO ARCH H4c #1974); marks registered 1 October 2026 before the build.** A space may carry topic notes:
topics and one sentence each, added after generation to answers on those topics, like the H2b referral. The Product
Guide gets one note for the retired compliance-reasoning service:

- **Topics:** `compliance[- ]reasoning`, `deep audit`, `bounded screening`.
- **Sentence:** "The compliance-reasoning service belonged to the proof of concept and is not part of this edition."
  This repeats what the guide itself says since AUDIT F2.

**Why.** ARCH H4, a general prompt rule, fixed the two framing questions but made the model move "not part of this
edition" onto Anam and the Digital SME. A note is tied to its own topics and does not touch the prompt.

**Built (`claude/arch-h4c`, 7b55c90, on the live line after AUDIT F2).**
- **One model.** `TopicSentence` holds topics and a sentence; the referral is one, and `SpaceConfig.notes` is a list.
- **Order.** The answer service adds the notes, then the referral, after generation and the grounding check.
- **Limits.** A sentence is never added twice and never to a refusal.

**Runs.**
- **Sales:** set sales-product-v2, oag_first, three runs, qwen3.5:4b, on a copy of the corrected guide with the
  referral and the note. Baseline: the AUDIT F2 runs.
- **Prompt identity:** a recording generator, one hash seed, against the live line (d8d9ab8).

## Marks and results

| Mark | Baseline | H4c | Verdict |
|---|---|---|---|
| `sales-entity-002` and `sales-entity-holdout-002` pass on at least 2 of 3 each | 0/3 and 0/3 | **3/3 and 3/3** | Met |
| The 36 Sales prompts byte-identical to the live line | — | **36/36** | Met |
| The note on the three compliance questions only | — | **9 of 9 rows on them, 0 elsewhere** | Met |
| Every other question within ±2 per split | tuning 62/69, holdout 31/33 | **60/69, 31/33** | Met |
| Redirect 18/18; no more than 3 wrong refusals; mean latency ≤ 10 s | 18/18; 3 | **18/18; 3; 2.2 s** | Met |
| Classic: no notes, the 69 prompts identical | — | **69/69** | Met |

**The tuning −2 is run-to-run variation.** It is one question, `sales-aggregate-004`, at 0/3 instead of 2/3, with an
identical prompt and no note. That question has scored 1, 2, 3 and 0 out of 3 in the last four runs (H2b, AUDIT F2, H4, H4c).

**Secondary probes.** The two probes on the compliance-reasoning service carry the note. Among the six controls,
which include the at-risk items Anam, the Digital SME, the process-diagram service and external evidence, none
carries a note or "not part of this edition". One control answer calls a real deployment "planned but not yet
delivered", a loose phrase that the unchanged prompt also produces.

## A finding in the published guide, independent of H4c

With the live prompt and the published AUDIT F2 wording, the model sometimes says that the governance review "is not
part of this edition", which is false. It happens on "Which models do the two supporting services use, and what can
neither of them do?" (`sales-mixed-002`):

| Wording | Misstatement, of 10 runs | `sales-mixed-002` passes, of 10 |
|---|---|---|
| Published (AUDIT F2) | 2 | 10 |
| Clearer: "Two local supporting services assist in this edition: … The proof of concept used a compliance-reasoning service instead of the statement-level governance review …; it is not part of this edition." | **0** | 1 |

The clearer wording removes the misstatement. The question's label, though, still expects DeepSeek-R1 8B among "the
two supporting services" models, which is the old guide's answer. Under the clearer wording the model names this
edition's two services correctly: the process-diagram service, and the governance review with Qwen 2.5 14B Instruct
and Qwen 3.5 35B-A3B. The old label marks that as a failure. The three compliance questions pass 30/30 under both
wordings.

## Decision

- **H4c:** recommend adopt. Every mark is met. Going live adds the note to the live guide's `space-config.json`, with
  the Human's approval.
- **The finding:** for the Human. The clearer wording and a new label for `sales-mixed-002` would remove a false
  statement from the live guide. The new label would expect Qwen 2.5 14B Instruct and Qwen 3.5 35B-A3B as the models,
  and that neither service can approve sources. The labels would become sales-product-v3.
