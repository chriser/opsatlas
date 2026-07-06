# Compliance Reasoning Evaluation - 234/258 passed (91%)

Generated: 2026-07-04T19:07:23+00:00
Depth: deep
Model profile: balanced=ollama:deepseek-r1:8b;deep=ollama:deepseek-r1:14b
Runs: 3
Fake generator: False
Throttle deep: False
Safety gates disabled: False
Semantic candidate threshold: 0.58

Total runtime: 3060.9s
Mean pair latency: 11.9s
P95 pair latency: 18.6s
Mean LLM-called latency: 12.6s
Mean deterministic latency: 0.0s

## Per-Class Metrics

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| contradiction | 100% | 71% | 83% | 72 |
| missing_obligation | 67% | 100% | 80% | 18 |
| missing_detail | 75% | 100% | 86% | 18 |
| too_vague | 100% | 100% | 100% | 18 |
| supported | 100% | 96% | 98% | 66 |
| not_related | 88% | 100% | 94% | 66 |
| needs_human_review | 0% | 0% | 0% | 0 |

## Split Metrics

| Split | Passed | Accuracy | LLM Coverage | not_related Recall | Contradiction Precision |
|---|---:|---:|---:|---:|---:|
| training | 207/222 | 93% | 93% | 100% | 100% |
| holdout | 27/36 | 75% | 100% | 100% | 100% |

## Guard Ablation

Model-only accuracy: 204/258 (79%)
With-guards accuracy: 234/258 (91%)
Guard-changed classifications: 42/258
Guard helped: 36
Guard hurt: 6

| Split | Model-only | With guards | Changed | Helped | Hurt |
|---|---:|---:|---:|---:|---:|
| training | 174/222 (78%) | 207/222 (93%) | 39 | 36 | 3 |
| holdout | 30/36 (83%) | 27/36 (75%) | 3 | 0 | 3 |

## Confusion Matrix

| Expected \ Actual | contradiction | missing_obligation | missing_detail | too_vague | supported | not_related | needs_human_review |
|---|---:|---:|---:|---:|---:|---:|---:|
| contradiction | 51 | 9 | 3 | 0 | 0 | 9 | 0 |
| missing_obligation | 0 | 18 | 0 | 0 | 0 | 0 | 0 |
| missing_detail | 0 | 0 | 18 | 0 | 0 | 0 | 0 |
| too_vague | 0 | 0 | 0 | 18 | 0 | 0 | 0 |
| supported | 0 | 0 | 3 | 0 | 63 | 0 | 0 |
| not_related | 0 | 0 | 0 | 0 | 0 | 66 | 0 |
| needs_human_review | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Observability

Rows that called the LLM: 243/258
Adjudicator coverage: 94%
Never adjudicated rows: 15
Candidate comparisons: 252
Total candidate count: 186
Lexical candidates: 105
Anchor-rescued candidates: 99
Semantic-rescued candidates: 36
Semantic attempts: 102
Semantic score distribution: n=102, min=0.34, median=0.52, p90=0.73, max=0.77
Embedding errors: 0
Same-obligation screen calls: 57
Same-obligation screen passes: 0
Same-obligation screen rejects: 57
Same-obligation screen errors: 0
Same-obligation screen fallback-to-primary calls: 0
Same-obligation screen polarity overrides: 0
Same-obligation screen latency: 302.5s
Total adjudication calls: 186
No-candidate not-related resolutions: 60
Rejected candidate findings retained: 15

| Expected class | Never adjudicated |
|---|---:|
| contradiction | 3 |
| missing_obligation | 3 |
| missing_detail | 0 |
| too_vague | 0 |
| supported | 0 |
| not_related | 9 |
| needs_human_review | 0 |

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
| contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 6 |

### Same-Obligation Screen Errors

| Error | Count |
|---|---:|
| none | 0 |

### No-Candidate Resolutions

| Resolution | Count |
|---|---:|
| fallback_missing_obligation | 6 |
| screen_rejected_missing_obligation | 6 |
| screen_rejected_not_related | 51 |
| not_related | 9 |

### Decision Classes

| Decision class | Model | Final | Accepted | Rejected |
|---|---:|---:|---:|---:|
| contradiction | 45 | 51 | 51 | 0 |
| missing_detail | 18 | 24 | 24 | 0 |
| missing_obligation | 6 | 15 | 0 | 0 |
| needs_human_review | 3 | 0 | 0 | 0 |
| not_related | 33 | 15 | 0 | 15 |
| supported | 63 | 63 | 63 | 0 |
| too_vague | 18 | 18 | 18 | 0 |

