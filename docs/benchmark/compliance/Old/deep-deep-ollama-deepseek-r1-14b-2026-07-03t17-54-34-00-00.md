# Compliance Reasoning Evaluation - 87/150 passed (58%)

Generated: 2026-07-03T17:54:34+00:00
Depth: deep
Model profile: deep=ollama:deepseek-r1:14b
Runs: 3
Fake generator: False
Throttle deep: False
Safety gates disabled: False
Semantic candidate threshold: 0.58

Total runtime: 1359.2s
Mean pair latency: 9.1s
P95 pair latency: 17.0s
Mean LLM-called latency: 14.2s
Mean deterministic latency: 0.0s

## Per-Class Metrics

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| contradiction | 100% | 50% | 67% | 36 |
| missing_obligation | 40% | 67% | 50% | 18 |
| missing_detail | 67% | 33% | 44% | 18 |
| too_vague | 83% | 83% | 83% | 18 |
| supported | 69% | 90% | 78% | 30 |
| not_related | 27% | 30% | 29% | 30 |
| needs_human_review | 0% | 0% | 0% | 0 |

## Split Metrics

| Split | Passed | Accuracy | LLM Coverage | not_related Recall | Contradiction Precision |
|---|---:|---:|---:|---:|---:|
| holdout | 15/36 | 42% | 17% | 25% | 100% |
| in_domain | 72/114 | 63% | 79% | 33% | 100% |

## Confusion Matrix

| Expected \ Actual | contradiction | missing_obligation | missing_detail | too_vague | supported | not_related | needs_human_review |
|---|---:|---:|---:|---:|---:|---:|---:|
| contradiction | 18 | 3 | 3 | 0 | 6 | 3 | 3 |
| missing_obligation | 0 | 12 | 0 | 0 | 0 | 6 | 0 |
| missing_detail | 0 | 0 | 6 | 3 | 0 | 9 | 0 |
| too_vague | 0 | 0 | 0 | 15 | 0 | 3 | 0 |
| supported | 0 | 0 | 0 | 0 | 27 | 3 | 0 |
| not_related | 0 | 15 | 0 | 0 | 6 | 9 | 0 |
| needs_human_review | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Observability

Rows that called the LLM: 96/150
Adjudicator coverage: 64%
Never adjudicated rows: 54
Candidate comparisons: 126
Total candidate count: 96
Lexical candidates: 57
Anchor-rescued candidates: 84
Semantic-rescued candidates: 3
Semantic attempts: 33
Semantic score distribution: n=33, min=0.34, median=0.50, p90=0.57, max=0.70
Embedding errors: 0
Total adjudication calls: 96
No-candidate not-related resolutions: 3
Rejected candidate findings retained: 30

| Expected class | Never adjudicated |
|---|---:|
| contradiction | 9 |
| missing_obligation | 12 |
| missing_detail | 0 |
| too_vague | 0 |
| supported | 9 |
| not_related | 24 |
| needs_human_review | 0 |

### Gate Demotions

| Reason | Count |
|---|---:|
| contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 3 |
| supported_coverage_gate:supported->not_related:weak_supported_anchor | 3 |

### No-Candidate Resolutions

| Resolution | Count |
|---|---:|
| fallback_missing_obligation | 30 |
| not_related | 3 |

### Decision Classes

| Decision class | Model | Final | Accepted | Rejected |
|---|---:|---:|---:|---:|
| contradiction | 21 | 18 | 18 | 0 |
| missing_detail | 9 | 9 | 9 | 0 |
| needs_human_review | 3 | 3 | 3 | 0 |
| not_related | 24 | 30 | 0 | 30 |
| supported | 21 | 18 | 18 | 0 |
| too_vague | 18 | 18 | 18 | 0 |

## Prompt Context

Prompt calls observed: 96
Mean prompt-token estimate: 1188
Max prompt-token estimate: 1237
Near context limit prompts: 0
Context warning threshold: 80% of num_ctx

## Stability

Labels with classification flips: 0/50
Classification variance: 0%

## Pair Results

