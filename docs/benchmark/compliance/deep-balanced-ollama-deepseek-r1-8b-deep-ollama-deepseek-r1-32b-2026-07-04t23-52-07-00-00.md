# Compliance Reasoning Evaluation - 207/258 passed (80%)

Generated: 2026-07-04T23:52:07+00:00
Depth: deep
Model profile: balanced=ollama:deepseek-r1:8b;deep=ollama:deepseek-r1:32b
Runs: 3
Fake generator: False
Throttle deep: False
Safety gates disabled: False
Semantic candidate threshold: 0.58

Total runtime: 6002.1s
Mean pair latency: 23.3s
P95 pair latency: 38.9s
Mean LLM-called latency: 24.7s
Mean deterministic latency: 0.0s

## Per-Class Metrics

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| contradiction | 100% | 79% | 88% | 72 |
| missing_obligation | 50% | 100% | 67% | 18 |
| missing_detail | 33% | 67% | 44% | 18 |
| too_vague | 83% | 83% | 83% | 18 |
| supported | 100% | 68% | 81% | 66 |
| not_related | 91% | 91% | 91% | 66 |

## Split Metrics

| Split | Passed | Accuracy | LLM Coverage | not_related Recall | Contradiction Precision |
|---|---:|---:|---:|---:|---:|
| training | 180/222 | 81% | 93% | 89% | 100% |
| holdout | 27/36 | 75% | 100% | 100% | 100% |

## Guard Ablation

Model-only accuracy: 201/258 (78%)
With-guards accuracy: 207/258 (80%)
Guard-changed classifications: 18/258
Guard helped: 12
Guard hurt: 6

| Split | Model-only | With guards | Changed | Helped | Hurt |
|---|---:|---:|---:|---:|---:|
| training | 171/222 (77%) | 180/222 (81%) | 15 | 12 | 3 |
| holdout | 30/36 (83%) | 27/36 (75%) | 3 | 0 | 3 |

## Confusion Matrix

| Expected \ Actual | contradiction | missing_obligation | missing_detail | too_vague | supported | not_related |
|---|---:|---:|---:|---:|---:|---:|
| contradiction | 57 | 6 | 3 | 0 | 0 | 6 |
| missing_obligation | 0 | 18 | 0 | 0 | 0 | 0 |
| missing_detail | 0 | 6 | 12 | 0 | 0 | 0 |
| too_vague | 0 | 0 | 3 | 15 | 0 | 0 |
| supported | 0 | 0 | 18 | 3 | 45 | 0 |
| not_related | 0 | 6 | 0 | 0 | 0 | 60 |

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
Same-obligation screen latency: 313.7s
Total adjudication calls: 186
No-candidate not-related resolutions: 60
Rejected candidate findings retained: 6

| Expected class | Never adjudicated |
|---|---:|
| contradiction | 3 |
| missing_obligation | 3 |
| missing_detail | 0 |
| too_vague | 0 |
| supported | 0 |
| not_related | 9 |

### Gate Demotions

