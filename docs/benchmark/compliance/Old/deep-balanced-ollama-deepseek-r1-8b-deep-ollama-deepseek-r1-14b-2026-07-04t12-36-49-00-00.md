# Compliance Reasoning Evaluation - 144/150 passed (96%)

Generated: 2026-07-04T12:36:49+00:00
Depth: deep
Model profile: balanced=ollama:deepseek-r1:8b;deep=ollama:deepseek-r1:14b
Runs: 3
Fake generator: False
Throttle deep: False
Safety gates disabled: False
Semantic candidate threshold: 0.58

Total runtime: 1941.3s
Mean pair latency: 12.9s
P95 pair latency: 19.3s
Mean LLM-called latency: 13.5s
Mean deterministic latency: 0.0s

## Per-Class Metrics

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| contradiction | 100% | 92% | 96% | 36 |
| missing_obligation | 86% | 100% | 92% | 18 |
| missing_detail | 86% | 100% | 92% | 18 |
| too_vague | 100% | 100% | 100% | 18 |
| supported | 100% | 90% | 95% | 30 |
| not_related | 100% | 100% | 100% | 30 |

## Split Metrics

| Split | Passed | Accuracy | LLM Coverage | not_related Recall | Contradiction Precision |
|---|---:|---:|---:|---:|---:|
| holdout | 30/36 | 83% | 92% | 100% | 100% |
| in_domain | 114/114 | 100% | 97% | 100% | 100% |

## Confusion Matrix

| Expected \ Actual | contradiction | missing_obligation | missing_detail | too_vague | supported | not_related |
|---|---:|---:|---:|---:|---:|---:|
| contradiction | 33 | 3 | 0 | 0 | 0 | 0 |
| missing_obligation | 0 | 18 | 0 | 0 | 0 | 0 |
| missing_detail | 0 | 0 | 18 | 0 | 0 | 0 |
| too_vague | 0 | 0 | 0 | 18 | 0 | 0 |
| supported | 0 | 0 | 3 | 0 | 27 | 0 |
| not_related | 0 | 0 | 0 | 0 | 0 | 30 |

## Observability

Rows that called the LLM: 144/150
Adjudicator coverage: 96%
Never adjudicated rows: 6
Candidate comparisons: 147
Total candidate count: 117
Lexical candidates: 63
Anchor-rescued candidates: 96
Semantic-rescued candidates: 9
Semantic attempts: 39
Semantic score distribution: n=39, min=0.34, median=0.50, p90=0.69, max=0.70
Embedding errors: 0
Same-obligation screen calls: 27
Same-obligation screen passes: 0
Same-obligation screen rejects: 27
Same-obligation screen errors: 0
Same-obligation screen fallback-to-primary calls: 0
Same-obligation screen polarity overrides: 0
Same-obligation screen latency: 159.2s
Total adjudication calls: 117
No-candidate not-related resolutions: 24
Rejected candidate findings retained: 6

| Expected class | Never adjudicated |
|---|---:|
| contradiction | 0 |
| missing_obligation | 3 |
| missing_detail | 0 |
| too_vague | 0 |
| supported | 0 |
| not_related | 3 |

### Gate Demotions

| Reason | Count |
|---|---:|
| direct_conflict_guard:needs_human_review->contradiction:classification_changed | 3 |
| direct_conflict_guard:missing_detail->contradiction:classification_changed | 6 |
| class_boundary_guard:not_related->too_vague:classification_changed | 3 |
| class_boundary_guard:not_related->missing_obligation:classification_changed | 9 |
| class_boundary_guard:too_vague->missing_detail:classification_changed | 3 |
| class_boundary_guard:not_related->missing_detail:classification_changed | 9 |
| direct_conflict_guard:not_related->contradiction:classification_changed | 3 |

### Same-Obligation Screen Errors

| Error | Count |
|---|---:|
| none | 0 |

### No-Candidate Resolutions

| Resolution | Count |
|---|---:|
| fallback_missing_obligation | 3 |
| screen_rejected_missing_obligation | 6 |
| screen_rejected_not_related | 21 |
| not_related | 3 |

### Decision Classes