## Prompt Context

Prompt calls observed: 186
Mean prompt-token estimate: 1188
Max prompt-token estimate: 1237
Near context limit prompts: 0
Context warning threshold: 80% of num_ctx

## Stability

Labels with classification flips: 0/86
Classification variance: 0%

## Pair Results

| Run | ID | Split | Domain | Expected | Model-only | Actual | Pass | Guard | LLM | Candidates | Screen | Candidate sources | Max semantic | Resolution/Gate | Latency |
|---:|---|---|---|---|---|---|:--:|:--:|:--:|---:|---:|---|---:|---|---:|
| 1 | vat-contradiction-retention-delete-001 | training | vat | contradiction | needs_human_review | contradiction | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | direct_conflict_guard:needs_human_review->contradiction:classification_changed | 21.4s |
| 1 | vat-contradiction-retention-not-required-002 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.3s |
| 1 | vat-contradiction-rate-change-old-rate-003 | training | vat | contradiction | missing_detail | contradiction | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | direct_conflict_guard:missing_detail->contradiction:classification_changed | 15.6s |
| 1 | vat-contradiction-rate-change-new-rate-004 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.8s |
| 1 | vat-contradiction-private-use-005 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 13.6s |
| 1 | packaging-contradiction-third-party-shipping-006 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 11.3s |
| 1 | packaging-contradiction-supplier-purchased-007 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 11.5s |
| 1 | packaging-contradiction-delete-evidence-008 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.3s |
| 1 | supported-vat-private-use-percentage-001 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 12.3s |
| 1 | supported-vat-evidence-retention-002 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.7s |
| 1 | supported-vat-rate-change-003 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 11.5s |
| 1 | supported-packaging-material-split-004 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.5s |
| 1 | supported-packaging-threshold-assessment-005 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.8s |
| 1 | supported-packaging-evidence-retention-006 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 15.2s |
| 1 | too-vague-vat-evidence-001 | training | vat | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.7s |
| 1 | too-vague-vat-business-use-002 | training | vat | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 15.1s |
| 1 | too-vague-vat-rate-change-003 | training | vat | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 16.0s |
| 1 | too-vague-packaging-material-004 | training | packaging_waste | too_vague | not_related | too_vague | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->too_vague:classification_changed | 12.3s |
| 1 | too-vague-packaging-threshold-005 | training | packaging_waste | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 15.5s |
| 1 | too-vague-packaging-evidence-006 | training | packaging_waste | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 15.4s |
| 1 | missing-obligation-vat-input-tax-evidence-001 | training | vat | missing_obligation | not_related | missing_obligation | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 15.2s |
| 1 | missing-obligation-vat-mixed-use-002 | training | vat | missing_obligation | missing_obligation | missing_obligation | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 1 | missing-obligation-vat-credit-note-003 | training | vat | missing_obligation | not_related | missing_obligation | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 13.0s |
| 1 | missing-obligation-packaging-threshold-004 | training | packaging_waste | missing_obligation | missing_obligation | missing_obligation | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.50 | screen_rejected_missing_obligation | 8.3s |
| 1 | missing-obligation-packaging-deadline-005 | training | packaging_waste | missing_obligation | not_related | missing_obligation | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 14.9s |
| 1 | missing-obligation-packaging-evidence-006 | training | packaging_waste | missing_obligation | missing_obligation | missing_obligation | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.57 | screen_rejected_missing_obligation | 6.0s |
| 1 | missing-detail-vat-retail-invoice-exception-001 | training | vat | missing_detail | missing_detail | missing_detail | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 15.2s |
| 1 | missing-detail-vat-import-evidence-002 | training | vat | missing_detail | missing_detail | missing_detail | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 13.8s |
| 1 | missing-detail-vat-rate-change-correction-003 | training | vat | missing_detail | too_vague | missing_detail | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:too_vague->missing_detail:classification_changed | 19.9s |
| 1 | missing-detail-packaging-material-categories-004 | training | packaging_waste | missing_detail | not_related | missing_detail | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 12.0s |
| 1 | missing-detail-packaging-household-scope-005 | training | packaging_waste | missing_detail | not_related | missing_detail | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 17.0s |
| 1 | missing-detail-packaging-reusable-006 | training | packaging_waste | missing_detail | not_related | missing_detail | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 28.8s |
| 1 | not-related-vat-supply-flexibility-lists-001 | training | vat | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.2s |
| 1 | not-related-vat-private-use-list-use-case-002 | training | vat | not_related | not_related | not_related | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 16.3s |
| 1 | not-related-vat-rate-change-parameter-003 | training | vat | not_related | not_related | not_related | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 10.8s |
| 1 | not-related-packaging-supplier-contract-004 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.53 | screen_rejected_not_related | 4.8s |
| 1 | not-related-packaging-age-restricted-005 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 5.0s |
| 1 | not-related-packaging-scheduling-006 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.55 | screen_rejected_not_related | 5.7s |
| 1 | holdout-bribery-contradiction-associated-persons-001 | training | bribery_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.70 |  | 15.5s |
| 1 | holdout-bribery-contradiction-employee-only-002 | training | bribery_holdout | contradiction | missing_detail | contradiction | PASS | yes | yes | 1 | 0 | L0/A0/S1 | 0.62 | direct_conflict_guard:missing_detail->contradiction:classification_changed | 18.8s |
| 1 | holdout-bribery-contradiction-facilitation-payment-003 | training | bribery_holdout | contradiction | not_related | contradiction | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | direct_conflict_guard:not_related->contradiction:classification_changed | 16.4s |
| 1 | holdout-bribery-contradiction-training-evidence-004 | training | bribery_holdout | contradiction | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 18.4s |
| 1 | holdout-bribery-supported-associated-persons-005 | training | bribery_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 15.9s |
| 1 | holdout-bribery-supported-gifts-approval-006 | training | bribery_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.69 |  | 14.5s |
| 1 | holdout-bribery-supported-training-007 | training | bribery_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.4s |
| 1 | holdout-bribery-supported-reporting-008 | training | bribery_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 13.4s |
| 1 | holdout-bribery-not-related-invoice-009 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.1s |
| 1 | holdout-bribery-not-related-product-label-010 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.44 | screen_rejected_not_related | 4.3s |
| 1 | holdout-bribery-not-related-integration-011 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 1 | holdout-bribery-not-related-stock-list-012 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.47 | screen_rejected_not_related | 5.5s |
| 1 | holdout-data-protection-contradiction-dsar-delay-001 | training | data_protection_holdout | contradiction | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.75 |  | 21.7s |
| 1 | holdout-data-protection-contradiction-erasure-retention-002 | training | data_protection_holdout | contradiction | contradiction | not_related | FAIL | yes | yes | 1 | 0 | L1/A0/S0 | 0.00 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 13.7s |
| 1 | holdout-data-protection-contradiction-breach-reporting-003 | training | data_protection_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.63 |  | 13.2s |
| 1 | holdout-data-protection-contradiction-consent-withdrawal-004 | training | data_protection_holdout | contradiction | missing_obligation | missing_obligation | FAIL | no | no | 0 | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 1 | holdout-data-protection-supported-dsar-deadline-005 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 11.5s |
| 1 | holdout-data-protection-supported-erasure-purpose-006 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 12.7s |
| 1 | holdout-data-protection-supported-breach-reporting-007 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 12.1s |
| 1 | holdout-data-protection-supported-consent-withdrawal-008 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 12.4s |
| 1 | holdout-data-protection-not-related-packaging-009 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.52 | screen_rejected_not_related | 5.3s |
| 1 | holdout-data-protection-not-related-integration-010 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.51 | screen_rejected_not_related | 5.6s |
| 1 | holdout-data-protection-not-related-contracts-011 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.41 | screen_rejected_not_related | 5.3s |
| 1 | holdout-data-protection-not-related-category-012 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.40 | screen_rejected_not_related | 5.7s |
| 1 | holdout-accessibility-contradiction-captions-001 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 16.5s |
| 1 | holdout-accessibility-contradiction-alt-text-002 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.64 |  | 17.4s |
| 1 | holdout-accessibility-contradiction-keyboard-003 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.60 |  | 14.2s |
| 1 | holdout-accessibility-contradiction-error-identification-004 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.65 |  | 15.8s |
| 1 | holdout-accessibility-supported-captions-005 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 13.2s |
| 1 | holdout-accessibility-supported-alt-text-006 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 18.0s |
| 1 | holdout-accessibility-supported-keyboard-007 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.74 |  | 14.4s |
| 1 | holdout-accessibility-supported-error-identification-008 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.68 |  | 14.7s |
| 1 | holdout-accessibility-not-related-contract-numbering-009 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.42 | screen_rejected_not_related | 6.5s |
| 1 | holdout-accessibility-not-related-vat-records-010 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.39 | not_related | 0.0s |
| 1 | holdout-accessibility-not-related-packaging-weights-011 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 1 | holdout-accessibility-not-related-integration-retry-012 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.52 | screen_rejected_not_related | 5.7s |
| 1 | holdout-consumer-rights-contradiction-total-price-001 | holdout | consumer_rights_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 17.0s |
| 1 | holdout-consumer-rights-contradiction-cancellation-rights-002 | holdout | consumer_rights_holdout | contradiction | contradiction | not_related | FAIL | yes | yes | 1 | 0 | L1/A0/S0 | 0.00 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 14.8s |
| 1 | holdout-consumer-rights-contradiction-faulty-goods-003 | holdout | consumer_rights_holdout | contradiction | not_related | not_related | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.77 |  | 27.6s |
| 1 | holdout-consumer-rights-contradiction-subscription-cancel-004 | holdout | consumer_rights_holdout | contradiction | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.73 |  | 15.7s |
| 1 | holdout-consumer-rights-supported-total-price-005 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 11.9s |
| 1 | holdout-consumer-rights-supported-cancellation-rights-006 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 15.6s |
| 1 | holdout-consumer-rights-supported-faulty-goods-007 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 15.1s |
| 1 | holdout-consumer-rights-supported-subscription-cancel-008 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 12.9s |
| 1 | holdout-consumer-rights-not-related-supplier-numbering-009 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 5.2s |
| 1 | holdout-consumer-rights-not-related-vat-records-010 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.44 | screen_rejected_not_related | 5.3s |
| 1 | holdout-consumer-rights-not-related-packaging-weights-011 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 5.7s |
| 1 | holdout-consumer-rights-not-related-integration-retry-012 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 3.6s |
| 2 | vat-contradiction-retention-delete-001 | training | vat | contradiction | needs_human_review | contradiction | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | direct_conflict_guard:needs_human_review->contradiction:classification_changed | 15.7s |
| 2 | vat-contradiction-retention-not-required-002 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.4s |
| 2 | vat-contradiction-rate-change-old-rate-003 | training | vat | contradiction | missing_detail | contradiction | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | direct_conflict_guard:missing_detail->contradiction:classification_changed | 15.7s |
| 2 | vat-contradiction-rate-change-new-rate-004 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.0s |
| 2 | vat-contradiction-private-use-005 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 13.8s |
| 2 | packaging-contradiction-third-party-shipping-006 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 11.3s |
| 2 | packaging-contradiction-supplier-purchased-007 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 11.5s |
| 2 | packaging-contradiction-delete-evidence-008 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.2s |
| 2 | supported-vat-private-use-percentage-001 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 12.2s |
| 2 | supported-vat-evidence-retention-002 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.6s |
| 2 | supported-vat-rate-change-003 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 11.6s |
| 2 | supported-packaging-material-split-004 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.5s |
| 2 | supported-packaging-threshold-assessment-005 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.8s |
| 2 | supported-packaging-evidence-retention-006 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 15.1s |
| 2 | too-vague-vat-evidence-001 | training | vat | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.6s |
| 2 | too-vague-vat-business-use-002 | training | vat | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 15.1s |
| 2 | too-vague-vat-rate-change-003 | training | vat | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 15.8s |
| 2 | too-vague-packaging-material-004 | training | packaging_waste | too_vague | not_related | too_vague | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->too_vague:classification_changed | 12.2s |
| 2 | too-vague-packaging-threshold-005 | training | packaging_waste | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 15.5s |
| 2 | too-vague-packaging-evidence-006 | training | packaging_waste | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 15.7s |
| 2 | missing-obligation-vat-input-tax-evidence-001 | training | vat | missing_obligation | not_related | missing_obligation | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 15.1s |
| 2 | missing-obligation-vat-mixed-use-002 | training | vat | missing_obligation | missing_obligation | missing_obligation | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 2 | missing-obligation-vat-credit-note-003 | training | vat | missing_obligation | not_related | missing_obligation | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 12.9s |
| 2 | missing-obligation-packaging-threshold-004 | training | packaging_waste | missing_obligation | missing_obligation | missing_obligation | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.50 | screen_rejected_missing_obligation | 5.3s |
| 2 | missing-obligation-packaging-deadline-005 | training | packaging_waste | missing_obligation | not_related | missing_obligation | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 15.0s |
| 2 | missing-obligation-packaging-evidence-006 | training | packaging_waste | missing_obligation | missing_obligation | missing_obligation | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.57 | screen_rejected_missing_obligation | 3.6s |
| 2 | missing-detail-vat-retail-invoice-exception-001 | training | vat | missing_detail | missing_detail | missing_detail | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 15.2s |
| 2 | missing-detail-vat-import-evidence-002 | training | vat | missing_detail | missing_detail | missing_detail | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 13.8s |
| 2 | missing-detail-vat-rate-change-correction-003 | training | vat | missing_detail | too_vague | missing_detail | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:too_vague->missing_detail:classification_changed | 19.7s |
| 2 | missing-detail-packaging-material-categories-004 | training | packaging_waste | missing_detail | not_related | missing_detail | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 11.9s |
| 2 | missing-detail-packaging-household-scope-005 | training | packaging_waste | missing_detail | not_related | missing_detail | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 17.0s |
| 2 | missing-detail-packaging-reusable-006 | training | packaging_waste | missing_detail | not_related | missing_detail | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 17.7s |
| 2 | not-related-vat-supply-flexibility-lists-001 | training | vat | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.1s |
| 2 | not-related-vat-private-use-list-use-case-002 | training | vat | not_related | not_related | not_related | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 15.7s |
| 2 | not-related-vat-rate-change-parameter-003 | training | vat | not_related | not_related | not_related | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 10.7s |
| 2 | not-related-packaging-supplier-contract-004 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.53 | screen_rejected_not_related | 4.8s |
| 2 | not-related-packaging-age-restricted-005 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 4.9s |
| 2 | not-related-packaging-scheduling-006 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.55 | screen_rejected_not_related | 5.6s |
| 2 | holdout-bribery-contradiction-associated-persons-001 | training | bribery_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.70 |  | 15.4s |
| 2 | holdout-bribery-contradiction-employee-only-002 | training | bribery_holdout | contradiction | missing_detail | contradiction | PASS | yes | yes | 1 | 0 | L0/A0/S1 | 0.62 | direct_conflict_guard:missing_detail->contradiction:classification_changed | 18.6s |
| 2 | holdout-bribery-contradiction-facilitation-payment-003 | training | bribery_holdout | contradiction | not_related | contradiction | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | direct_conflict_guard:not_related->contradiction:classification_changed | 16.3s |
| 2 | holdout-bribery-contradiction-training-evidence-004 | training | bribery_holdout | contradiction | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 18.2s |
| 2 | holdout-bribery-supported-associated-persons-005 | training | bribery_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 15.9s |
| 2 | holdout-bribery-supported-gifts-approval-006 | training | bribery_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.69 |  | 14.5s |
| 2 | holdout-bribery-supported-training-007 | training | bribery_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.5s |
| 2 | holdout-bribery-supported-reporting-008 | training | bribery_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 13.3s |
| 2 | holdout-bribery-not-related-invoice-009 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.0s |
| 2 | holdout-bribery-not-related-product-label-010 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.44 | screen_rejected_not_related | 4.2s |
| 2 | holdout-bribery-not-related-integration-011 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 2 | holdout-bribery-not-related-stock-list-012 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.47 | screen_rejected_not_related | 5.4s |
| 2 | holdout-data-protection-contradiction-dsar-delay-001 | training | data_protection_holdout | contradiction | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.75 |  | 21.6s |
| 2 | holdout-data-protection-contradiction-erasure-retention-002 | training | data_protection_holdout | contradiction | contradiction | not_related | FAIL | yes | yes | 1 | 0 | L1/A0/S0 | 0.00 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 13.6s |
| 2 | holdout-data-protection-contradiction-breach-reporting-003 | training | data_protection_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.63 |  | 13.2s |
| 2 | holdout-data-protection-contradiction-consent-withdrawal-004 | training | data_protection_holdout | contradiction | missing_obligation | missing_obligation | FAIL | no | no | 0 | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 2 | holdout-data-protection-supported-dsar-deadline-005 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 11.5s |
| 2 | holdout-data-protection-supported-erasure-purpose-006 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 12.7s |
| 2 | holdout-data-protection-supported-breach-reporting-007 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 12.2s |
| 2 | holdout-data-protection-supported-consent-withdrawal-008 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 12.5s |
| 2 | holdout-data-protection-not-related-packaging-009 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.52 | screen_rejected_not_related | 5.3s |
| 2 | holdout-data-protection-not-related-integration-010 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.51 | screen_rejected_not_related | 5.6s |
| 2 | holdout-data-protection-not-related-contracts-011 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.41 | screen_rejected_not_related | 5.2s |
| 2 | holdout-data-protection-not-related-category-012 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.40 | screen_rejected_not_related | 5.6s |
| 2 | holdout-accessibility-contradiction-captions-001 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 16.3s |
| 2 | holdout-accessibility-contradiction-alt-text-002 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.64 |  | 17.2s |
| 2 | holdout-accessibility-contradiction-keyboard-003 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.60 |  | 13.9s |
| 2 | holdout-accessibility-contradiction-error-identification-004 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.65 |  | 15.5s |
| 2 | holdout-accessibility-supported-captions-005 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 13.1s |
| 2 | holdout-accessibility-supported-alt-text-006 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 18.8s |
| 2 | holdout-accessibility-supported-keyboard-007 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.74 |  | 14.0s |
| 2 | holdout-accessibility-supported-error-identification-008 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.68 |  | 14.5s |
| 2 | holdout-accessibility-not-related-contract-numbering-009 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.42 | screen_rejected_not_related | 6.4s |
| 2 | holdout-accessibility-not-related-vat-records-010 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.39 | not_related | 0.0s |
| 2 | holdout-accessibility-not-related-packaging-weights-011 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 2 | holdout-accessibility-not-related-integration-retry-012 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.52 | screen_rejected_not_related | 5.5s |
| 2 | holdout-consumer-rights-contradiction-total-price-001 | holdout | consumer_rights_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 16.8s |
| 2 | holdout-consumer-rights-contradiction-cancellation-rights-002 | holdout | consumer_rights_holdout | contradiction | contradiction | not_related | FAIL | yes | yes | 1 | 0 | L1/A0/S0 | 0.00 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 14.8s |
| 2 | holdout-consumer-rights-contradiction-faulty-goods-003 | holdout | consumer_rights_holdout | contradiction | not_related | not_related | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.77 |  | 27.5s |
| 2 | holdout-consumer-rights-contradiction-subscription-cancel-004 | holdout | consumer_rights_holdout | contradiction | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.73 |  | 15.6s |
| 2 | holdout-consumer-rights-supported-total-price-005 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 11.8s |
| 2 | holdout-consumer-rights-supported-cancellation-rights-006 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 15.6s |
| 2 | holdout-consumer-rights-supported-faulty-goods-007 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 15.0s |
| 2 | holdout-consumer-rights-supported-subscription-cancel-008 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 12.9s |
| 2 | holdout-consumer-rights-not-related-supplier-numbering-009 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 5.1s |
| 2 | holdout-consumer-rights-not-related-vat-records-010 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.44 | screen_rejected_not_related | 5.2s |
| 2 | holdout-consumer-rights-not-related-packaging-weights-011 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 5.6s |
| 2 | holdout-consumer-rights-not-related-integration-retry-012 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 3.5s |
| 3 | vat-contradiction-retention-delete-001 | training | vat | contradiction | needs_human_review | contradiction | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | direct_conflict_guard:needs_human_review->contradiction:classification_changed | 15.8s |
| 3 | vat-contradiction-retention-not-required-002 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.4s |
| 3 | vat-contradiction-rate-change-old-rate-003 | training | vat | contradiction | missing_detail | contradiction | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | direct_conflict_guard:missing_detail->contradiction:classification_changed | 15.8s |
| 3 | vat-contradiction-rate-change-new-rate-004 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.9s |
| 3 | vat-contradiction-private-use-005 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 13.5s |
| 3 | packaging-contradiction-third-party-shipping-006 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 11.3s |
| 3 | packaging-contradiction-supplier-purchased-007 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 11.5s |
| 3 | packaging-contradiction-delete-evidence-008 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.3s |
| 3 | supported-vat-private-use-percentage-001 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 12.3s |
| 3 | supported-vat-evidence-retention-002 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.7s |
| 3 | supported-vat-rate-change-003 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 11.6s |
| 3 | supported-packaging-material-split-004 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.5s |
| 3 | supported-packaging-threshold-assessment-005 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 12.8s |
| 3 | supported-packaging-evidence-retention-006 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 15.1s |
| 3 | too-vague-vat-evidence-001 | training | vat | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.6s |
| 3 | too-vague-vat-business-use-002 | training | vat | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 15.2s |
| 3 | too-vague-vat-rate-change-003 | training | vat | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 16.1s |
| 3 | too-vague-packaging-material-004 | training | packaging_waste | too_vague | not_related | too_vague | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->too_vague:classification_changed | 12.5s |
| 3 | too-vague-packaging-threshold-005 | training | packaging_waste | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 15.5s |
| 3 | too-vague-packaging-evidence-006 | training | packaging_waste | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 15.4s |
| 3 | missing-obligation-vat-input-tax-evidence-001 | training | vat | missing_obligation | not_related | missing_obligation | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 15.2s |
| 3 | missing-obligation-vat-mixed-use-002 | training | vat | missing_obligation | missing_obligation | missing_obligation | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 3 | missing-obligation-vat-credit-note-003 | training | vat | missing_obligation | not_related | missing_obligation | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 13.0s |
| 3 | missing-obligation-packaging-threshold-004 | training | packaging_waste | missing_obligation | missing_obligation | missing_obligation | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.50 | screen_rejected_missing_obligation | 5.1s |
| 3 | missing-obligation-packaging-deadline-005 | training | packaging_waste | missing_obligation | not_related | missing_obligation | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 14.9s |
| 3 | missing-obligation-packaging-evidence-006 | training | packaging_waste | missing_obligation | missing_obligation | missing_obligation | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.57 | screen_rejected_missing_obligation | 3.6s |
| 3 | missing-detail-vat-retail-invoice-exception-001 | training | vat | missing_detail | missing_detail | missing_detail | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 15.3s |
| 3 | missing-detail-vat-import-evidence-002 | training | vat | missing_detail | missing_detail | missing_detail | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 13.9s |
| 3 | missing-detail-vat-rate-change-correction-003 | training | vat | missing_detail | too_vague | missing_detail | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:too_vague->missing_detail:classification_changed | 19.8s |
| 3 | missing-detail-packaging-material-categories-004 | training | packaging_waste | missing_detail | not_related | missing_detail | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 11.9s |
| 3 | missing-detail-packaging-household-scope-005 | training | packaging_waste | missing_detail | not_related | missing_detail | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 16.9s |
| 3 | missing-detail-packaging-reusable-006 | training | packaging_waste | missing_detail | not_related | missing_detail | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 17.7s |
| 3 | not-related-vat-supply-flexibility-lists-001 | training | vat | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.1s |
| 3 | not-related-vat-private-use-list-use-case-002 | training | vat | not_related | not_related | not_related | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 15.8s |
| 3 | not-related-vat-rate-change-parameter-003 | training | vat | not_related | not_related | not_related | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 10.8s |
| 3 | not-related-packaging-supplier-contract-004 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.53 | screen_rejected_not_related | 4.6s |
| 3 | not-related-packaging-age-restricted-005 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 4.8s |
| 3 | not-related-packaging-scheduling-006 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.55 | screen_rejected_not_related | 5.5s |
| 3 | holdout-bribery-contradiction-associated-persons-001 | training | bribery_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.70 |  | 15.3s |
| 3 | holdout-bribery-contradiction-employee-only-002 | training | bribery_holdout | contradiction | missing_detail | contradiction | PASS | yes | yes | 1 | 0 | L0/A0/S1 | 0.62 | direct_conflict_guard:missing_detail->contradiction:classification_changed | 18.6s |
| 3 | holdout-bribery-contradiction-facilitation-payment-003 | training | bribery_holdout | contradiction | not_related | contradiction | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | direct_conflict_guard:not_related->contradiction:classification_changed | 16.1s |
| 3 | holdout-bribery-contradiction-training-evidence-004 | training | bribery_holdout | contradiction | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 18.1s |
| 3 | holdout-bribery-supported-associated-persons-005 | training | bribery_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 15.8s |
| 3 | holdout-bribery-supported-gifts-approval-006 | training | bribery_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.69 |  | 14.5s |
| 3 | holdout-bribery-supported-training-007 | training | bribery_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 13.3s |
| 3 | holdout-bribery-supported-reporting-008 | training | bribery_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 13.3s |
| 3 | holdout-bribery-not-related-invoice-009 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.0s |
| 3 | holdout-bribery-not-related-product-label-010 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.44 | screen_rejected_not_related | 4.2s |
| 3 | holdout-bribery-not-related-integration-011 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 3 | holdout-bribery-not-related-stock-list-012 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.47 | screen_rejected_not_related | 5.4s |
| 3 | holdout-data-protection-contradiction-dsar-delay-001 | training | data_protection_holdout | contradiction | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.75 |  | 21.7s |
| 3 | holdout-data-protection-contradiction-erasure-retention-002 | training | data_protection_holdout | contradiction | contradiction | not_related | FAIL | yes | yes | 1 | 0 | L1/A0/S0 | 0.00 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 13.7s |
| 3 | holdout-data-protection-contradiction-breach-reporting-003 | training | data_protection_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.63 |  | 13.2s |
| 3 | holdout-data-protection-contradiction-consent-withdrawal-004 | training | data_protection_holdout | contradiction | missing_obligation | missing_obligation | FAIL | no | no | 0 | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 3 | holdout-data-protection-supported-dsar-deadline-005 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 11.5s |
| 3 | holdout-data-protection-supported-erasure-purpose-006 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 12.8s |
| 3 | holdout-data-protection-supported-breach-reporting-007 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 12.1s |
| 3 | holdout-data-protection-supported-consent-withdrawal-008 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 12.4s |
| 3 | holdout-data-protection-not-related-packaging-009 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.52 | screen_rejected_not_related | 5.2s |
| 3 | holdout-data-protection-not-related-integration-010 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.51 | screen_rejected_not_related | 5.5s |
| 3 | holdout-data-protection-not-related-contracts-011 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.41 | screen_rejected_not_related | 5.2s |
| 3 | holdout-data-protection-not-related-category-012 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.40 | screen_rejected_not_related | 5.6s |
| 3 | holdout-accessibility-contradiction-captions-001 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 16.3s |
| 3 | holdout-accessibility-contradiction-alt-text-002 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.64 |  | 17.4s |
| 3 | holdout-accessibility-contradiction-keyboard-003 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.60 |  | 14.3s |
| 3 | holdout-accessibility-contradiction-error-identification-004 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.65 |  | 15.5s |
| 3 | holdout-accessibility-supported-captions-005 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 13.2s |
| 3 | holdout-accessibility-supported-alt-text-006 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 17.8s |
| 3 | holdout-accessibility-supported-keyboard-007 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.74 |  | 14.1s |
| 3 | holdout-accessibility-supported-error-identification-008 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.68 |  | 14.6s |
| 3 | holdout-accessibility-not-related-contract-numbering-009 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.42 | screen_rejected_not_related | 6.4s |
| 3 | holdout-accessibility-not-related-vat-records-010 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.39 | not_related | 0.0s |
| 3 | holdout-accessibility-not-related-packaging-weights-011 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 3 | holdout-accessibility-not-related-integration-retry-012 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.52 | screen_rejected_not_related | 5.5s |
| 3 | holdout-consumer-rights-contradiction-total-price-001 | holdout | consumer_rights_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 16.8s |
| 3 | holdout-consumer-rights-contradiction-cancellation-rights-002 | holdout | consumer_rights_holdout | contradiction | contradiction | not_related | FAIL | yes | yes | 1 | 0 | L1/A0/S0 | 0.00 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 14.8s |
| 3 | holdout-consumer-rights-contradiction-faulty-goods-003 | holdout | consumer_rights_holdout | contradiction | not_related | not_related | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.77 |  | 27.5s |
| 3 | holdout-consumer-rights-contradiction-subscription-cancel-004 | holdout | consumer_rights_holdout | contradiction | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.73 |  | 15.7s |
| 3 | holdout-consumer-rights-supported-total-price-005 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 11.8s |
| 3 | holdout-consumer-rights-supported-cancellation-rights-006 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 15.7s |
| 3 | holdout-consumer-rights-supported-faulty-goods-007 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 15.3s |
| 3 | holdout-consumer-rights-supported-subscription-cancel-008 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 13.2s |
| 3 | holdout-consumer-rights-not-related-supplier-numbering-009 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 5.2s |
| 3 | holdout-consumer-rights-not-related-vat-records-010 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.44 | screen_rejected_not_related | 5.3s |
| 3 | holdout-consumer-rights-not-related-packaging-weights-011 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 5.7s |
| 3 | holdout-consumer-rights-not-related-integration-retry-012 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 3.6s |