| Run | ID | Split | Domain | Expected | Actual | Pass | LLM | Candidates | Candidate sources | Max semantic | Resolution/Gate | Latency |
|---:|---|---|---|---|---|:--:|:--:|---:|---|---:|---|---:|
| 1 | vat-contradiction-retention-delete-001 | in_domain | vat | contradiction | needs_human_review | FAIL | yes | 1 | L0/A1/S0 | 0.00 |  | 18.7s |
| 1 | vat-contradiction-retention-not-required-002 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 12.5s |
| 1 | vat-contradiction-rate-change-old-rate-003 | in_domain | vat | contradiction | missing_detail | FAIL | yes | 1 | L1/A1/S0 | 0.00 |  | 15.8s |
| 1 | vat-contradiction-rate-change-new-rate-004 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 13.0s |
| 1 | vat-contradiction-private-use-005 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 13.8s |
| 1 | packaging-contradiction-third-party-shipping-006 | in_domain | packaging_waste | contradiction | contradiction | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 11.4s |
| 1 | packaging-contradiction-supplier-purchased-007 | in_domain | packaging_waste | contradiction | not_related | FAIL | yes | 1 | L0/A1/S0 | 0.00 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 11.6s |
| 1 | packaging-contradiction-delete-evidence-008 | in_domain | packaging_waste | contradiction | contradiction | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 13.4s |
| 1 | supported-vat-private-use-percentage-001 | in_domain | vat | supported | supported | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 12.4s |
| 1 | supported-vat-evidence-retention-002 | in_domain | vat | supported | supported | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 12.8s |
| 1 | supported-vat-rate-change-003 | in_domain | vat | supported | supported | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 11.6s |
| 1 | supported-packaging-material-split-004 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 12.7s |
| 1 | supported-packaging-threshold-assessment-005 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 12.9s |
| 1 | supported-packaging-evidence-retention-006 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 15.2s |
| 1 | too-vague-vat-evidence-001 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 13.7s |
| 1 | too-vague-vat-business-use-002 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 15.3s |
| 1 | too-vague-vat-rate-change-003 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 16.0s |
| 1 | too-vague-packaging-material-004 | in_domain | packaging_waste | too_vague | not_related | FAIL | yes | 1 | L0/A1/S0 | 0.00 |  | 12.4s |
| 1 | too-vague-packaging-threshold-005 | in_domain | packaging_waste | too_vague | too_vague | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 15.6s |
| 1 | too-vague-packaging-evidence-006 | in_domain | packaging_waste | too_vague | too_vague | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 15.6s |
| 1 | missing-obligation-vat-input-tax-evidence-001 | in_domain | vat | missing_obligation | missing_obligation | PASS | no | 0 | L0/A0/S0 | 0.52 | fallback_missing_obligation | 0.3s |
| 1 | missing-obligation-vat-mixed-use-002 | in_domain | vat | missing_obligation | missing_obligation | PASS | no | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 1 | missing-obligation-vat-credit-note-003 | in_domain | vat | missing_obligation | not_related | FAIL | yes | 1 | L0/A1/S0 | 0.00 |  | 13.1s |
| 1 | missing-obligation-packaging-threshold-004 | in_domain | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | L0/A0/S0 | 0.50 | fallback_missing_obligation | 0.0s |
| 1 | missing-obligation-packaging-deadline-005 | in_domain | packaging_waste | missing_obligation | not_related | FAIL | yes | 1 | L1/A1/S0 | 0.00 |  | 15.0s |
| 1 | missing-obligation-packaging-evidence-006 | in_domain | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | L0/A0/S0 | 0.57 | fallback_missing_obligation | 0.0s |
| 1 | missing-detail-vat-retail-invoice-exception-001 | in_domain | vat | missing_detail | missing_detail | PASS | yes | 1 | L1/A0/S0 | 0.00 |  | 15.3s |
| 1 | missing-detail-vat-import-evidence-002 | in_domain | vat | missing_detail | missing_detail | PASS | yes | 1 | L1/A0/S0 | 0.00 |  | 13.6s |
| 1 | missing-detail-vat-rate-change-correction-003 | in_domain | vat | missing_detail | too_vague | FAIL | yes | 1 | L0/A1/S0 | 0.00 |  | 19.4s |
| 1 | missing-detail-packaging-material-categories-004 | in_domain | packaging_waste | missing_detail | not_related | FAIL | yes | 1 | L0/A1/S0 | 0.00 |  | 11.7s |
| 1 | missing-detail-packaging-household-scope-005 | in_domain | packaging_waste | missing_detail | not_related | FAIL | yes | 1 | L1/A1/S0 | 0.00 |  | 16.6s |
| 1 | missing-detail-packaging-reusable-006 | in_domain | packaging_waste | missing_detail | not_related | FAIL | yes | 1 | L1/A1/S0 | 0.00 |  | 17.7s |
| 1 | not-related-vat-supply-flexibility-lists-001 | in_domain | vat | not_related | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.49 | fallback_missing_obligation | 0.0s |
| 1 | not-related-vat-private-use-list-use-case-002 | in_domain | vat | not_related | not_related | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 15.8s |
| 1 | not-related-vat-rate-change-parameter-003 | in_domain | vat | not_related | not_related | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 10.8s |
| 1 | not-related-packaging-supplier-contract-004 | in_domain | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.53 | fallback_missing_obligation | 0.0s |
| 1 | not-related-packaging-age-restricted-005 | in_domain | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.49 | fallback_missing_obligation | 0.0s |
| 1 | not-related-packaging-scheduling-006 | in_domain | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.55 | fallback_missing_obligation | 0.0s |
| 1 | holdout-bribery-contradiction-associated-persons-001 | holdout | bribery_holdout | contradiction | contradiction | PASS | yes | 1 | L0/A0/S1 | 0.70 |  | 15.4s |
| 1 | holdout-bribery-contradiction-employee-only-002 | holdout | bribery_holdout | contradiction | supported | FAIL | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 1 | holdout-bribery-contradiction-facilitation-payment-003 | holdout | bribery_holdout | contradiction | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.49 | fallback_missing_obligation | 0.0s |
| 1 | holdout-bribery-contradiction-training-evidence-004 | holdout | bribery_holdout | contradiction | supported | FAIL | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 1 | holdout-bribery-supported-associated-persons-005 | holdout | bribery_holdout | supported | not_related | FAIL | yes | 1 | L1/A0/S0 | 0.00 | supported_coverage_gate:supported->not_related:weak_supported_anchor | 15.8s |
| 1 | holdout-bribery-supported-gifts-approval-006 | holdout | bribery_holdout | supported | supported | PASS | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 1 | holdout-bribery-supported-training-007 | holdout | bribery_holdout | supported | supported | PASS | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 1 | holdout-bribery-supported-reporting-008 | holdout | bribery_holdout | supported | supported | PASS | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 1 | holdout-bribery-not-related-invoice-009 | holdout | bribery_holdout | not_related | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.49 | fallback_missing_obligation | 0.0s |
| 1 | holdout-bribery-not-related-product-label-010 | holdout | bribery_holdout | not_related | supported | FAIL | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 1 | holdout-bribery-not-related-integration-011 | holdout | bribery_holdout | not_related | not_related | PASS | no | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 1 | holdout-bribery-not-related-stock-list-012 | holdout | bribery_holdout | not_related | supported | FAIL | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 2 | vat-contradiction-retention-delete-001 | in_domain | vat | contradiction | needs_human_review | FAIL | yes | 1 | L0/A1/S0 | 0.00 |  | 15.9s |
| 2 | vat-contradiction-retention-not-required-002 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 12.5s |
| 2 | vat-contradiction-rate-change-old-rate-003 | in_domain | vat | contradiction | missing_detail | FAIL | yes | 1 | L1/A1/S0 | 0.00 |  | 15.8s |
| 2 | vat-contradiction-rate-change-new-rate-004 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 13.0s |
| 2 | vat-contradiction-private-use-005 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 13.8s |
| 2 | packaging-contradiction-third-party-shipping-006 | in_domain | packaging_waste | contradiction | contradiction | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 11.4s |
| 2 | packaging-contradiction-supplier-purchased-007 | in_domain | packaging_waste | contradiction | not_related | FAIL | yes | 1 | L0/A1/S0 | 0.00 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 11.6s |
| 2 | packaging-contradiction-delete-evidence-008 | in_domain | packaging_waste | contradiction | contradiction | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 13.4s |
| 2 | supported-vat-private-use-percentage-001 | in_domain | vat | supported | supported | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 12.3s |
| 2 | supported-vat-evidence-retention-002 | in_domain | vat | supported | supported | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 12.7s |
| 2 | supported-vat-rate-change-003 | in_domain | vat | supported | supported | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 11.6s |
| 2 | supported-packaging-material-split-004 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 12.6s |
| 2 | supported-packaging-threshold-assessment-005 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 12.8s |
| 2 | supported-packaging-evidence-retention-006 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 15.2s |
| 2 | too-vague-vat-evidence-001 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 13.7s |
| 2 | too-vague-vat-business-use-002 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 15.2s |
| 2 | too-vague-vat-rate-change-003 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 16.0s |
| 2 | too-vague-packaging-material-004 | in_domain | packaging_waste | too_vague | not_related | FAIL | yes | 1 | L0/A1/S0 | 0.00 |  | 12.3s |
| 2 | too-vague-packaging-threshold-005 | in_domain | packaging_waste | too_vague | too_vague | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 15.6s |
| 2 | too-vague-packaging-evidence-006 | in_domain | packaging_waste | too_vague | too_vague | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 15.6s |
| 2 | missing-obligation-vat-input-tax-evidence-001 | in_domain | vat | missing_obligation | missing_obligation | PASS | no | 0 | L0/A0/S0 | 0.52 | fallback_missing_obligation | 0.0s |
| 2 | missing-obligation-vat-mixed-use-002 | in_domain | vat | missing_obligation | missing_obligation | PASS | no | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 2 | missing-obligation-vat-credit-note-003 | in_domain | vat | missing_obligation | not_related | FAIL | yes | 1 | L0/A1/S0 | 0.00 |  | 13.1s |
| 2 | missing-obligation-packaging-threshold-004 | in_domain | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | L0/A0/S0 | 0.50 | fallback_missing_obligation | 0.0s |
| 2 | missing-obligation-packaging-deadline-005 | in_domain | packaging_waste | missing_obligation | not_related | FAIL | yes | 1 | L1/A1/S0 | 0.00 |  | 15.0s |
| 2 | missing-obligation-packaging-evidence-006 | in_domain | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | L0/A0/S0 | 0.57 | fallback_missing_obligation | 0.0s |
| 2 | missing-detail-vat-retail-invoice-exception-001 | in_domain | vat | missing_detail | missing_detail | PASS | yes | 1 | L1/A0/S0 | 0.00 |  | 15.3s |
| 2 | missing-detail-vat-import-evidence-002 | in_domain | vat | missing_detail | missing_detail | PASS | yes | 1 | L1/A0/S0 | 0.00 |  | 13.7s |
| 2 | missing-detail-vat-rate-change-correction-003 | in_domain | vat | missing_detail | too_vague | FAIL | yes | 1 | L0/A1/S0 | 0.00 |  | 19.5s |
| 2 | missing-detail-packaging-material-categories-004 | in_domain | packaging_waste | missing_detail | not_related | FAIL | yes | 1 | L0/A1/S0 | 0.00 |  | 11.8s |
| 2 | missing-detail-packaging-household-scope-005 | in_domain | packaging_waste | missing_detail | not_related | FAIL | yes | 1 | L1/A1/S0 | 0.00 |  | 16.7s |
| 2 | missing-detail-packaging-reusable-006 | in_domain | packaging_waste | missing_detail | not_related | FAIL | yes | 1 | L1/A1/S0 | 0.00 |  | 17.4s |
| 2 | not-related-vat-supply-flexibility-lists-001 | in_domain | vat | not_related | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.49 | fallback_missing_obligation | 0.0s |
| 2 | not-related-vat-private-use-list-use-case-002 | in_domain | vat | not_related | not_related | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 15.5s |
| 2 | not-related-vat-rate-change-parameter-003 | in_domain | vat | not_related | not_related | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 10.6s |
| 2 | not-related-packaging-supplier-contract-004 | in_domain | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.53 | fallback_missing_obligation | 0.0s |
| 2 | not-related-packaging-age-restricted-005 | in_domain | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.49 | fallback_missing_obligation | 0.0s |
| 2 | not-related-packaging-scheduling-006 | in_domain | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.55 | fallback_missing_obligation | 0.0s |
| 2 | holdout-bribery-contradiction-associated-persons-001 | holdout | bribery_holdout | contradiction | contradiction | PASS | yes | 1 | L0/A0/S1 | 0.70 |  | 15.1s |
| 2 | holdout-bribery-contradiction-employee-only-002 | holdout | bribery_holdout | contradiction | supported | FAIL | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 2 | holdout-bribery-contradiction-facilitation-payment-003 | holdout | bribery_holdout | contradiction | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.49 | fallback_missing_obligation | 0.0s |
| 2 | holdout-bribery-contradiction-training-evidence-004 | holdout | bribery_holdout | contradiction | supported | FAIL | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 2 | holdout-bribery-supported-associated-persons-005 | holdout | bribery_holdout | supported | not_related | FAIL | yes | 1 | L1/A0/S0 | 0.00 | supported_coverage_gate:supported->not_related:weak_supported_anchor | 15.5s |
| 2 | holdout-bribery-supported-gifts-approval-006 | holdout | bribery_holdout | supported | supported | PASS | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 2 | holdout-bribery-supported-training-007 | holdout | bribery_holdout | supported | supported | PASS | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 2 | holdout-bribery-supported-reporting-008 | holdout | bribery_holdout | supported | supported | PASS | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 2 | holdout-bribery-not-related-invoice-009 | holdout | bribery_holdout | not_related | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.49 | fallback_missing_obligation | 0.0s |
| 2 | holdout-bribery-not-related-product-label-010 | holdout | bribery_holdout | not_related | supported | FAIL | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 2 | holdout-bribery-not-related-integration-011 | holdout | bribery_holdout | not_related | not_related | PASS | no | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 2 | holdout-bribery-not-related-stock-list-012 | holdout | bribery_holdout | not_related | supported | FAIL | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 3 | vat-contradiction-retention-delete-001 | in_domain | vat | contradiction | needs_human_review | FAIL | yes | 1 | L0/A1/S0 | 0.00 |  | 15.6s |
| 3 | vat-contradiction-retention-not-required-002 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 12.3s |
| 3 | vat-contradiction-rate-change-old-rate-003 | in_domain | vat | contradiction | missing_detail | FAIL | yes | 1 | L1/A1/S0 | 0.00 |  | 15.5s |
| 3 | vat-contradiction-rate-change-new-rate-004 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 12.8s |
| 3 | vat-contradiction-private-use-005 | in_domain | vat | contradiction | contradiction | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 13.6s |
| 3 | packaging-contradiction-third-party-shipping-006 | in_domain | packaging_waste | contradiction | contradiction | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 11.2s |
| 3 | packaging-contradiction-supplier-purchased-007 | in_domain | packaging_waste | contradiction | not_related | FAIL | yes | 1 | L0/A1/S0 | 0.00 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 11.4s |
| 3 | packaging-contradiction-delete-evidence-008 | in_domain | packaging_waste | contradiction | contradiction | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 13.1s |
| 3 | supported-vat-private-use-percentage-001 | in_domain | vat | supported | supported | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 12.1s |
| 3 | supported-vat-evidence-retention-002 | in_domain | vat | supported | supported | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 12.5s |
| 3 | supported-vat-rate-change-003 | in_domain | vat | supported | supported | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 11.4s |
| 3 | supported-packaging-material-split-004 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 12.4s |
| 3 | supported-packaging-threshold-assessment-005 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 12.6s |
| 3 | supported-packaging-evidence-retention-006 | in_domain | packaging_waste | supported | supported | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 14.9s |
| 3 | too-vague-vat-evidence-001 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 13.5s |
| 3 | too-vague-vat-business-use-002 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 15.0s |
| 3 | too-vague-vat-rate-change-003 | in_domain | vat | too_vague | too_vague | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 15.7s |
| 3 | too-vague-packaging-material-004 | in_domain | packaging_waste | too_vague | not_related | FAIL | yes | 1 | L0/A1/S0 | 0.00 |  | 12.1s |
| 3 | too-vague-packaging-threshold-005 | in_domain | packaging_waste | too_vague | too_vague | PASS | yes | 1 | L1/A1/S0 | 0.00 |  | 15.3s |
| 3 | too-vague-packaging-evidence-006 | in_domain | packaging_waste | too_vague | too_vague | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 15.3s |
| 3 | missing-obligation-vat-input-tax-evidence-001 | in_domain | vat | missing_obligation | missing_obligation | PASS | no | 0 | L0/A0/S0 | 0.52 | fallback_missing_obligation | 0.0s |
| 3 | missing-obligation-vat-mixed-use-002 | in_domain | vat | missing_obligation | missing_obligation | PASS | no | 0 | L0/A0/S0 | 0.00 | fallback_missing_obligation | 0.0s |
| 3 | missing-obligation-vat-credit-note-003 | in_domain | vat | missing_obligation | not_related | FAIL | yes | 1 | L0/A1/S0 | 0.00 |  | 12.9s |
| 3 | missing-obligation-packaging-threshold-004 | in_domain | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | L0/A0/S0 | 0.50 | fallback_missing_obligation | 0.0s |
| 3 | missing-obligation-packaging-deadline-005 | in_domain | packaging_waste | missing_obligation | not_related | FAIL | yes | 1 | L1/A1/S0 | 0.00 |  | 14.9s |
| 3 | missing-obligation-packaging-evidence-006 | in_domain | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | L0/A0/S0 | 0.57 | fallback_missing_obligation | 0.0s |
| 3 | missing-detail-vat-retail-invoice-exception-001 | in_domain | vat | missing_detail | missing_detail | PASS | yes | 1 | L1/A0/S0 | 0.00 |  | 15.3s |
| 3 | missing-detail-vat-import-evidence-002 | in_domain | vat | missing_detail | missing_detail | PASS | yes | 1 | L1/A0/S0 | 0.00 |  | 13.9s |
| 3 | missing-detail-vat-rate-change-correction-003 | in_domain | vat | missing_detail | too_vague | FAIL | yes | 1 | L0/A1/S0 | 0.00 |  | 19.9s |
| 3 | missing-detail-packaging-material-categories-004 | in_domain | packaging_waste | missing_detail | not_related | FAIL | yes | 1 | L0/A1/S0 | 0.00 |  | 12.0s |
| 3 | missing-detail-packaging-household-scope-005 | in_domain | packaging_waste | missing_detail | not_related | FAIL | yes | 1 | L1/A1/S0 | 0.00 |  | 17.0s |
| 3 | missing-detail-packaging-reusable-006 | in_domain | packaging_waste | missing_detail | not_related | FAIL | yes | 1 | L1/A1/S0 | 0.00 |  | 17.8s |
| 3 | not-related-vat-supply-flexibility-lists-001 | in_domain | vat | not_related | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.49 | fallback_missing_obligation | 0.0s |
| 3 | not-related-vat-private-use-list-use-case-002 | in_domain | vat | not_related | not_related | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 15.8s |
| 3 | not-related-vat-rate-change-parameter-003 | in_domain | vat | not_related | not_related | PASS | yes | 1 | L0/A1/S0 | 0.00 |  | 10.8s |
| 3 | not-related-packaging-supplier-contract-004 | in_domain | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.53 | fallback_missing_obligation | 0.0s |
| 3 | not-related-packaging-age-restricted-005 | in_domain | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.49 | fallback_missing_obligation | 0.0s |
| 3 | not-related-packaging-scheduling-006 | in_domain | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.55 | fallback_missing_obligation | 0.0s |
| 3 | holdout-bribery-contradiction-associated-persons-001 | holdout | bribery_holdout | contradiction | contradiction | PASS | yes | 1 | L0/A0/S1 | 0.70 |  | 15.4s |
| 3 | holdout-bribery-contradiction-employee-only-002 | holdout | bribery_holdout | contradiction | supported | FAIL | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 3 | holdout-bribery-contradiction-facilitation-payment-003 | holdout | bribery_holdout | contradiction | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.49 | fallback_missing_obligation | 0.0s |
| 3 | holdout-bribery-contradiction-training-evidence-004 | holdout | bribery_holdout | contradiction | supported | FAIL | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 3 | holdout-bribery-supported-associated-persons-005 | holdout | bribery_holdout | supported | not_related | FAIL | yes | 1 | L1/A0/S0 | 0.00 | supported_coverage_gate:supported->not_related:weak_supported_anchor | 15.9s |
| 3 | holdout-bribery-supported-gifts-approval-006 | holdout | bribery_holdout | supported | supported | PASS | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 3 | holdout-bribery-supported-training-007 | holdout | bribery_holdout | supported | supported | PASS | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 3 | holdout-bribery-supported-reporting-008 | holdout | bribery_holdout | supported | supported | PASS | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 3 | holdout-bribery-not-related-invoice-009 | holdout | bribery_holdout | not_related | missing_obligation | FAIL | no | 0 | L0/A0/S0 | 0.49 | fallback_missing_obligation | 0.0s |
| 3 | holdout-bribery-not-related-product-label-010 | holdout | bribery_holdout | not_related | supported | FAIL | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |
| 3 | holdout-bribery-not-related-integration-011 | holdout | bribery_holdout | not_related | not_related | PASS | no | 0 | L0/A0/S0 | 0.34 | not_related | 0.0s |
| 3 | holdout-bribery-not-related-stock-list-012 | holdout | bribery_holdout | not_related | supported | FAIL | no | 0 | L0/A0/S0 | 0.00 |  | 0.0s |