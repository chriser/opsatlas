# Compliance Reasoning Evaluation - 84/114 passed (74%)

Generated: 2026-07-03T15:30:39+00:00
Depth: deep
Model profile: deep=ollama:deepseek-r1:14b
Runs: 3
Fake generator: False
Throttle deep: False
Safety gates disabled: False

Total runtime: 1396.4s
Mean pair latency: 12.2s
P95 pair latency: 19.0s
Mean LLM-called latency: 15.5s
Mean deterministic latency: 0.0s

## Per-Class Metrics

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| contradiction | 100% | 88% | 93% | 24 |
| missing_obligation | 50% | 67% | 57% | 18 |
| missing_detail | 67% | 67% | 67% | 18 |
| too_vague | 100% | 83% | 91% | 18 |
| supported | 86% | 100% | 92% | 18 |
| not_related | 40% | 33% | 36% | 18 |

## Confusion Matrix

| Expected \ Actual | contradiction | missing_obligation | missing_detail | too_vague | supported | not_related |
|---|---:|---:|---:|---:|---:|---:|
| contradiction | 21 | 0 | 0 | 0 | 3 | 0 |
| missing_obligation | 0 | 12 | 3 | 0 | 0 | 3 |
| missing_detail | 0 | 0 | 12 | 0 | 0 | 6 |
| too_vague | 0 | 0 | 3 | 15 | 0 | 0 |
| supported | 0 | 0 | 0 | 0 | 18 | 0 |
| not_related | 0 | 12 | 0 | 0 | 0 | 6 |

## Observability

Rows that called the LLM: 90/114
Adjudicator coverage: 79%
Never adjudicated rows: 24
Total candidate count: 90
Lexical candidates: 54
Anchor-rescued candidates: 84
Semantic-rescued candidates: 0
Embedding errors: 0
Total adjudication calls: 90
Rejected candidate findings retained: 15

| Expected class | Never adjudicated |
|---|---:|
| contradiction | 0 |
| missing_obligation | 12 |
| missing_detail | 0 |
| too_vague | 0 |
| supported | 0 |
| not_related | 12 |

### Gate Demotions

| Reason | Count |
|---|---:|
| none | 0 |

### Decision Classes

| Decision class | Model | Final | Accepted | Rejected |
|---|---:|---:|---:|---:|
| contradiction | 21 | 21 | 21 | 0 |
| missing_detail | 18 | 18 | 18 | 0 |
| not_related | 15 | 15 | 0 | 15 |
| supported | 21 | 21 | 21 | 0 |
| too_vague | 15 | 15 | 15 | 0 |

## Prompt Context

Prompt calls observed: 90
Mean prompt-token estimate: 1145
Max prompt-token estimate: 1194
Near context limit prompts: 0
Context warning threshold: 80% of num_ctx

## Stability

Labels with classification flips: 0/38
Classification variance: 0%

## Pair Results

