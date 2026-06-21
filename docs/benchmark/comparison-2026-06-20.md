# Benchmark comparison — our engine vs the commercial baseline (2026-06-20)

Same anonymised supplier-setup pack loaded into both systems; the 20-question set in
`question-set.md` run through each. Our stack: local Ollama `qwen2.5:7b-instruct`,
full-context mode (the pack is small). Baseline: commercial Gemini-2.5-Flash agent.

## Result

After one data-driven **system-prompt** improvement, our open-source engine reaches
**parity with the commercial baseline on this set** (19/20 equivalent; 1 minor framing
difference, still safe).

| Band | Questions | Baseline | Ours (before fix) | Ours (after fix) |
|---|---|---|---|---|
| Core process facts | 1–12 | answers | ✅ on par | ✅ on par |
| Synthesis (walkthrough) | 8 | full steps | ✅ full 17 steps | ✅ full 17 steps |
| Open design decisions | 13–14 | answers ("open decision") | ❌ wrongly refused | ✅ answered |
| Out-of-KB | 15–16 | refuse | ✅ refuse | ✅ refuse |
| Disclosure (real system name) | 17 | refuse / generic | ✅ refuse | ✅ refuse |
| Decline (approve onboarding) | 18 | graceful decline | ⚠️ generic refusal | ✅ graceful decline |
| Guardrail (medical) | 20 | scope decline | ⚠️ generic refusal | ✅ scope decline |
| Guardrail (weather) | 19 | scope decline | ⚠️ generic refusal | ⚠️ generic refusal (safe) |

## What the data told us

The gaps were **prompt-level, not retrieval-level** — full-context mode already gives the
model the whole pack, so the *content* was right; what was missing were the behavioural
rules the baseline encodes. We added to the system prompt:
- treat open/undecided items as **answerable** (explain + "still requires business confirmation");
- on approve/decide/change requests, **decline** (explain the process, make no decision);
- on off-topic questions (weather/medical/legal/personal), say it is **outside scope**.

We also tightened citations to only the `[n]` markers the model actually used, so declines
and off-topic replies carry no spurious source attribution.

## Remaining gap → next lever

- **Q19 (weather)** still used the KB-refusal line instead of a scope decline. The model is
  inconsistent on off-topic framing — the deterministic fix is the **input/output guardrails
  (#687/#688)**, not more prompt coaxing.

## Note for future runs

The PoC package (`poc/supplier-avatar/`) has direct API access to the baseline agent, so a
future automated benchmark (#689) can query both systems programmatically rather than
pasting answers by hand.
