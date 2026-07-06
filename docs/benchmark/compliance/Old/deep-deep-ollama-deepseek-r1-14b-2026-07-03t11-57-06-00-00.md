# Compliance Reasoning Evaluation - 33/114 passed (29%)

Generated: 2026-07-03T11:57:06+00:00
Depth: deep
Model profile: deep=ollama:deepseek-r1:14b
Runs: 3
Fake generator: False
Throttle deep: False

Total runtime: 719.6s
Mean pair latency: 6.3s
P95 pair latency: 14.1s

## Per-Class Metrics

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| contradiction | 67% | 25% | 36% | 24 |
| missing_obligation | 19% | 100% | 32% | 18 |
| missing_detail | 100% | 17% | 29% | 18 |
| too_vague | 0% | 0% | 0% | 18 |
| supported | 100% | 33% | 50% | 18 |
| not_related | 0% | 0% | 0% | 18 |

## Confusion Matrix

| Expected \ Actual | contradiction | missing_obligation | missing_detail | too_vague | supported | not_related |
|---|---:|---:|---:|---:|---:|---:|
| contradiction | 6 | 18 | 0 | 0 | 0 | 0 |
| missing_obligation | 0 | 18 | 0 | 0 | 0 | 0 |
| missing_detail | 3 | 12 | 3 | 0 | 0 | 0 |
| too_vague | 0 | 18 | 0 | 0 | 0 | 0 |
| supported | 0 | 12 | 0 | 0 | 6 | 0 |
| not_related | 0 | 18 | 0 | 0 | 0 | 0 |

## Stability

Labels with classification flips: 0/38
Classification variance: 0%

## Pair Results