| Run | ID | Domain | Expected | Actual | Pass | LLM | Candidates | Gate reason | Latency |
|---:|---|---|---|---|:--:|:--:|---:|---|---:|
| 1 | vat-contradiction-retention-delete-001 | vat | contradiction | contradiction | PASS | yes | 1 |  | 16.8s |
| 1 | vat-contradiction-retention-not-required-002 | vat | contradiction | contradiction | PASS | yes | 1 |  | 18.5s |
| 1 | vat-contradiction-rate-change-old-rate-003 | vat | contradiction | contradiction | PASS | yes | 1 |  | 14.8s |
| 1 | vat-contradiction-rate-change-new-rate-004 | vat | contradiction | contradiction | PASS | yes | 1 |  | 14.9s |
| 1 | vat-contradiction-private-use-005 | vat | contradiction | contradiction | PASS | yes | 1 |  | 16.9s |
| 1 | packaging-contradiction-third-party-shipping-006 | packaging_waste | contradiction | supported | FAIL | yes | 1 |  | 18.4s |
| 1 | packaging-contradiction-supplier-purchased-007 | packaging_waste | contradiction | contradiction | PASS | yes | 1 |  | 12.7s |
| 1 | packaging-contradiction-delete-evidence-008 | packaging_waste | contradiction | contradiction | PASS | yes | 1 |  | 13.0s |
| 1 | supported-vat-private-use-percentage-001 | vat | supported | supported | PASS | yes | 1 |  | 11.8s |
| 1 | supported-vat-evidence-retention-002 | vat | supported | supported | PASS | yes | 1 |  | 14.5s |
| 1 | supported-vat-rate-change-003 | vat | supported | supported | PASS | yes | 1 |  | 16.1s |
| 1 | supported-packaging-material-split-004 | packaging_waste | supported | supported | PASS | yes | 1 |  | 12.9s |
| 1 | supported-packaging-threshold-assessment-005 | packaging_waste | supported | supported | PASS | yes | 1 |  | 14.3s |
| 1 | supported-packaging-evidence-retention-006 | packaging_waste | supported | supported | PASS | yes | 1 |  | 14.2s |
| 1 | too-vague-vat-evidence-001 | vat | too_vague | too_vague | PASS | yes | 1 |  | 15.5s |
| 1 | too-vague-vat-business-use-002 | vat | too_vague | too_vague | PASS | yes | 1 |  | 12.9s |
| 1 | too-vague-vat-rate-change-003 | vat | too_vague | too_vague | PASS | yes | 1 |  | 14.4s |
| 1 | too-vague-packaging-material-004 | packaging_waste | too_vague | too_vague | PASS | yes | 1 |  | 16.6s |
| 1 | too-vague-packaging-threshold-005 | packaging_waste | too_vague | missing_detail | FAIL | yes | 1 |  | 16.8s |
| 1 | too-vague-packaging-evidence-006 | packaging_waste | too_vague | too_vague | PASS | yes | 1 |  | 14.0s |
| 1 | missing-obligation-vat-input-tax-evidence-001 | vat | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.3s |
| 1 | missing-obligation-vat-mixed-use-002 | vat | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | missing-obligation-vat-credit-note-003 | vat | missing_obligation | not_related | FAIL | yes | 1 |  | 14.7s |
| 1 | missing-obligation-packaging-threshold-004 | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | missing-obligation-packaging-deadline-005 | packaging_waste | missing_obligation | missing_detail | FAIL | yes | 1 |  | 22.5s |
| 1 | missing-obligation-packaging-evidence-006 | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | missing-detail-vat-retail-invoice-exception-001 | vat | missing_detail | missing_detail | PASS | yes | 1 |  | 15.0s |
| 1 | missing-detail-vat-import-evidence-002 | vat | missing_detail | missing_detail | PASS | yes | 1 |  | 14.0s |
| 1 | missing-detail-vat-rate-change-correction-003 | vat | missing_detail | missing_detail | PASS | yes | 1 |  | 14.0s |
| 1 | missing-detail-packaging-material-categories-004 | packaging_waste | missing_detail | not_related | FAIL | yes | 1 |  | 10.2s |
| 1 | missing-detail-packaging-household-scope-005 | packaging_waste | missing_detail | missing_detail | PASS | yes | 1 |  | 15.8s |
| 1 | missing-detail-packaging-reusable-006 | packaging_waste | missing_detail | not_related | FAIL | yes | 1 |  | 17.9s |
| 1 | not-related-vat-supply-flexibility-lists-001 | vat | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | not-related-vat-private-use-list-use-case-002 | vat | not_related | not_related | PASS | yes | 1 |  | 13.4s |
| 1 | not-related-vat-rate-change-parameter-003 | vat | not_related | not_related | PASS | yes | 1 |  | 17.0s |
| 1 | not-related-packaging-supplier-contract-004 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | not-related-packaging-age-restricted-005 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | not-related-packaging-scheduling-006 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | vat-contradiction-retention-delete-001 | vat | contradiction | contradiction | PASS | yes | 1 |  | 13.3s |
| 2 | vat-contradiction-retention-not-required-002 | vat | contradiction | contradiction | PASS | yes | 1 |  | 17.5s |
| 2 | vat-contradiction-rate-change-old-rate-003 | vat | contradiction | contradiction | PASS | yes | 1 |  | 14.1s |
| 2 | vat-contradiction-rate-change-new-rate-004 | vat | contradiction | contradiction | PASS | yes | 1 |  | 14.2s |
| 2 | vat-contradiction-private-use-005 | vat | contradiction | contradiction | PASS | yes | 1 |  | 16.8s |
| 2 | packaging-contradiction-third-party-shipping-006 | packaging_waste | contradiction | supported | FAIL | yes | 1 |  | 18.1s |
| 2 | packaging-contradiction-supplier-purchased-007 | packaging_waste | contradiction | contradiction | PASS | yes | 1 |  | 12.6s |
| 2 | packaging-contradiction-delete-evidence-008 | packaging_waste | contradiction | contradiction | PASS | yes | 1 |  | 13.0s |
| 2 | supported-vat-private-use-percentage-001 | vat | supported | supported | PASS | yes | 1 |  | 11.7s |
| 2 | supported-vat-evidence-retention-002 | vat | supported | supported | PASS | yes | 1 |  | 14.4s |
| 2 | supported-vat-rate-change-003 | vat | supported | supported | PASS | yes | 1 |  | 16.1s |
| 2 | supported-packaging-material-split-004 | packaging_waste | supported | supported | PASS | yes | 1 |  | 12.9s |
| 2 | supported-packaging-threshold-assessment-005 | packaging_waste | supported | supported | PASS | yes | 1 |  | 14.2s |
| 2 | supported-packaging-evidence-retention-006 | packaging_waste | supported | supported | PASS | yes | 1 |  | 14.3s |
| 2 | too-vague-vat-evidence-001 | vat | too_vague | too_vague | PASS | yes | 1 |  | 15.5s |
| 2 | too-vague-vat-business-use-002 | vat | too_vague | too_vague | PASS | yes | 1 |  | 13.1s |
| 2 | too-vague-vat-rate-change-003 | vat | too_vague | too_vague | PASS | yes | 1 |  | 14.5s |
| 2 | too-vague-packaging-material-004 | packaging_waste | too_vague | too_vague | PASS | yes | 1 |  | 16.6s |
| 2 | too-vague-packaging-threshold-005 | packaging_waste | too_vague | missing_detail | FAIL | yes | 1 |  | 17.0s |
| 2 | too-vague-packaging-evidence-006 | packaging_waste | too_vague | too_vague | PASS | yes | 1 |  | 14.6s |
| 2 | missing-obligation-vat-input-tax-evidence-001 | vat | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | missing-obligation-vat-mixed-use-002 | vat | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | missing-obligation-vat-credit-note-003 | vat | missing_obligation | not_related | FAIL | yes | 1 |  | 15.5s |
| 2 | missing-obligation-packaging-threshold-004 | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | missing-obligation-packaging-deadline-005 | packaging_waste | missing_obligation | missing_detail | FAIL | yes | 1 |  | 23.9s |
| 2 | missing-obligation-packaging-evidence-006 | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | missing-detail-vat-retail-invoice-exception-001 | vat | missing_detail | missing_detail | PASS | yes | 1 |  | 16.4s |
| 2 | missing-detail-vat-import-evidence-002 | vat | missing_detail | missing_detail | PASS | yes | 1 |  | 15.3s |
| 2 | missing-detail-vat-rate-change-correction-003 | vat | missing_detail | missing_detail | PASS | yes | 1 |  | 15.2s |
| 2 | missing-detail-packaging-material-categories-004 | packaging_waste | missing_detail | not_related | FAIL | yes | 1 |  | 11.2s |
| 2 | missing-detail-packaging-household-scope-005 | packaging_waste | missing_detail | missing_detail | PASS | yes | 1 |  | 17.2s |
| 2 | missing-detail-packaging-reusable-006 | packaging_waste | missing_detail | not_related | FAIL | yes | 1 |  | 19.0s |
| 2 | not-related-vat-supply-flexibility-lists-001 | vat | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | not-related-vat-private-use-list-use-case-002 | vat | not_related | not_related | PASS | yes | 1 |  | 14.2s |
| 2 | not-related-vat-rate-change-parameter-003 | vat | not_related | not_related | PASS | yes | 1 |  | 18.6s |
| 2 | not-related-packaging-supplier-contract-004 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | not-related-packaging-age-restricted-005 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | not-related-packaging-scheduling-006 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | vat-contradiction-retention-delete-001 | vat | contradiction | contradiction | PASS | yes | 1 |  | 14.5s |
| 3 | vat-contradiction-retention-not-required-002 | vat | contradiction | contradiction | PASS | yes | 1 |  | 19.1s |
| 3 | vat-contradiction-rate-change-old-rate-003 | vat | contradiction | contradiction | PASS | yes | 1 |  | 15.4s |
| 3 | vat-contradiction-rate-change-new-rate-004 | vat | contradiction | contradiction | PASS | yes | 1 |  | 15.5s |
| 3 | vat-contradiction-private-use-005 | vat | contradiction | contradiction | PASS | yes | 1 |  | 17.8s |
| 3 | packaging-contradiction-third-party-shipping-006 | packaging_waste | contradiction | supported | FAIL | yes | 1 |  | 19.2s |
| 3 | packaging-contradiction-supplier-purchased-007 | packaging_waste | contradiction | contradiction | PASS | yes | 1 |  | 13.4s |
| 3 | packaging-contradiction-delete-evidence-008 | packaging_waste | contradiction | contradiction | PASS | yes | 1 |  | 13.9s |
| 3 | supported-vat-private-use-percentage-001 | vat | supported | supported | PASS | yes | 1 |  | 12.5s |
| 3 | supported-vat-evidence-retention-002 | vat | supported | supported | PASS | yes | 1 |  | 15.3s |
| 3 | supported-vat-rate-change-003 | vat | supported | supported | PASS | yes | 1 |  | 17.0s |
| 3 | supported-packaging-material-split-004 | packaging_waste | supported | supported | PASS | yes | 1 |  | 13.7s |
| 3 | supported-packaging-threshold-assessment-005 | packaging_waste | supported | supported | PASS | yes | 1 |  | 15.2s |
| 3 | supported-packaging-evidence-retention-006 | packaging_waste | supported | supported | PASS | yes | 1 |  | 15.1s |
| 3 | too-vague-vat-evidence-001 | vat | too_vague | too_vague | PASS | yes | 1 |  | 16.4s |
| 3 | too-vague-vat-business-use-002 | vat | too_vague | too_vague | PASS | yes | 1 |  | 13.7s |
| 3 | too-vague-vat-rate-change-003 | vat | too_vague | too_vague | PASS | yes | 1 |  | 15.3s |
| 3 | too-vague-packaging-material-004 | packaging_waste | too_vague | too_vague | PASS | yes | 1 |  | 17.7s |
| 3 | too-vague-packaging-threshold-005 | packaging_waste | too_vague | missing_detail | FAIL | yes | 1 |  | 17.8s |
| 3 | too-vague-packaging-evidence-006 | packaging_waste | too_vague | too_vague | PASS | yes | 1 |  | 14.9s |
| 3 | missing-obligation-vat-input-tax-evidence-001 | vat | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | missing-obligation-vat-mixed-use-002 | vat | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | missing-obligation-vat-credit-note-003 | vat | missing_obligation | not_related | FAIL | yes | 1 |  | 15.7s |
| 3 | missing-obligation-packaging-threshold-004 | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | missing-obligation-packaging-deadline-005 | packaging_waste | missing_obligation | missing_detail | FAIL | yes | 1 |  | 24.0s |
| 3 | missing-obligation-packaging-evidence-006 | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | missing-detail-vat-retail-invoice-exception-001 | vat | missing_detail | missing_detail | PASS | yes | 1 |  | 16.3s |
| 3 | missing-detail-vat-import-evidence-002 | vat | missing_detail | missing_detail | PASS | yes | 1 |  | 15.2s |
| 3 | missing-detail-vat-rate-change-correction-003 | vat | missing_detail | missing_detail | PASS | yes | 1 |  | 15.2s |
| 3 | missing-detail-packaging-material-categories-004 | packaging_waste | missing_detail | not_related | FAIL | yes | 1 |  | 11.1s |
| 3 | missing-detail-packaging-household-scope-005 | packaging_waste | missing_detail | missing_detail | PASS | yes | 1 |  | 17.4s |
| 3 | missing-detail-packaging-reusable-006 | packaging_waste | missing_detail | not_related | FAIL | yes | 1 |  | 19.3s |
| 3 | not-related-vat-supply-flexibility-lists-001 | vat | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | not-related-vat-private-use-list-use-case-002 | vat | not_related | not_related | PASS | yes | 1 |  | 14.4s |
| 3 | not-related-vat-rate-change-parameter-003 | vat | not_related | not_related | PASS | yes | 1 |  | 18.9s |
| 3 | not-related-packaging-supplier-contract-004 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | not-related-packaging-age-restricted-005 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | not-related-packaging-scheduling-006 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |