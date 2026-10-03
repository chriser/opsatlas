# REF S22b: product claims from the prompt into the guide (3 October 2026)

**Verdict: not adopted. Engine 1.8.9's evidence prompt stays as it is.**

The mark (the Human's decision, 3 October 2026): with the drafts in `evaluation/sets/tibi/s22b-guide-drafts.json`
published on a disposable copy, the candidate prompt (`candidate-prompt.diff`) is scored against 1.8.9 on that same
copy. No measure may move beyond the scorecard's tolerance. Only if it passes do the drafts go to the live guide for
the Human's approval, followed by the engine change.

Method:
- One disposable copy of the sales workspace, with both drafts published and re-approved.
- Core on 127.0.0.1:8798.
- `evaluate_engine --runs 2 --judge`, run from two worktrees pinned at 1023c60: 1.8.9 first, then the candidate.
- Knowledge digest `58646a68…` and scenarios `315b84b3562e4b98` were the same for both runs.

| Measure | 1.8.9 | Candidate | Verdict |
|---|---|---|---|
| fallback rate | 0.077 | 0.154 | degraded |
| judged support | 5.0 | 4.77 | degraded |
| blocked sentences | 9 | 6 | improved |
| first segment p95 ms | 1494.5 | 1267.9 | improved |
| all other measures | | | same |

Neither degradation is noise. Each repeats in both runs:
- **rehearsal-bank[5]** falls back with the candidate prompt.
- **small-talk-then-product[1]** mentions a web control panel the records do not hold (judged support 2).

This is the second time moving the prompt's examples into rules has lowered the scorecard. The first attempt is
commit bc20e81.

Neither the drafts nor the engine change were submitted to live.

The "Before" column in the two saved cards is the live 0945 card (the live data), not the copy. For that reason both
runs were compared directly, card against card. These cards are kept in this subfolder so the next engine's scorecard
does not compare itself with a copy.