| Reason | Count |
|---|---:|
| class_boundary_guard:not_related->too_vague:classification_changed | 3 |
| class_boundary_guard:not_related->missing_obligation:classification_changed | 6 |
| class_boundary_guard:not_related->missing_detail:classification_changed | 3 |
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
| contradiction | 63 | 57 | 57 | 0 |
| missing_detail | 33 | 36 | 36 | 0 |
| missing_obligation | 18 | 24 | 0 | 0 |
| not_related | 12 | 6 | 0 | 6 |
| supported | 45 | 45 | 45 | 0 |
| too_vague | 15 | 18 | 18 | 0 |

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
| 1 | vat-contradiction-retention-delete-001 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 44.1s |
| 1 | vat-contradiction-retention-not-required-002 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 26.5s |
| 1 | vat-contradiction-rate-change-old-rate-003 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 25.9s |
| 1 | vat-contradiction-rate-change-new-rate-004 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 33.3s |
| 1 | vat-contradiction-private-use-005 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 30.0s |
| 1 | packaging-contradiction-third-party-shipping-006 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 23.5s |
| 1 | packaging-contradiction-supplier-purchased-007 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 22.0s |
| 1 | packaging-contradiction-delete-evidence-008 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 28.6s |
| 1 | supported-vat-private-use-percentage-001 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 30.2s |
| 1 | supported-vat-evidence-retention-002 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 25.0s |
| 1 | supported-vat-rate-change-003 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 30.6s |
| 1 | supported-packaging-material-split-004 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 23.3s |
| 1 | supported-packaging-threshold-assessment-005 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 25.2s |
| 1 | supported-packaging-evidence-retention-006 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 23.5s |
| 1 | too-vague-vat-evidence-001 | training | vat | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 30.9s |
| 1 | too-vague-vat-business-use-002 | training | vat | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 31.4s |
| 1 | too-vague-vat-rate-change-003 | training | vat | too_vague | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 39.6s |
| 1 | too-vague-packaging-material-004 | training | packaging_waste | too_vague | not_related | too_vague | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->too_vague:classification_changed | 33.0s |
| 1 | too-vague-packaging-threshold-005 | training | packaging_waste | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 27.8s |
| 1 | too-vague-packaging-evidence-006 | training | packaging_waste | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 22.9s |
| 1 | missing-obligation-vat-input-tax-evidence-001 | training | vat | missing_obligation | missing_obligation | missing_obligation | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 35.3s |
| 1 | missing-obligation-vat-mixed-use-002 | training | vat | missing_obligation | missing_obligation | missing_obligation | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 1 | missing-obligation-vat-credit-note-003 | training | vat | missing_obligation | not_related | missing_obligation | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 47.0s |
| 1 | missing-obligation-packaging-threshold-004 | training | packaging_waste | missing_obligation | missing_obligation | missing_obligation | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.50 | screen_rejected_missing_obligation | 8.5s |
| 1 | missing-obligation-packaging-deadline-005 | training | packaging_waste | missing_obligation | not_related | missing_obligation | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 39.7s |
| 1 | missing-obligation-packaging-evidence-006 | training | packaging_waste | missing_obligation | missing_obligation | missing_obligation | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.57 | screen_rejected_missing_obligation | 5.9s |
| 1 | missing-detail-vat-retail-invoice-exception-001 | training | vat | missing_detail | missing_detail | missing_detail | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 26.2s |
| 1 | missing-detail-vat-import-evidence-002 | training | vat | missing_detail | missing_detail | missing_detail | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 28.5s |
| 1 | missing-detail-vat-rate-change-correction-003 | training | vat | missing_detail | missing_detail | missing_detail | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 27.0s |
| 1 | missing-detail-packaging-material-categories-004 | training | packaging_waste | missing_detail | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 26.5s |
| 1 | missing-detail-packaging-household-scope-005 | training | packaging_waste | missing_detail | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 35.0s |
| 1 | missing-detail-packaging-reusable-006 | training | packaging_waste | missing_detail | not_related | missing_detail | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 34.5s |
| 1 | not-related-vat-supply-flexibility-lists-001 | training | vat | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.2s |
| 1 | not-related-vat-private-use-list-use-case-002 | training | vat | not_related | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 32.2s |
| 1 | not-related-vat-rate-change-parameter-003 | training | vat | not_related | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 21.1s |
| 1 | not-related-packaging-supplier-contract-004 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.53 | screen_rejected_not_related | 4.8s |
| 1 | not-related-packaging-age-restricted-005 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 4.9s |
| 1 | not-related-packaging-scheduling-006 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.55 | screen_rejected_not_related | 5.6s |
| 1 | holdout-bribery-contradiction-associated-persons-001 | training | bribery_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.70 |  | 27.2s |
| 1 | holdout-bribery-contradiction-employee-only-002 | training | bribery_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.62 |  | 32.9s |
| 1 | holdout-bribery-contradiction-facilitation-payment-003 | training | bribery_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 34.9s |
| 1 | holdout-bribery-contradiction-training-evidence-004 | training | bribery_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 31.2s |
| 1 | holdout-bribery-supported-associated-persons-005 | training | bribery_holdout | supported | too_vague | too_vague | FAIL | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 33.0s |
| 1 | holdout-bribery-supported-gifts-approval-006 | training | bribery_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.69 |  | 31.2s |
| 1 | holdout-bribery-supported-training-007 | training | bribery_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 32.9s |
| 1 | holdout-bribery-supported-reporting-008 | training | bribery_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 33.1s |
| 1 | holdout-bribery-not-related-invoice-009 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.2s |
| 1 | holdout-bribery-not-related-product-label-010 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.44 | screen_rejected_not_related | 4.3s |
| 1 | holdout-bribery-not-related-integration-011 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 1 | holdout-bribery-not-related-stock-list-012 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.47 | screen_rejected_not_related | 5.5s |
| 1 | holdout-data-protection-contradiction-dsar-delay-001 | training | data_protection_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.75 |  | 30.0s |
| 1 | holdout-data-protection-contradiction-erasure-retention-002 | training | data_protection_holdout | contradiction | contradiction | not_related | FAIL | yes | yes | 1 | 0 | L1/A0/S0 | 0.00 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 38.1s |
| 1 | holdout-data-protection-contradiction-breach-reporting-003 | training | data_protection_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.63 |  | 30.6s |
| 1 | holdout-data-protection-contradiction-consent-withdrawal-004 | training | data_protection_holdout | contradiction | missing_obligation | missing_obligation | FAIL | no | no | 0 | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 1 | holdout-data-protection-supported-dsar-deadline-005 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 26.3s |
| 1 | holdout-data-protection-supported-erasure-purpose-006 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 24.9s |
| 1 | holdout-data-protection-supported-breach-reporting-007 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 28.1s |
| 1 | holdout-data-protection-supported-consent-withdrawal-008 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 32.6s |
| 1 | holdout-data-protection-not-related-packaging-009 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.52 | screen_rejected_not_related | 5.3s |
| 1 | holdout-data-protection-not-related-integration-010 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.51 | screen_rejected_not_related | 5.6s |
| 1 | holdout-data-protection-not-related-contracts-011 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.41 | screen_rejected_not_related | 5.3s |
| 1 | holdout-data-protection-not-related-category-012 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.40 | screen_rejected_not_related | 5.7s |
| 1 | holdout-accessibility-contradiction-captions-001 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 32.5s |
| 1 | holdout-accessibility-contradiction-alt-text-002 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.64 |  | 31.5s |
| 1 | holdout-accessibility-contradiction-keyboard-003 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.60 |  | 25.1s |
| 1 | holdout-accessibility-contradiction-error-identification-004 | training | accessibility_holdout | contradiction | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.65 |  | 36.8s |
| 1 | holdout-accessibility-supported-captions-005 | training | accessibility_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 28.7s |
| 1 | holdout-accessibility-supported-alt-text-006 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 35.3s |
| 1 | holdout-accessibility-supported-keyboard-007 | training | accessibility_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.74 |  | 28.8s |
| 1 | holdout-accessibility-supported-error-identification-008 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.68 |  | 22.8s |
| 1 | holdout-accessibility-not-related-contract-numbering-009 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.42 | screen_rejected_not_related | 6.5s |
| 1 | holdout-accessibility-not-related-vat-records-010 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.39 | not_related | 0.0s |
| 1 | holdout-accessibility-not-related-packaging-weights-011 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 1 | holdout-accessibility-not-related-integration-retry-012 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.52 | screen_rejected_not_related | 5.7s |
| 1 | holdout-consumer-rights-contradiction-total-price-001 | holdout | consumer_rights_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 35.5s |
| 1 | holdout-consumer-rights-contradiction-cancellation-rights-002 | holdout | consumer_rights_holdout | contradiction | contradiction | not_related | FAIL | yes | yes | 1 | 0 | L1/A0/S0 | 0.00 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 33.4s |
| 1 | holdout-consumer-rights-contradiction-faulty-goods-003 | holdout | consumer_rights_holdout | contradiction | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.77 |  | 50.2s |
| 1 | holdout-consumer-rights-contradiction-subscription-cancel-004 | holdout | consumer_rights_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.73 |  | 27.0s |
| 1 | holdout-consumer-rights-supported-total-price-005 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 28.9s |
| 1 | holdout-consumer-rights-supported-cancellation-rights-006 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 23.2s |
| 1 | holdout-consumer-rights-supported-faulty-goods-007 | holdout | consumer_rights_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 31.6s |
| 1 | holdout-consumer-rights-supported-subscription-cancel-008 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 22.3s |
| 1 | holdout-consumer-rights-not-related-supplier-numbering-009 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 5.2s |
| 1 | holdout-consumer-rights-not-related-vat-records-010 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.44 | screen_rejected_not_related | 5.3s |
| 1 | holdout-consumer-rights-not-related-packaging-weights-011 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 5.7s |
| 1 | holdout-consumer-rights-not-related-integration-retry-012 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 3.6s |
| 2 | vat-contradiction-retention-delete-001 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 28.8s |
| 2 | vat-contradiction-retention-not-required-002 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 25.8s |
| 2 | vat-contradiction-rate-change-old-rate-003 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 25.9s |
| 2 | vat-contradiction-rate-change-new-rate-004 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 33.9s |
| 2 | vat-contradiction-private-use-005 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 30.4s |
| 2 | packaging-contradiction-third-party-shipping-006 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 23.9s |
| 2 | packaging-contradiction-supplier-purchased-007 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 22.4s |
| 2 | packaging-contradiction-delete-evidence-008 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 28.7s |
| 2 | supported-vat-private-use-percentage-001 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 30.3s |
| 2 | supported-vat-evidence-retention-002 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 25.1s |
| 2 | supported-vat-rate-change-003 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 30.9s |
| 2 | supported-packaging-material-split-004 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 23.8s |
| 2 | supported-packaging-threshold-assessment-005 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 25.8s |
| 2 | supported-packaging-evidence-retention-006 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 24.0s |
| 2 | too-vague-vat-evidence-001 | training | vat | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 31.3s |
| 2 | too-vague-vat-business-use-002 | training | vat | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 31.5s |
| 2 | too-vague-vat-rate-change-003 | training | vat | too_vague | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 39.8s |
| 2 | too-vague-packaging-material-004 | training | packaging_waste | too_vague | not_related | too_vague | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->too_vague:classification_changed | 33.1s |
| 2 | too-vague-packaging-threshold-005 | training | packaging_waste | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 28.1s |
| 2 | too-vague-packaging-evidence-006 | training | packaging_waste | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 23.1s |
| 2 | missing-obligation-vat-input-tax-evidence-001 | training | vat | missing_obligation | missing_obligation | missing_obligation | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 35.4s |
| 2 | missing-obligation-vat-mixed-use-002 | training | vat | missing_obligation | missing_obligation | missing_obligation | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 2 | missing-obligation-vat-credit-note-003 | training | vat | missing_obligation | not_related | missing_obligation | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 47.3s |
| 2 | missing-obligation-packaging-threshold-004 | training | packaging_waste | missing_obligation | missing_obligation | missing_obligation | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.50 | screen_rejected_missing_obligation | 6.3s |
| 2 | missing-obligation-packaging-deadline-005 | training | packaging_waste | missing_obligation | not_related | missing_obligation | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 40.6s |
| 2 | missing-obligation-packaging-evidence-006 | training | packaging_waste | missing_obligation | missing_obligation | missing_obligation | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.57 | screen_rejected_missing_obligation | 6.0s |
| 2 | missing-detail-vat-retail-invoice-exception-001 | training | vat | missing_detail | missing_detail | missing_detail | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 27.1s |
| 2 | missing-detail-vat-import-evidence-002 | training | vat | missing_detail | missing_detail | missing_detail | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 29.5s |
| 2 | missing-detail-vat-rate-change-correction-003 | training | vat | missing_detail | missing_detail | missing_detail | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 27.9s |
| 2 | missing-detail-packaging-material-categories-004 | training | packaging_waste | missing_detail | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 27.3s |
| 2 | missing-detail-packaging-household-scope-005 | training | packaging_waste | missing_detail | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 35.9s |
| 2 | missing-detail-packaging-reusable-006 | training | packaging_waste | missing_detail | not_related | missing_detail | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 35.3s |
| 2 | not-related-vat-supply-flexibility-lists-001 | training | vat | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.2s |
| 2 | not-related-vat-private-use-list-use-case-002 | training | vat | not_related | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 32.9s |
| 2 | not-related-vat-rate-change-parameter-003 | training | vat | not_related | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 21.5s |
| 2 | not-related-packaging-supplier-contract-004 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.53 | screen_rejected_not_related | 4.8s |
| 2 | not-related-packaging-age-restricted-005 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 5.0s |
| 2 | not-related-packaging-scheduling-006 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.55 | screen_rejected_not_related | 5.7s |
| 2 | holdout-bribery-contradiction-associated-persons-001 | training | bribery_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.70 |  | 27.8s |
| 2 | holdout-bribery-contradiction-employee-only-002 | training | bribery_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.62 |  | 33.5s |
| 2 | holdout-bribery-contradiction-facilitation-payment-003 | training | bribery_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 35.7s |
| 2 | holdout-bribery-contradiction-training-evidence-004 | training | bribery_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 31.8s |
| 2 | holdout-bribery-supported-associated-persons-005 | training | bribery_holdout | supported | too_vague | too_vague | FAIL | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 33.7s |
| 2 | holdout-bribery-supported-gifts-approval-006 | training | bribery_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.69 |  | 31.9s |
| 2 | holdout-bribery-supported-training-007 | training | bribery_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 33.5s |
| 2 | holdout-bribery-supported-reporting-008 | training | bribery_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 33.8s |
| 2 | holdout-bribery-not-related-invoice-009 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.2s |
| 2 | holdout-bribery-not-related-product-label-010 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.44 | screen_rejected_not_related | 4.3s |
| 2 | holdout-bribery-not-related-integration-011 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 2 | holdout-bribery-not-related-stock-list-012 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.47 | screen_rejected_not_related | 5.5s |
| 2 | holdout-data-protection-contradiction-dsar-delay-001 | training | data_protection_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.75 |  | 30.6s |
| 2 | holdout-data-protection-contradiction-erasure-retention-002 | training | data_protection_holdout | contradiction | contradiction | not_related | FAIL | yes | yes | 1 | 0 | L1/A0/S0 | 0.00 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 38.9s |
| 2 | holdout-data-protection-contradiction-breach-reporting-003 | training | data_protection_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.63 |  | 31.0s |
| 2 | holdout-data-protection-contradiction-consent-withdrawal-004 | training | data_protection_holdout | contradiction | missing_obligation | missing_obligation | FAIL | no | no | 0 | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 2 | holdout-data-protection-supported-dsar-deadline-005 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 26.8s |
| 2 | holdout-data-protection-supported-erasure-purpose-006 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 25.4s |
| 2 | holdout-data-protection-supported-breach-reporting-007 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 28.5s |
| 2 | holdout-data-protection-supported-consent-withdrawal-008 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 33.3s |
| 2 | holdout-data-protection-not-related-packaging-009 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.52 | screen_rejected_not_related | 5.4s |
| 2 | holdout-data-protection-not-related-integration-010 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.51 | screen_rejected_not_related | 5.7s |
| 2 | holdout-data-protection-not-related-contracts-011 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.41 | screen_rejected_not_related | 5.4s |
| 2 | holdout-data-protection-not-related-category-012 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.40 | screen_rejected_not_related | 5.8s |
| 2 | holdout-accessibility-contradiction-captions-001 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 33.2s |
| 2 | holdout-accessibility-contradiction-alt-text-002 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.64 |  | 32.1s |
| 2 | holdout-accessibility-contradiction-keyboard-003 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.60 |  | 25.6s |
| 2 | holdout-accessibility-contradiction-error-identification-004 | training | accessibility_holdout | contradiction | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.65 |  | 37.5s |
| 2 | holdout-accessibility-supported-captions-005 | training | accessibility_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 29.4s |
| 2 | holdout-accessibility-supported-alt-text-006 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 35.4s |
| 2 | holdout-accessibility-supported-keyboard-007 | training | accessibility_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.74 |  | 28.9s |
| 2 | holdout-accessibility-supported-error-identification-008 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.68 |  | 22.8s |
| 2 | holdout-accessibility-not-related-contract-numbering-009 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.42 | screen_rejected_not_related | 6.4s |
| 2 | holdout-accessibility-not-related-vat-records-010 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.39 | not_related | 0.0s |
| 2 | holdout-accessibility-not-related-packaging-weights-011 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 2 | holdout-accessibility-not-related-integration-retry-012 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.52 | screen_rejected_not_related | 5.6s |
| 2 | holdout-consumer-rights-contradiction-total-price-001 | holdout | consumer_rights_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 35.6s |
| 2 | holdout-consumer-rights-contradiction-cancellation-rights-002 | holdout | consumer_rights_holdout | contradiction | contradiction | not_related | FAIL | yes | yes | 1 | 0 | L1/A0/S0 | 0.00 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 33.6s |
| 2 | holdout-consumer-rights-contradiction-faulty-goods-003 | holdout | consumer_rights_holdout | contradiction | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.77 |  | 50.4s |
| 2 | holdout-consumer-rights-contradiction-subscription-cancel-004 | holdout | consumer_rights_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.73 |  | 27.1s |
| 2 | holdout-consumer-rights-supported-total-price-005 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 29.0s |
| 2 | holdout-consumer-rights-supported-cancellation-rights-006 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 23.3s |
| 2 | holdout-consumer-rights-supported-faulty-goods-007 | holdout | consumer_rights_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 31.8s |
| 2 | holdout-consumer-rights-supported-subscription-cancel-008 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 22.4s |
| 2 | holdout-consumer-rights-not-related-supplier-numbering-009 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 5.3s |
| 2 | holdout-consumer-rights-not-related-vat-records-010 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.44 | screen_rejected_not_related | 5.3s |
| 2 | holdout-consumer-rights-not-related-packaging-weights-011 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 5.8s |
| 2 | holdout-consumer-rights-not-related-integration-retry-012 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 3.6s |
| 3 | vat-contradiction-retention-delete-001 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 28.9s |
| 3 | vat-contradiction-retention-not-required-002 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 25.5s |
| 3 | vat-contradiction-rate-change-old-rate-003 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 25.5s |
| 3 | vat-contradiction-rate-change-new-rate-004 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 33.3s |
| 3 | vat-contradiction-private-use-005 | training | vat | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 29.9s |
| 3 | packaging-contradiction-third-party-shipping-006 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 23.6s |
| 3 | packaging-contradiction-supplier-purchased-007 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 22.1s |
| 3 | packaging-contradiction-delete-evidence-008 | training | packaging_waste | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 28.3s |
| 3 | supported-vat-private-use-percentage-001 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 29.8s |
| 3 | supported-vat-evidence-retention-002 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 24.6s |
| 3 | supported-vat-rate-change-003 | training | vat | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 30.4s |
| 3 | supported-packaging-material-split-004 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 23.4s |
| 3 | supported-packaging-threshold-assessment-005 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 25.4s |
| 3 | supported-packaging-evidence-retention-006 | training | packaging_waste | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 23.8s |
| 3 | too-vague-vat-evidence-001 | training | vat | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 31.1s |
| 3 | too-vague-vat-business-use-002 | training | vat | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 31.0s |
| 3 | too-vague-vat-rate-change-003 | training | vat | too_vague | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 39.1s |
| 3 | too-vague-packaging-material-004 | training | packaging_waste | too_vague | not_related | too_vague | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->too_vague:classification_changed | 32.5s |
| 3 | too-vague-packaging-threshold-005 | training | packaging_waste | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 27.6s |
| 3 | too-vague-packaging-evidence-006 | training | packaging_waste | too_vague | too_vague | too_vague | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 22.7s |
| 3 | missing-obligation-vat-input-tax-evidence-001 | training | vat | missing_obligation | missing_obligation | missing_obligation | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 34.8s |
| 3 | missing-obligation-vat-mixed-use-002 | training | vat | missing_obligation | missing_obligation | missing_obligation | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 3 | missing-obligation-vat-credit-note-003 | training | vat | missing_obligation | not_related | missing_obligation | PASS | yes | yes | 1 | 0 | L0/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 46.5s |
| 3 | missing-obligation-packaging-threshold-004 | training | packaging_waste | missing_obligation | missing_obligation | missing_obligation | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.50 | screen_rejected_missing_obligation | 6.2s |
| 3 | missing-obligation-packaging-deadline-005 | training | packaging_waste | missing_obligation | not_related | missing_obligation | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_obligation:classification_changed | 39.9s |
| 3 | missing-obligation-packaging-evidence-006 | training | packaging_waste | missing_obligation | missing_obligation | missing_obligation | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.57 | screen_rejected_missing_obligation | 5.9s |
| 3 | missing-detail-vat-retail-invoice-exception-001 | training | vat | missing_detail | missing_detail | missing_detail | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 26.6s |
| 3 | missing-detail-vat-import-evidence-002 | training | vat | missing_detail | missing_detail | missing_detail | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 29.0s |
| 3 | missing-detail-vat-rate-change-correction-003 | training | vat | missing_detail | missing_detail | missing_detail | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 27.4s |
| 3 | missing-detail-packaging-material-categories-004 | training | packaging_waste | missing_detail | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 26.8s |
| 3 | missing-detail-packaging-household-scope-005 | training | packaging_waste | missing_detail | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 35.6s |
| 3 | missing-detail-packaging-reusable-006 | training | packaging_waste | missing_detail | not_related | missing_detail | PASS | yes | yes | 1 | 0 | L1/A1/S0 | 0.00 | class_boundary_guard:not_related->missing_detail:classification_changed | 35.3s |
| 3 | not-related-vat-supply-flexibility-lists-001 | training | vat | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.3s |
| 3 | not-related-vat-private-use-list-use-case-002 | training | vat | not_related | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 32.9s |
| 3 | not-related-vat-rate-change-parameter-003 | training | vat | not_related | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 21.6s |
| 3 | not-related-packaging-supplier-contract-004 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.53 | screen_rejected_not_related | 4.8s |
| 3 | not-related-packaging-age-restricted-005 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 4.9s |
| 3 | not-related-packaging-scheduling-006 | training | packaging_waste | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.55 | screen_rejected_not_related | 5.7s |
| 3 | holdout-bribery-contradiction-associated-persons-001 | training | bribery_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.70 |  | 27.8s |
| 3 | holdout-bribery-contradiction-employee-only-002 | training | bribery_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.62 |  | 33.6s |
| 3 | holdout-bribery-contradiction-facilitation-payment-003 | training | bribery_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 35.7s |
| 3 | holdout-bribery-contradiction-training-evidence-004 | training | bribery_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A1/S0 | 0.00 |  | 31.8s |
| 3 | holdout-bribery-supported-associated-persons-005 | training | bribery_holdout | supported | too_vague | too_vague | FAIL | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 33.7s |
| 3 | holdout-bribery-supported-gifts-approval-006 | training | bribery_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.69 |  | 32.1s |
| 3 | holdout-bribery-supported-training-007 | training | bribery_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 33.4s |
| 3 | holdout-bribery-supported-reporting-008 | training | bribery_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 33.8s |
| 3 | holdout-bribery-not-related-invoice-009 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 6.2s |
| 3 | holdout-bribery-not-related-product-label-010 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.44 | screen_rejected_not_related | 4.3s |
| 3 | holdout-bribery-not-related-integration-011 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 3 | holdout-bribery-not-related-stock-list-012 | training | bribery_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.47 | screen_rejected_not_related | 5.5s |
| 3 | holdout-data-protection-contradiction-dsar-delay-001 | training | data_protection_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.75 |  | 30.6s |
| 3 | holdout-data-protection-contradiction-erasure-retention-002 | training | data_protection_holdout | contradiction | contradiction | not_related | FAIL | yes | yes | 1 | 0 | L1/A0/S0 | 0.00 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 38.9s |
| 3 | holdout-data-protection-contradiction-breach-reporting-003 | training | data_protection_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.63 |  | 31.2s |
| 3 | holdout-data-protection-contradiction-consent-withdrawal-004 | training | data_protection_holdout | contradiction | missing_obligation | missing_obligation | FAIL | no | no | 0 | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 3 | holdout-data-protection-supported-dsar-deadline-005 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 26.8s |
| 3 | holdout-data-protection-supported-erasure-purpose-006 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 25.4s |
| 3 | holdout-data-protection-supported-breach-reporting-007 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 28.5s |
| 3 | holdout-data-protection-supported-consent-withdrawal-008 | training | data_protection_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 33.3s |
| 3 | holdout-data-protection-not-related-packaging-009 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.52 | screen_rejected_not_related | 5.4s |
| 3 | holdout-data-protection-not-related-integration-010 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.51 | screen_rejected_not_related | 5.7s |
| 3 | holdout-data-protection-not-related-contracts-011 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.41 | screen_rejected_not_related | 5.4s |
| 3 | holdout-data-protection-not-related-category-012 | training | data_protection_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.40 | screen_rejected_not_related | 5.8s |
| 3 | holdout-accessibility-contradiction-captions-001 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A1/S0 | 0.00 |  | 33.2s |
| 3 | holdout-accessibility-contradiction-alt-text-002 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.64 |  | 32.1s |
| 3 | holdout-accessibility-contradiction-keyboard-003 | training | accessibility_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.60 |  | 25.6s |
| 3 | holdout-accessibility-contradiction-error-identification-004 | training | accessibility_holdout | contradiction | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.65 |  | 37.5s |
| 3 | holdout-accessibility-supported-captions-005 | training | accessibility_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 29.3s |
| 3 | holdout-accessibility-supported-alt-text-006 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 36.1s |
| 3 | holdout-accessibility-supported-keyboard-007 | training | accessibility_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.74 |  | 29.4s |
| 3 | holdout-accessibility-supported-error-identification-008 | training | accessibility_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.68 |  | 23.2s |
| 3 | holdout-accessibility-not-related-contract-numbering-009 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.42 | screen_rejected_not_related | 6.6s |
| 3 | holdout-accessibility-not-related-vat-records-010 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.39 | not_related | 0.0s |
| 3 | holdout-accessibility-not-related-packaging-weights-011 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | no | 0 | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 3 | holdout-accessibility-not-related-integration-retry-012 | training | accessibility_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.52 | screen_rejected_not_related | 5.7s |
| 3 | holdout-consumer-rights-contradiction-total-price-001 | holdout | consumer_rights_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 36.2s |
| 3 | holdout-consumer-rights-contradiction-cancellation-rights-002 | holdout | consumer_rights_holdout | contradiction | contradiction | not_related | FAIL | yes | yes | 1 | 0 | L1/A0/S0 | 0.00 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 34.2s |
| 3 | holdout-consumer-rights-contradiction-faulty-goods-003 | holdout | consumer_rights_holdout | contradiction | missing_obligation | missing_obligation | FAIL | no | yes | 1 | 0 | L0/A0/S1 | 0.77 |  | 51.3s |
| 3 | holdout-consumer-rights-contradiction-subscription-cancel-004 | holdout | consumer_rights_holdout | contradiction | contradiction | contradiction | PASS | no | yes | 1 | 0 | L0/A0/S1 | 0.73 |  | 27.6s |
| 3 | holdout-consumer-rights-supported-total-price-005 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 29.5s |
| 3 | holdout-consumer-rights-supported-cancellation-rights-006 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 23.8s |
| 3 | holdout-consumer-rights-supported-faulty-goods-007 | holdout | consumer_rights_holdout | supported | missing_detail | missing_detail | FAIL | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 32.4s |
| 3 | holdout-consumer-rights-supported-subscription-cancel-008 | holdout | consumer_rights_holdout | supported | supported | supported | PASS | no | yes | 1 | 0 | L1/A0/S0 | 0.00 |  | 22.8s |
| 3 | holdout-consumer-rights-not-related-supplier-numbering-009 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 5.3s |
| 3 | holdout-consumer-rights-not-related-vat-records-010 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.44 | screen_rejected_not_related | 5.4s |
| 3 | holdout-consumer-rights-not-related-packaging-weights-011 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 5.8s |
| 3 | holdout-consumer-rights-not-related-integration-retry-012 | holdout | consumer_rights_holdout | not_related | not_related | not_related | PASS | no | yes | 0 | 1 | L0/A0/S0 | 0.49 | screen_rejected_not_related | 3.7s |