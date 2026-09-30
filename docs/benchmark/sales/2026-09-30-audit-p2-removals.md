# AUDIT P2 — parking the compliance sidecar, simulator, stress lab and value analytics out of Sales

**Hypothesis (ADO AUDIT F1 #1968); marks registered 30 September 2026 before the build.** Removing the
compliance-reasoning sidecar and parking the simulator, the Process Stress Lab and value analytics in OpsAtlas Classic
changes no Sales behaviour.

**Why.** The deep audit of the same day (`docs/audits/2026-09-30-deep-audit.md`, section 4) found the sidecar switched
off in Sales, superseded by statement governance (GOV E1) and polled every 30 seconds by the panel with no other
request in a week. The simulator, the stress lab and value analytics had two or three requests in five days, no Sales
data to work on, and a home in Classic, which keeps all four unchanged in its frozen checkout.

**Built (`claude/audit-parking`, on the live line: it does not carry ARCH H3a, which awaits its decision).**

- **Deleted.** The sidecar (`services/compliance_reasoning/`), its bridge and routes, its evaluation harness, two scripts,
  two label files and five test files. Also the simulator, the stress lab and value analytics, with their routes,
  pages, API client code and styles.
- **Kept.** The record of the last compliance review (`src/assistant/compliance/latest.py`). The facts map still reads
  it: the Classic regression corpus holds 30 compliance findings, 23 obligations and 12 claims from it. Analytics
  event type names stay, so historical events still read.
- **IAM.** Catalogue and seeds move to version 2. Four permissions retire with their features: `processes.stress.run`,
  `diagnostics.simulator.run`, `analytics.value.manage` and `governance.reviews.cancel`. A custom role saved under
  version 1 keeps its row, and a retired key in it grants nothing (new policy test). The live `iam.db` has no custom
  roles or denies, so nothing there refers to the retired keys.
- **Panel.** The status list drops the compliance row, which was a poll of a service Sales never configured. An old
  bookmark to a removed page opens the dashboard.
- **Evidence page.** References to removed tests and data now point into the Classic tag, for example
  `opsatlas-v1-dt603-final:tests/test_simulator_runner.py`.

## Marks and results

| Mark | Result | Verdict |
|---|---|---|
| Full suite green, less only the removed tests; ruff clean; the panel builds | 1,165 passed; the base (28601f9, the live line) had 1,280, and 116 left with the removed code, 1 added | Met |
| Route manifest: only the removed paths disappear (compliance ×10, simulator ×5, stress-test ×1, value ×2) | Those 18, plus the internal-review cancel route; nothing else changed and nothing was added | Met, one declared addition |
| The prompts for the 36 Sales and 69 Classic questions are byte-identical before and after | Sales 36/36. Classic 69/69 under the same hash seed, checked with seeds 1 and 2, and again on the live line | Met, see the seed note |
| The Classic copy's facts map has the same object counts after a rebuild | Identical: 453 links, and every object type's count | Met |
| The governance-benchmark scripts still import and run their offline paths | Both import. Scoring the pair results reproduces the recorded scorecard exactly. The statement filter reproduces the recorded filtered output exactly | Met, see the extractor note |
| A headless visit of every remaining page shows no console error | Every menu page (19) and every analytics tab (11) without a console error; no request to a removed route. The one failed request was Tibi knowledge asking the voice service, which the throwaway check did not run | Met for every menu page, see the process-review note |

## Deviations from the registered plan

- **The internal-review cancel route.** It only ever cancelled a sidecar job and answered 409 for a local review,
  which cannot be cancelled. It went with the sidecar, and `governance.reviews.cancel` retired with it.
  `governance.findings.resolve` stays: Tibi's answer review uses it.
- **The claim extractor.** The registered refinement moved it into the governance package. That would have moved 23
  definitions (about 280 lines) and five models only to keep a historical comparison runnable. Instead, the
  statement-index script no longer measures the retired extractor, and the pair benchmark no longer has an `engine`
  mode. Their recorded results (`statement-index.json`, `result-engine-v8.10.json`) stay, the scorecard still scores
  the engine's results, and Classic can run both again.

## Notes

- **The seed note.** Unseeded, two Classic prompts differed (`structured-relationship-003`, `mixed-002`). The old
  code gives the same two differences between two of its own runs under different hash seeds. The cause predates
  this change: aliases that differ only in case, such as "Payment Contract" and "Payment contract", tie in a
  case-insensitive sort, so their order follows the set's hash order. A follow-up makes the order total.
- **The process-review note.** The address `#process-review` without a session id is not in the menu, and it throws
  in the shell's fallback view. This dates from 28 September (8cf3233) and has a follow-up. With a session id, the
  page works.
- **Models.** `deepseek-r1:32b` (19.9 GB) is no longer referenced by Sales and can be removed on the host.
  `deepseek-r1:8b` stays, because Classic's compliance review uses it.
- **Tibi.** No engine file changed: the engine fingerprint covers `services/sme_interviewer/` and the claims rules,
  and neither was touched.

**Decision.** Adopt, as approved in audit decision 2. Every mark is met; the two deviations above are the Human's to confirm or overrule.