| Run | ID | Domain | Expected | Actual | Pass | Latency |
|---:|---|---|---|---|:--:|---:|
| 1 | vat-contradiction-retention-delete-001 | vat | contradiction | missing_obligation | FAIL | 13.2s |
| 1 | vat-contradiction-retention-not-required-002 | vat | contradiction | missing_obligation | FAIL | 13.7s |
| 1 | vat-contradiction-rate-change-old-rate-003 | vat | contradiction | missing_obligation | FAIL | 11.9s |
| 1 | vat-contradiction-rate-change-new-rate-004 | vat | contradiction | missing_obligation | FAIL | 11.8s |
| 1 | vat-contradiction-private-use-005 | vat | contradiction | contradiction | PASS | 13.8s |
| 1 | packaging-contradiction-third-party-shipping-006 | packaging_waste | contradiction | missing_obligation | FAIL | 10.5s |
| 1 | packaging-contradiction-supplier-purchased-007 | packaging_waste | contradiction | missing_obligation | FAIL | 0.0s |
| 1 | packaging-contradiction-delete-evidence-008 | packaging_waste | contradiction | contradiction | PASS | 14.9s |
| 1 | supported-vat-private-use-percentage-001 | vat | supported | missing_obligation | FAIL | 11.8s |
| 1 | supported-vat-evidence-retention-002 | vat | supported | supported | PASS | 13.8s |
| 1 | supported-vat-rate-change-003 | vat | supported | missing_obligation | FAIL | 14.0s |
| 1 | supported-packaging-material-split-004 | packaging_waste | supported | supported | PASS | 14.1s |
| 1 | supported-packaging-threshold-assessment-005 | packaging_waste | supported | missing_obligation | FAIL | 11.6s |
| 1 | supported-packaging-evidence-retention-006 | packaging_waste | supported | missing_obligation | FAIL | 12.6s |
| 1 | too-vague-vat-evidence-001 | vat | too_vague | missing_obligation | FAIL | 0.0s |
| 1 | too-vague-vat-business-use-002 | vat | too_vague | missing_obligation | FAIL | 0.0s |
| 1 | too-vague-vat-rate-change-003 | vat | too_vague | missing_obligation | FAIL | 0.0s |
| 1 | too-vague-packaging-material-004 | packaging_waste | too_vague | missing_obligation | FAIL | 0.0s |
| 1 | too-vague-packaging-threshold-005 | packaging_waste | too_vague | missing_obligation | FAIL | 0.0s |
| 1 | too-vague-packaging-evidence-006 | packaging_waste | too_vague | missing_obligation | FAIL | 0.0s |
| 1 | missing-obligation-vat-input-tax-evidence-001 | vat | missing_obligation | missing_obligation | PASS | 0.0s |
| 1 | missing-obligation-vat-mixed-use-002 | vat | missing_obligation | missing_obligation | PASS | 0.0s |
| 1 | missing-obligation-vat-credit-note-003 | vat | missing_obligation | missing_obligation | PASS | 0.0s |
| 1 | missing-obligation-packaging-threshold-004 | packaging_waste | missing_obligation | missing_obligation | PASS | 0.0s |
| 1 | missing-obligation-packaging-deadline-005 | packaging_waste | missing_obligation | missing_obligation | PASS | 11.3s |
| 1 | missing-obligation-packaging-evidence-006 | packaging_waste | missing_obligation | missing_obligation | PASS | 0.0s |
| 1 | missing-detail-vat-retail-invoice-exception-001 | vat | missing_detail | missing_detail | PASS | 13.2s |
| 1 | missing-detail-vat-import-evidence-002 | vat | missing_detail | contradiction | FAIL | 12.8s |
| 1 | missing-detail-vat-rate-change-correction-003 | vat | missing_detail | missing_obligation | FAIL | 0.0s |
| 1 | missing-detail-packaging-material-categories-004 | packaging_waste | missing_detail | missing_obligation | FAIL | 0.0s |
| 1 | missing-detail-packaging-household-scope-005 | packaging_waste | missing_detail | missing_obligation | FAIL | 11.4s |
| 1 | missing-detail-packaging-reusable-006 | packaging_waste | missing_detail | missing_obligation | FAIL | 14.1s |
| 1 | not-related-vat-supply-flexibility-lists-001 | vat | not_related | missing_obligation | FAIL | 0.0s |
| 1 | not-related-vat-private-use-list-use-case-002 | vat | not_related | missing_obligation | FAIL | 11.2s |
| 1 | not-related-vat-rate-change-parameter-003 | vat | not_related | missing_obligation | FAIL | 0.0s |
| 1 | not-related-packaging-supplier-contract-004 | packaging_waste | not_related | missing_obligation | FAIL | 0.0s |
| 1 | not-related-packaging-age-restricted-005 | packaging_waste | not_related | missing_obligation | FAIL | 0.0s |
| 1 | not-related-packaging-scheduling-006 | packaging_waste | not_related | missing_obligation | FAIL | 0.0s |
| 2 | vat-contradiction-retention-delete-001 | vat | contradiction | missing_obligation | FAIL | 11.2s |
| 2 | vat-contradiction-retention-not-required-002 | vat | contradiction | missing_obligation | FAIL | 13.9s |
| 2 | vat-contradiction-rate-change-old-rate-003 | vat | contradiction | missing_obligation | FAIL | 12.0s |
| 2 | vat-contradiction-rate-change-new-rate-004 | vat | contradiction | missing_obligation | FAIL | 11.8s |
| 2 | vat-contradiction-private-use-005 | vat | contradiction | contradiction | PASS | 13.5s |
| 2 | packaging-contradiction-third-party-shipping-006 | packaging_waste | contradiction | missing_obligation | FAIL | 10.5s |
| 2 | packaging-contradiction-supplier-purchased-007 | packaging_waste | contradiction | missing_obligation | FAIL | 0.0s |
| 2 | packaging-contradiction-delete-evidence-008 | packaging_waste | contradiction | contradiction | PASS | 14.9s |
| 2 | supported-vat-private-use-percentage-001 | vat | supported | missing_obligation | FAIL | 11.8s |
| 2 | supported-vat-evidence-retention-002 | vat | supported | supported | PASS | 13.9s |
| 2 | supported-vat-rate-change-003 | vat | supported | missing_obligation | FAIL | 14.0s |
| 2 | supported-packaging-material-split-004 | packaging_waste | supported | supported | PASS | 13.9s |
| 2 | supported-packaging-threshold-assessment-005 | packaging_waste | supported | missing_obligation | FAIL | 11.6s |
| 2 | supported-packaging-evidence-retention-006 | packaging_waste | supported | missing_obligation | FAIL | 12.6s |
| 2 | too-vague-vat-evidence-001 | vat | too_vague | missing_obligation | FAIL | 0.0s |
| 2 | too-vague-vat-business-use-002 | vat | too_vague | missing_obligation | FAIL | 0.0s |
| 2 | too-vague-vat-rate-change-003 | vat | too_vague | missing_obligation | FAIL | 0.0s |
| 2 | too-vague-packaging-material-004 | packaging_waste | too_vague | missing_obligation | FAIL | 0.0s |
| 2 | too-vague-packaging-threshold-005 | packaging_waste | too_vague | missing_obligation | FAIL | 0.0s |
| 2 | too-vague-packaging-evidence-006 | packaging_waste | too_vague | missing_obligation | FAIL | 0.0s |
| 2 | missing-obligation-vat-input-tax-evidence-001 | vat | missing_obligation | missing_obligation | PASS | 0.0s |
| 2 | missing-obligation-vat-mixed-use-002 | vat | missing_obligation | missing_obligation | PASS | 0.0s |
| 2 | missing-obligation-vat-credit-note-003 | vat | missing_obligation | missing_obligation | PASS | 0.0s |
| 2 | missing-obligation-packaging-threshold-004 | packaging_waste | missing_obligation | missing_obligation | PASS | 0.0s |
| 2 | missing-obligation-packaging-deadline-005 | packaging_waste | missing_obligation | missing_obligation | PASS | 11.2s |
| 2 | missing-obligation-packaging-evidence-006 | packaging_waste | missing_obligation | missing_obligation | PASS | 0.0s |
| 2 | missing-detail-vat-retail-invoice-exception-001 | vat | missing_detail | missing_detail | PASS | 13.0s |
| 2 | missing-detail-vat-import-evidence-002 | vat | missing_detail | contradiction | FAIL | 12.6s |
| 2 | missing-detail-vat-rate-change-correction-003 | vat | missing_detail | missing_obligation | FAIL | 0.0s |
| 2 | missing-detail-packaging-material-categories-004 | packaging_waste | missing_detail | missing_obligation | FAIL | 0.0s |
| 2 | missing-detail-packaging-household-scope-005 | packaging_waste | missing_detail | missing_obligation | FAIL | 11.4s |
| 2 | missing-detail-packaging-reusable-006 | packaging_waste | missing_detail | missing_obligation | FAIL | 14.1s |
| 2 | not-related-vat-supply-flexibility-lists-001 | vat | not_related | missing_obligation | FAIL | 0.0s |
| 2 | not-related-vat-private-use-list-use-case-002 | vat | not_related | missing_obligation | FAIL | 11.1s |
| 2 | not-related-vat-rate-change-parameter-003 | vat | not_related | missing_obligation | FAIL | 0.0s |
| 2 | not-related-packaging-supplier-contract-004 | packaging_waste | not_related | missing_obligation | FAIL | 0.0s |
| 2 | not-related-packaging-age-restricted-005 | packaging_waste | not_related | missing_obligation | FAIL | 0.0s |
| 2 | not-related-packaging-scheduling-006 | packaging_waste | not_related | missing_obligation | FAIL | 0.0s |
| 3 | vat-contradiction-retention-delete-001 | vat | contradiction | missing_obligation | FAIL | 11.2s |
| 3 | vat-contradiction-retention-not-required-002 | vat | contradiction | missing_obligation | FAIL | 13.9s |
| 3 | vat-contradiction-rate-change-old-rate-003 | vat | contradiction | missing_obligation | FAIL | 12.0s |
| 3 | vat-contradiction-rate-change-new-rate-004 | vat | contradiction | missing_obligation | FAIL | 11.6s |
| 3 | vat-contradiction-private-use-005 | vat | contradiction | contradiction | PASS | 13.5s |
| 3 | packaging-contradiction-third-party-shipping-006 | packaging_waste | contradiction | missing_obligation | FAIL | 10.5s |
| 3 | packaging-contradiction-supplier-purchased-007 | packaging_waste | contradiction | missing_obligation | FAIL | 0.0s |
| 3 | packaging-contradiction-delete-evidence-008 | packaging_waste | contradiction | contradiction | PASS | 14.9s |
| 3 | supported-vat-private-use-percentage-001 | vat | supported | missing_obligation | FAIL | 11.8s |
| 3 | supported-vat-evidence-retention-002 | vat | supported | supported | PASS | 13.9s |
| 3 | supported-vat-rate-change-003 | vat | supported | missing_obligation | FAIL | 14.1s |
| 3 | supported-packaging-material-split-004 | packaging_waste | supported | supported | PASS | 13.8s |
| 3 | supported-packaging-threshold-assessment-005 | packaging_waste | supported | missing_obligation | FAIL | 11.6s |
| 3 | supported-packaging-evidence-retention-006 | packaging_waste | supported | missing_obligation | FAIL | 12.6s |
| 3 | too-vague-vat-evidence-001 | vat | too_vague | missing_obligation | FAIL | 0.0s |
| 3 | too-vague-vat-business-use-002 | vat | too_vague | missing_obligation | FAIL | 0.0s |
| 3 | too-vague-vat-rate-change-003 | vat | too_vague | missing_obligation | FAIL | 0.0s |
| 3 | too-vague-packaging-material-004 | packaging_waste | too_vague | missing_obligation | FAIL | 0.0s |
| 3 | too-vague-packaging-threshold-005 | packaging_waste | too_vague | missing_obligation | FAIL | 0.0s |
| 3 | too-vague-packaging-evidence-006 | packaging_waste | too_vague | missing_obligation | FAIL | 0.0s |
| 3 | missing-obligation-vat-input-tax-evidence-001 | vat | missing_obligation | missing_obligation | PASS | 0.0s |
| 3 | missing-obligation-vat-mixed-use-002 | vat | missing_obligation | missing_obligation | PASS | 0.0s |
| 3 | missing-obligation-vat-credit-note-003 | vat | missing_obligation | missing_obligation | PASS | 0.0s |
| 3 | missing-obligation-packaging-threshold-004 | packaging_waste | missing_obligation | missing_obligation | PASS | 0.0s |
| 3 | missing-obligation-packaging-deadline-005 | packaging_waste | missing_obligation | missing_obligation | PASS | 11.2s |
| 3 | missing-obligation-packaging-evidence-006 | packaging_waste | missing_obligation | missing_obligation | PASS | 0.0s |
| 3 | missing-detail-vat-retail-invoice-exception-001 | vat | missing_detail | missing_detail | PASS | 13.0s |
| 3 | missing-detail-vat-import-evidence-002 | vat | missing_detail | contradiction | FAIL | 12.5s |
| 3 | missing-detail-vat-rate-change-correction-003 | vat | missing_detail | missing_obligation | FAIL | 0.0s |
| 3 | missing-detail-packaging-material-categories-004 | packaging_waste | missing_detail | missing_obligation | FAIL | 0.0s |
| 3 | missing-detail-packaging-household-scope-005 | packaging_waste | missing_detail | missing_obligation | FAIL | 11.4s |
| 3 | missing-detail-packaging-reusable-006 | packaging_waste | missing_detail | missing_obligation | FAIL | 14.1s |
| 3 | not-related-vat-supply-flexibility-lists-001 | vat | not_related | missing_obligation | FAIL | 0.0s |
| 3 | not-related-vat-private-use-list-use-case-002 | vat | not_related | missing_obligation | FAIL | 11.1s |
| 3 | not-related-vat-rate-change-parameter-003 | vat | not_related | missing_obligation | FAIL | 0.0s |
| 3 | not-related-packaging-supplier-contract-004 | packaging_waste | not_related | missing_obligation | FAIL | 0.0s |
| 3 | not-related-packaging-age-restricted-005 | packaging_waste | not_related | missing_obligation | FAIL | 0.0s |
| 3 | not-related-packaging-scheduling-006 | packaging_waste | not_related | missing_obligation | FAIL | 0.0s |