| Decision class | Model | Final | Accepted | Rejected |
|---|---:|---:|---:|---:|
| contradiction | 21 | 33 | 33 | 0 |
| missing_detail | 15 | 21 | 21 | 0 |
| missing_obligation | 3 | 12 | 0 | 0 |
| needs_human_review | 3 | 0 | 0 | 0 |
| not_related | 30 | 6 | 0 | 6 |
| supported | 27 | 27 | 27 | 0 |
| too_vague | 18 | 18 | 18 | 0 |

## Prompt Context

Prompt calls observed: 117
Mean prompt-token estimate: 1187
Max prompt-token estimate: 1237
Near context limit prompts: 0
Context warning threshold: 80% of num_ctx

## Stability

Labels with classification flips: 0/50
Classification variance: 0%

## Pair Results

| Run | ID | Split | Domain | Expected | Actual | Pass | LLM | Candidates | Screen | Candidate sources | Max semantic | Resolution/Gate | Latency |
|---:|---|---|---|---|---|:--:|:--:|---:|---:|---|---:|---|---:|
| 1 | vat-contradiction-retention-delete-001 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | direct_conflict_guard:needs_human_review->contradiction:classification_changed | 23.1s |
| 1 | vat-contradiction-retention-not-required-002 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.8s |
| 1 | vat-contradiction-rate-change-old-rate-003 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 | direct_conflict_guard:missing_detail->contradiction:classification_changed | 16.2s |
| 1 | vat-contradiction-rate-change-new-rate-004 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.5s |
| 1 | vat-contradiction-private-use-005 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 14.4s |
| 1 | packaging-contradiction-third-party-shipping-006 | in_domain | packaging_waste | contradiction | contradiction | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 11.8s |
| 1 | packaging-contradiction-supplier-purchased-007 | in_domain | packaging_waste | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 12.0s |
| 1 | packaging-contradiction-delete-evidence-008 | in_domain | packaging_waste | contradiction | contradiction | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.9s |
| 1 | supported-vat-private-use-percentage-001 | in_domain | vat | supported | supported | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 12.7s |
| 1 | supported-vat-evidence-retention-002 | in_domain | vat | supported | supported | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.0s |
| 1 | supported-vat-rate-change-003 | in_domain | vat | supported | supported | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 11.9s |
| 1 | supported-packaging-material-split-004 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.8s |
| 1 | supported-packaging-threshold-assessment-005 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.1s |
| 1 | supported-packaging-evidence-retention-006 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 15.5s |
| 1 | too-vague-vat-evidence-001 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 14.0s |
| 1 | too-vague-vat-business-use-002 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 15.5s |
| 1 | too-vague-vat-rate-change-003 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 16.3s |
| 1 | too-vague-packaging-material-004 | in_domain | packaging_waste | too_vague | too_vague | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->too_vague:classification_changed | 12.6s |
| 1 | too-vague-packaging-threshold-005 | in_domain | packaging_waste | too_vague | too_vague | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 16.0s |
| 1 | too-vague-packaging-evidence-006 | in_domain | packaging_waste | too_vague | too_vague | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 16.0s |
| 1 | missing-obligation-vat-input-tax-evidence-001 | in_domain | vat | missing_obligation | missing_obligation | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 15.8s |
| 1 | missing-obligation-vat-mixed-use-002 | in_domain | vat | missing_obligation | missing_obligation | PASS | no | 0 | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 1 | missing-obligation-vat-credit-note-003 | in_domain | vat | missing_obligation | missing_obligation | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 13.5s |
| 1 | missing-obligation-packaging-threshold-004 | in_domain | packaging_waste | missing_obligation | missing_obligation | PASS | yes | 0 | 1 | L0/A0/S0 | 0.50 | screen_rejected_missing_obligation | 9.3s |
| 1 | missing-obligation-packaging-deadline-005 | in_domain | packaging_waste | missing_obligation | missing_obligation | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 15.5s |
| 1 | missing-obligation-packaging-evidence-006 | in_domain | packaging_waste | missing_obligation | missing_obligation | PASS | yes | 0 | 1 | L0/A0/S0 | 0.57 | screen_rejected_missing_obligation | 6.2s |
| 1 | missing-detail-vat-retail-invoice-exception-001 | in_domain | vat | missing_detail | missing_detail | PASS | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 15.6s |
| 1 | missing-detail-vat-import-evidence-002 | in_domain | vat | missing_detail | missing_detail | PASS | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 14.2s |
| 1 | missing-detail-vat-rate-change-correction-003 | in_domain | vat | missing_detail | missing_detail | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:too_vague->missing_detail:classification_changed | 20.3s |
| 1 | missing-detail-packaging-material-categories-004 | in_domain | packaging_waste | missing_detail | missing_detail | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 12.2s |
| 1 | missing-detail-packaging-household-scope-005 | in_domain | packaging_waste | missing_detail | missing_detail | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 17.3s |
| 1 | missing-detail-packaging-reusable-006 | in_domain | packaging_waste | missing_detail | missing_detail | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 18.1s |
| 1 | not-related-vat-supply-flexibility-lists-001 | in_domain | vat | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.4s |
| 1 | not-related-vat-private-use-list-use-case-002 | in_domain | vat | not_related | not_related | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 16.1s |
| 1 | not-related-vat-rate-change-parameter-003 | in_domain | vat | not_related | not_related | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 11.0s |
| 1 | not-related-packaging-supplier-contract-004 | in_domain | packaging_waste | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.53 | screen_rejected_not_related | 5.0s |
| 1 | not-related-packaging-age-restricted-005 | in_domain | packaging_waste | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 5.1s |
| 1 | not-related-packaging-scheduling-006 | in_domain | packaging_waste | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.55 | screen_rejected_not_related | 5.8s |
| 1 | holdout-bribery-contradiction-associated-persons-001 | holdout | bribery_holdout | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A0/S1 | 0.70 |  | 15.8s |
| 1 | holdout-bribery-contradiction-employee-only-002 | holdout | bribery_holdout | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A0/S1 | 0.62 | direct_conflict_guard:missing_detail->contradiction:classification_changed | 19.1s |
| 1 | holdout-bribery-contradiction-facilitation-payment-003 | holdout | bribery_holdout | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | direct_conflict_guard:not_related->contradiction:classification_changed | 16.7s |
| 1 | holdout-bribery-contradiction-training-evidence-004 | holdout | bribery_holdout | contradiction | missing_obligation | FAIL | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 18.8s |
| 1 | holdout-bribery-supported-associated-persons-005 | holdout | bribery_holdout | supported | supported | PASS | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 16.4s |
| 1 | holdout-bribery-supported-gifts-approval-006 | holdout | bribery_holdout | supported | supported | PASS | yes | 1 | 0 | L0/A0/S1 | 0.69 |  | 15.0s |
| 1 | holdout-bribery-supported-training-007 | holdout | bribery_holdout | supported | missing_detail | FAIL | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.9s |
| 1 | holdout-bribery-supported-reporting-008 | holdout | bribery_holdout | supported | supported | PASS | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 13.8s |
| 1 | holdout-bribery-not-related-invoice-009 | holdout | bribery_holdout | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.4s |
| 1 | holdout-bribery-not-related-product-label-010 | holdout | bribery_holdout | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.44 | screen_rejected_not_related | 4.5s |
| 1 | holdout-bribery-not-related-integration-011 | holdout | bribery_holdout | not_related | not_related | PASS | no | 0 | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 1 | holdout-bribery-not-related-stock-list-012 | holdout | bribery_holdout | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.47 | screen_rejected_not_related | 5.7s |
| 2 | vat-contradiction-retention-delete-001 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | direct_conflict_guard:needs_human_review->contradiction:classification_changed | 16.4s |
| 2 | vat-contradiction-retention-not-required-002 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.9s |
| 2 | vat-contradiction-rate-change-old-rate-003 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 | direct_conflict_guard:missing_detail->contradiction:classification_changed | 16.3s |
| 2 | vat-contradiction-rate-change-new-rate-004 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.3s |
| 2 | vat-contradiction-private-use-005 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 14.1s |
| 2 | packaging-contradiction-third-party-shipping-006 | in_domain | packaging_waste | contradiction | contradiction | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 11.7s |
| 2 | packaging-contradiction-supplier-purchased-007 | in_domain | packaging_waste | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 11.9s |
| 2 | packaging-contradiction-delete-evidence-008 | in_domain | packaging_waste | contradiction | contradiction | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.7s |
| 2 | supported-vat-private-use-percentage-001 | in_domain | vat | supported | supported | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 12.9s |
| 2 | supported-vat-evidence-retention-002 | in_domain | vat | supported | supported | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.3s |
| 2 | supported-vat-rate-change-003 | in_domain | vat | supported | supported | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.2s |
| 2 | supported-packaging-material-split-004 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.2s |
| 2 | supported-packaging-threshold-assessment-005 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.5s |
| 2 | supported-packaging-evidence-retention-006 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 15.9s |
| 2 | too-vague-vat-evidence-001 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 14.3s |
| 2 | too-vague-vat-business-use-002 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 15.9s |
| 2 | too-vague-vat-rate-change-003 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 16.8s |
| 2 | too-vague-packaging-material-004 | in_domain | packaging_waste | too_vague | too_vague | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->too_vague:classification_changed | 13.0s |
| 2 | too-vague-packaging-threshold-005 | in_domain | packaging_waste | too_vague | too_vague | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 16.4s |
| 2 | too-vague-packaging-evidence-006 | in_domain | packaging_waste | too_vague | too_vague | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 16.5s |
| 2 | missing-obligation-vat-input-tax-evidence-001 | in_domain | vat | missing_obligation | missing_obligation | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 16.1s |
| 2 | missing-obligation-vat-mixed-use-002 | in_domain | vat | missing_obligation | missing_obligation | PASS | no | 0 | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 2 | missing-obligation-vat-credit-note-003 | in_domain | vat | missing_obligation | missing_obligation | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 13.8s |
| 2 | missing-obligation-packaging-threshold-004 | in_domain | packaging_waste | missing_obligation | missing_obligation | PASS | yes | 0 | 1 | L0/A0/S0 | 0.50 | screen_rejected_missing_obligation | 6.6s |
| 2 | missing-obligation-packaging-deadline-005 | in_domain | packaging_waste | missing_obligation | missing_obligation | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 15.8s |
| 2 | missing-obligation-packaging-evidence-006 | in_domain | packaging_waste | missing_obligation | missing_obligation | PASS | yes | 0 | 1 | L0/A0/S0 | 0.57 | screen_rejected_missing_obligation | 6.3s |
| 2 | missing-detail-vat-retail-invoice-exception-001 | in_domain | vat | missing_detail | missing_detail | PASS | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 16.2s |
| 2 | missing-detail-vat-import-evidence-002 | in_domain | vat | missing_detail | missing_detail | PASS | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 14.7s |
| 2 | missing-detail-vat-rate-change-correction-003 | in_domain | vat | missing_detail | missing_detail | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:too_vague->missing_detail:classification_changed | 21.0s |
| 2 | missing-detail-packaging-material-categories-004 | in_domain | packaging_waste | missing_detail | missing_detail | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 12.6s |
| 2 | missing-detail-packaging-household-scope-005 | in_domain | packaging_waste | missing_detail | missing_detail | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 17.9s |
| 2 | missing-detail-packaging-reusable-006 | in_domain | packaging_waste | missing_detail | missing_detail | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 18.7s |
| 2 | not-related-vat-supply-flexibility-lists-001 | in_domain | vat | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.6s |
| 2 | not-related-vat-private-use-list-use-case-002 | in_domain | vat | not_related | not_related | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 16.8s |
| 2 | not-related-vat-rate-change-parameter-003 | in_domain | vat | not_related | not_related | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 11.5s |
| 2 | not-related-packaging-supplier-contract-004 | in_domain | packaging_waste | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.53 | screen_rejected_not_related | 5.2s |
| 2 | not-related-packaging-age-restricted-005 | in_domain | packaging_waste | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 5.3s |
| 2 | not-related-packaging-scheduling-006 | in_domain | packaging_waste | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.55 | screen_rejected_not_related | 6.1s |
| 2 | holdout-bribery-contradiction-associated-persons-001 | holdout | bribery_holdout | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A0/S1 | 0.70 |  | 16.5s |
| 2 | holdout-bribery-contradiction-employee-only-002 | holdout | bribery_holdout | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A0/S1 | 0.62 | direct_conflict_guard:missing_detail->contradiction:classification_changed | 20.1s |
| 2 | holdout-bribery-contradiction-facilitation-payment-003 | holdout | bribery_holdout | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | direct_conflict_guard:not_related->contradiction:classification_changed | 17.5s |
| 2 | holdout-bribery-contradiction-training-evidence-004 | holdout | bribery_holdout | contradiction | missing_obligation | FAIL | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 19.7s |
| 2 | holdout-bribery-supported-associated-persons-005 | holdout | bribery_holdout | supported | supported | PASS | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 17.2s |
| 2 | holdout-bribery-supported-gifts-approval-006 | holdout | bribery_holdout | supported | supported | PASS | yes | 1 | 0 | L0/A0/S1 | 0.69 |  | 15.7s |
| 2 | holdout-bribery-supported-training-007 | holdout | bribery_holdout | supported | missing_detail | FAIL | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 14.5s |
| 2 | holdout-bribery-supported-reporting-008 | holdout | bribery_holdout | supported | supported | PASS | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 14.4s |
| 2 | holdout-bribery-not-related-invoice-009 | holdout | bribery_holdout | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.7s |
| 2 | holdout-bribery-not-related-product-label-010 | holdout | bribery_holdout | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.44 | screen_rejected_not_related | 4.6s |
| 2 | holdout-bribery-not-related-integration-011 | holdout | bribery_holdout | not_related | not_related | PASS | no | 0 | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 2 | holdout-bribery-not-related-stock-list-012 | holdout | bribery_holdout | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.47 | screen_rejected_not_related | 5.9s |
| 3 | vat-contradiction-retention-delete-001 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | direct_conflict_guard:needs_human_review->contradiction:classification_changed | 17.1s |
| 3 | vat-contradiction-retention-not-required-002 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.5s |
| 3 | vat-contradiction-rate-change-old-rate-003 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 | direct_conflict_guard:missing_detail->contradiction:classification_changed | 17.3s |
| 3 | vat-contradiction-rate-change-new-rate-004 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 14.1s |
| 3 | vat-contradiction-private-use-005 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 14.8s |
| 3 | packaging-contradiction-third-party-shipping-006 | in_domain | packaging_waste | contradiction | contradiction | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.2s |
| 3 | packaging-contradiction-supplier-purchased-007 | in_domain | packaging_waste | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 12.4s |
| 3 | packaging-contradiction-delete-evidence-008 | in_domain | packaging_waste | contradiction | contradiction | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 14.3s |
| 3 | supported-vat-private-use-percentage-001 | in_domain | vat | supported | supported | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 13.2s |
| 3 | supported-vat-evidence-retention-002 | in_domain | vat | supported | supported | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.6s |
| 3 | supported-vat-rate-change-003 | in_domain | vat | supported | supported | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.4s |
| 3 | supported-packaging-material-split-004 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.5s |
| 3 | supported-packaging-threshold-assessment-005 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.8s |
| 3 | supported-packaging-evidence-retention-006 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 16.3s |
| 3 | too-vague-vat-evidence-001 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 14.7s |
| 3 | too-vague-vat-business-use-002 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 16.2s |
| 3 | too-vague-vat-rate-change-003 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 16.8s |
| 3 | too-vague-packaging-material-004 | in_domain | packaging_waste | too_vague | too_vague | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->too_vague:classification_changed | 13.0s |
| 3 | too-vague-packaging-threshold-005 | in_domain | packaging_waste | too_vague | too_vague | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 16.4s |
| 3 | too-vague-packaging-evidence-006 | in_domain | packaging_waste | too_vague | too_vague | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 16.4s |
| 3 | missing-obligation-vat-input-tax-evidence-001 | in_domain | vat | missing_obligation | missing_obligation | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 16.1s |
| 3 | missing-obligation-vat-mixed-use-002 | in_domain | vat | missing_obligation | missing_obligation | PASS | no | 0 | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 3 | missing-obligation-vat-credit-note-003 | in_domain | vat | missing_obligation | missing_obligation | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 13.8s |
| 3 | missing-obligation-packaging-threshold-004 | in_domain | packaging_waste | missing_obligation | missing_obligation | PASS | yes | 0 | 1 | L0/A0/S0 | 0.50 | screen_rejected_missing_obligation | 6.4s |
| 3 | missing-obligation-packaging-deadline-005 | in_domain | packaging_waste | missing_obligation | missing_obligation | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 15.8s |
| 3 | missing-obligation-packaging-evidence-006 | in_domain | packaging_waste | missing_obligation | missing_obligation | PASS | yes | 0 | 1 | L0/A0/S0 | 0.57 | screen_rejected_missing_obligation | 6.3s |
| 3 | missing-detail-vat-retail-invoice-exception-001 | in_domain | vat | missing_detail | missing_detail | PASS | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 16.2s |
| 3 | missing-detail-vat-import-evidence-002 | in_domain | vat | missing_detail | missing_detail | PASS | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 14.7s |
| 3 | missing-detail-vat-rate-change-correction-003 | in_domain | vat | missing_detail | missing_detail | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:too_vague->missing_detail:classification_changed | 21.0s |
| 3 | missing-detail-packaging-material-categories-004 | in_domain | packaging_waste | missing_detail | missing_detail | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 12.6s |
| 3 | missing-detail-packaging-household-scope-005 | in_domain | packaging_waste | missing_detail | missing_detail | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 17.9s |
| 3 | missing-detail-packaging-reusable-006 | in_domain | packaging_waste | missing_detail | missing_detail | PASS | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 18.7s |
| 3 | not-related-vat-supply-flexibility-lists-001 | in_domain | vat | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.6s |
| 3 | not-related-vat-private-use-list-use-case-002 | in_domain | vat | not_related | not_related | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 16.6s |
| 3 | not-related-vat-rate-change-parameter-003 | in_domain | vat | not_related | not_related | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 11.4s |
| 3 | not-related-packaging-supplier-contract-004 | in_domain | packaging_waste | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.53 | screen_rejected_not_related | 5.1s |
| 3 | not-related-packaging-age-restricted-005 | in_domain | packaging_waste | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 5.2s |
| 3 | not-related-packaging-scheduling-006 | in_domain | packaging_waste | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.55 | screen_rejected_not_related | 6.0s |
| 3 | holdout-bribery-contradiction-associated-persons-001 | holdout | bribery_holdout | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A0/S1 | 0.70 |  | 16.3s |
| 3 | holdout-bribery-contradiction-employee-only-002 | holdout | bribery_holdout | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A0/S1 | 0.62 | direct_conflict_guard:missing_detail->contradiction:classification_changed | 19.7s |
| 3 | holdout-bribery-contradiction-facilitation-payment-003 | holdout | bribery_holdout | contradiction | contradiction | PASS | yes | 1 | 0 | L0/A1/S0 | 0.00 | direct_conflict_guard:not_related->contradiction:classification_changed | 17.2s |
| 3 | holdout-bribery-contradiction-training-evidence-004 | holdout | bribery_holdout | contradiction | missing_obligation | FAIL | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 19.3s |
| 3 | holdout-bribery-supported-associated-persons-005 | holdout | bribery_holdout | supported | supported | PASS | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 16.8s |
| 3 | holdout-bribery-supported-gifts-approval-006 | holdout | bribery_holdout | supported | supported | PASS | yes | 1 | 0 | L0/A0/S1 | 0.69 |  | 15.4s |
| 3 | holdout-bribery-supported-training-007 | holdout | bribery_holdout | supported | missing_detail | FAIL | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 14.3s |
| 3 | holdout-bribery-supported-reporting-008 | holdout | bribery_holdout | supported | supported | PASS | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 14.2s |
| 3 | holdout-bribery-not-related-invoice-009 | holdout | bribery_holdout | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.5s |
| 3 | holdout-bribery-not-related-product-label-010 | holdout | bribery_holdout | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.44 | screen_rejected_not_related | 4.5s |
| 3 | holdout-bribery-not-related-integration-011 | holdout | bribery_holdout | not_related | not_related | PASS | no | 0 | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 3 | holdout-bribery-not-related-stock-list-012 | holdout | bribery_holdout | not_related | not_related | PASS | yes | 0 | 1 | L0/A0/S0 | 0.47 | screen_rejected_not_related | 5.8s |