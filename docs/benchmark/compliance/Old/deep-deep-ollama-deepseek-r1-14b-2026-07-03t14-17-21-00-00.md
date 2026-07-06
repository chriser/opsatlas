# Compliance Reasoning Evaluation - 33/114 passed (29%)

Generated: 2026-07-03T14:17:21+00:00
Depth: deep
Model profile: deep=ollama:deepseek-r1:14b
Runs: 3
Fake generator: False
Throttle deep: False
Safety gates disabled: False

Total runtime: 917.4s
Mean pair latency: 8.0s
P95 pair latency: 18.2s
Mean LLM-called latency: 14.6s
Mean deterministic latency: 0.0s

## Per-Class Metrics

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| contradiction | 100% | 25% | 40% | 24 |
| missing_obligation | 26% | 100% | 41% | 18 |
| missing_detail | 0% | 0% | 0% | 18 |
| too_vague | 0% | 0% | 0% | 18 |
| supported | 100% | 33% | 50% | 18 |
| not_related | 9% | 17% | 12% | 18 |

## Confusion Matrix

| Expected \ Actual | contradiction | missing_obligation | missing_detail | too_vague | supported | not_related |
|---|---:|---:|---:|---:|---:|---:|
| contradiction | 6 | 9 | 0 | 0 | 0 | 9 |
| missing_obligation | 0 | 18 | 0 | 0 | 0 | 0 |
| missing_detail | 0 | 9 | 0 | 0 | 0 | 9 |
| too_vague | 0 | 18 | 0 | 0 | 0 | 0 |
| supported | 0 | 0 | 0 | 0 | 6 | 12 |
| not_related | 0 | 15 | 0 | 0 | 0 | 3 |

## Observability

Rows that called the LLM: 63/114
Adjudicator coverage: 55%
Never adjudicated rows: 51
Total candidate count: 63
Total adjudication calls: 63
Rejected candidate findings retained: 33

| Expected class | Never adjudicated |
|---|---:|
| contradiction | 3 |
| missing_obligation | 15 |
| missing_detail | 6 |
| too_vague | 12 |
| supported | 0 |
| not_related | 15 |

### Gate Demotions

| Reason | Count |
|---|---:|
| contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 6 |
| supported_coverage_gate:supported->not_related:supported_requested_change | 6 |
| supported_coverage_gate:supported->not_related:weak_supported_anchor | 12 |

### Decision Classes

| Decision class | Model | Final | Accepted | Rejected |
|---|---:|---:|---:|---:|
| contradiction | 12 | 6 | 6 | 0 |
| missing_obligation | 18 | 18 | 0 | 0 |
| not_related | 9 | 33 | 0 | 33 |
| supported | 24 | 6 | 6 | 0 |

## Prompt Context

Prompt calls observed: 63
Mean prompt-token estimate: 871
Max prompt-token estimate: 914
Near context limit prompts: 0
Context warning threshold: 80% of num_ctx

## Stability

Labels with classification flips: 0/38
Classification variance: 0%

## Pair Results

| Run | ID | Domain | Expected | Actual | Pass | LLM | Candidates | Gate reason | Latency |
|---:|---|---|---|---|:--:|:--:|---:|---|---:|
| 1 | vat-contradiction-retention-delete-001 | vat | contradiction | missing_obligation | FAIL | yes | 1 |  | 19.1s |
| 1 | vat-contradiction-retention-not-required-002 | vat | contradiction | contradiction | PASS | yes | 1 |  | 15.2s |
| 1 | vat-contradiction-rate-change-old-rate-003 | vat | contradiction | not_related | FAIL | yes | 1 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 16.4s |
| 1 | vat-contradiction-rate-change-new-rate-004 | vat | contradiction | not_related | FAIL | yes | 1 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 16.0s |
| 1 | vat-contradiction-private-use-005 | vat | contradiction | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:supported_requested_change | 15.6s |
| 1 | packaging-contradiction-third-party-shipping-006 | packaging_waste | contradiction | missing_obligation | FAIL | yes | 1 |  | 14.8s |
| 1 | packaging-contradiction-supplier-purchased-007 | packaging_waste | contradiction | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | packaging-contradiction-delete-evidence-008 | packaging_waste | contradiction | contradiction | PASS | yes | 1 |  | 10.7s |
| 1 | supported-vat-private-use-percentage-001 | vat | supported | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:weak_supported_anchor | 12.3s |
| 1 | supported-vat-evidence-retention-002 | vat | supported | supported | PASS | yes | 1 |  | 12.3s |
| 1 | supported-vat-rate-change-003 | vat | supported | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:weak_supported_anchor | 11.9s |
| 1 | supported-packaging-material-split-004 | packaging_waste | supported | supported | PASS | yes | 1 |  | 12.5s |
| 1 | supported-packaging-threshold-assessment-005 | packaging_waste | supported | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:weak_supported_anchor | 10.2s |
| 1 | supported-packaging-evidence-retention-006 | packaging_waste | supported | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:weak_supported_anchor | 12.7s |
| 1 | too-vague-vat-evidence-001 | vat | too_vague | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | too-vague-vat-business-use-002 | vat | too_vague | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | too-vague-vat-rate-change-003 | vat | too_vague | missing_obligation | FAIL | yes | 1 |  | 12.4s |
| 1 | too-vague-packaging-material-004 | packaging_waste | too_vague | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | too-vague-packaging-threshold-005 | packaging_waste | too_vague | missing_obligation | FAIL | yes | 1 |  | 18.0s |
| 1 | too-vague-packaging-evidence-006 | packaging_waste | too_vague | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | missing-obligation-vat-input-tax-evidence-001 | vat | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | missing-obligation-vat-mixed-use-002 | vat | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | missing-obligation-vat-credit-note-003 | vat | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | missing-obligation-packaging-threshold-004 | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | missing-obligation-packaging-deadline-005 | packaging_waste | missing_obligation | missing_obligation | PASS | yes | 1 |  | 12.9s |
| 1 | missing-obligation-packaging-evidence-006 | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | missing-detail-vat-retail-invoice-exception-001 | vat | missing_detail | missing_obligation | FAIL | yes | 1 |  | 15.2s |
| 1 | missing-detail-vat-import-evidence-002 | vat | missing_detail | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:supported_requested_change | 17.9s |
| 1 | missing-detail-vat-rate-change-correction-003 | vat | missing_detail | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | missing-detail-packaging-material-categories-004 | packaging_waste | missing_detail | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | missing-detail-packaging-household-scope-005 | packaging_waste | missing_detail | not_related | FAIL | yes | 1 |  | 18.2s |
| 1 | missing-detail-packaging-reusable-006 | packaging_waste | missing_detail | not_related | FAIL | yes | 1 |  | 19.3s |
| 1 | not-related-vat-supply-flexibility-lists-001 | vat | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | not-related-vat-private-use-list-use-case-002 | vat | not_related | not_related | PASS | yes | 1 |  | 14.8s |
| 1 | not-related-vat-rate-change-parameter-003 | vat | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | not-related-packaging-supplier-contract-004 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | not-related-packaging-age-restricted-005 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 1 | not-related-packaging-scheduling-006 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | vat-contradiction-retention-delete-001 | vat | contradiction | missing_obligation | FAIL | yes | 1 |  | 17.0s |
| 2 | vat-contradiction-retention-not-required-002 | vat | contradiction | contradiction | PASS | yes | 1 |  | 14.9s |
| 2 | vat-contradiction-rate-change-old-rate-003 | vat | contradiction | not_related | FAIL | yes | 1 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 16.3s |
| 2 | vat-contradiction-rate-change-new-rate-004 | vat | contradiction | not_related | FAIL | yes | 1 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 12.7s |
| 2 | vat-contradiction-private-use-005 | vat | contradiction | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:supported_requested_change | 15.4s |
| 2 | packaging-contradiction-third-party-shipping-006 | packaging_waste | contradiction | missing_obligation | FAIL | yes | 1 |  | 14.8s |
| 2 | packaging-contradiction-supplier-purchased-007 | packaging_waste | contradiction | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | packaging-contradiction-delete-evidence-008 | packaging_waste | contradiction | contradiction | PASS | yes | 1 |  | 10.7s |
| 2 | supported-vat-private-use-percentage-001 | vat | supported | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:weak_supported_anchor | 12.3s |
| 2 | supported-vat-evidence-retention-002 | vat | supported | supported | PASS | yes | 1 |  | 12.2s |
| 2 | supported-vat-rate-change-003 | vat | supported | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:weak_supported_anchor | 11.9s |
| 2 | supported-packaging-material-split-004 | packaging_waste | supported | supported | PASS | yes | 1 |  | 12.5s |
| 2 | supported-packaging-threshold-assessment-005 | packaging_waste | supported | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:weak_supported_anchor | 10.3s |
| 2 | supported-packaging-evidence-retention-006 | packaging_waste | supported | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:weak_supported_anchor | 12.8s |
| 2 | too-vague-vat-evidence-001 | vat | too_vague | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | too-vague-vat-business-use-002 | vat | too_vague | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | too-vague-vat-rate-change-003 | vat | too_vague | missing_obligation | FAIL | yes | 1 |  | 12.4s |
| 2 | too-vague-packaging-material-004 | packaging_waste | too_vague | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | too-vague-packaging-threshold-005 | packaging_waste | too_vague | missing_obligation | FAIL | yes | 1 |  | 18.1s |
| 2 | too-vague-packaging-evidence-006 | packaging_waste | too_vague | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | missing-obligation-vat-input-tax-evidence-001 | vat | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | missing-obligation-vat-mixed-use-002 | vat | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | missing-obligation-vat-credit-note-003 | vat | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | missing-obligation-packaging-threshold-004 | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | missing-obligation-packaging-deadline-005 | packaging_waste | missing_obligation | missing_obligation | PASS | yes | 1 |  | 13.0s |
| 2 | missing-obligation-packaging-evidence-006 | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | missing-detail-vat-retail-invoice-exception-001 | vat | missing_detail | missing_obligation | FAIL | yes | 1 |  | 12.4s |
| 2 | missing-detail-vat-import-evidence-002 | vat | missing_detail | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:supported_requested_change | 17.9s |
| 2 | missing-detail-vat-rate-change-correction-003 | vat | missing_detail | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | missing-detail-packaging-material-categories-004 | packaging_waste | missing_detail | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | missing-detail-packaging-household-scope-005 | packaging_waste | missing_detail | not_related | FAIL | yes | 1 |  | 24.5s |
| 2 | missing-detail-packaging-reusable-006 | packaging_waste | missing_detail | not_related | FAIL | yes | 1 |  | 19.3s |
| 2 | not-related-vat-supply-flexibility-lists-001 | vat | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | not-related-vat-private-use-list-use-case-002 | vat | not_related | not_related | PASS | yes | 1 |  | 14.6s |
| 2 | not-related-vat-rate-change-parameter-003 | vat | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | not-related-packaging-supplier-contract-004 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | not-related-packaging-age-restricted-005 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 2 | not-related-packaging-scheduling-006 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | vat-contradiction-retention-delete-001 | vat | contradiction | missing_obligation | FAIL | yes | 1 |  | 16.8s |
| 3 | vat-contradiction-retention-not-required-002 | vat | contradiction | contradiction | PASS | yes | 1 |  | 15.0s |
| 3 | vat-contradiction-rate-change-old-rate-003 | vat | contradiction | not_related | FAIL | yes | 1 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 16.4s |
| 3 | vat-contradiction-rate-change-new-rate-004 | vat | contradiction | not_related | FAIL | yes | 1 | contradiction_safety_gate:contradiction->not_related:low_concrete_obligation_overlap | 12.7s |
| 3 | vat-contradiction-private-use-005 | vat | contradiction | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:supported_requested_change | 15.5s |
| 3 | packaging-contradiction-third-party-shipping-006 | packaging_waste | contradiction | missing_obligation | FAIL | yes | 1 |  | 14.7s |
| 3 | packaging-contradiction-supplier-purchased-007 | packaging_waste | contradiction | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | packaging-contradiction-delete-evidence-008 | packaging_waste | contradiction | contradiction | PASS | yes | 1 |  | 10.8s |
| 3 | supported-vat-private-use-percentage-001 | vat | supported | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:weak_supported_anchor | 12.4s |
| 3 | supported-vat-evidence-retention-002 | vat | supported | supported | PASS | yes | 1 |  | 12.3s |
| 3 | supported-vat-rate-change-003 | vat | supported | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:weak_supported_anchor | 12.0s |
| 3 | supported-packaging-material-split-004 | packaging_waste | supported | supported | PASS | yes | 1 |  | 12.5s |
| 3 | supported-packaging-threshold-assessment-005 | packaging_waste | supported | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:weak_supported_anchor | 10.3s |
| 3 | supported-packaging-evidence-retention-006 | packaging_waste | supported | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:weak_supported_anchor | 12.8s |
| 3 | too-vague-vat-evidence-001 | vat | too_vague | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | too-vague-vat-business-use-002 | vat | too_vague | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | too-vague-vat-rate-change-003 | vat | too_vague | missing_obligation | FAIL | yes | 1 |  | 12.3s |
| 3 | too-vague-packaging-material-004 | packaging_waste | too_vague | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | too-vague-packaging-threshold-005 | packaging_waste | too_vague | missing_obligation | FAIL | yes | 1 |  | 18.1s |
| 3 | too-vague-packaging-evidence-006 | packaging_waste | too_vague | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | missing-obligation-vat-input-tax-evidence-001 | vat | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | missing-obligation-vat-mixed-use-002 | vat | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | missing-obligation-vat-credit-note-003 | vat | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | missing-obligation-packaging-threshold-004 | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | missing-obligation-packaging-deadline-005 | packaging_waste | missing_obligation | missing_obligation | PASS | yes | 1 |  | 13.0s |
| 3 | missing-obligation-packaging-evidence-006 | packaging_waste | missing_obligation | missing_obligation | PASS | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | missing-detail-vat-retail-invoice-exception-001 | vat | missing_detail | missing_obligation | FAIL | yes | 1 |  | 15.3s |
| 3 | missing-detail-vat-import-evidence-002 | vat | missing_detail | not_related | FAIL | yes | 1 | supported_coverage_gate:supported->not_related:supported_requested_change | 17.8s |
| 3 | missing-detail-vat-rate-change-correction-003 | vat | missing_detail | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | missing-detail-packaging-material-categories-004 | packaging_waste | missing_detail | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | missing-detail-packaging-household-scope-005 | packaging_waste | missing_detail | not_related | FAIL | yes | 1 |  | 18.3s |
| 3 | missing-detail-packaging-reusable-006 | packaging_waste | missing_detail | not_related | FAIL | yes | 1 |  | 19.3s |
| 3 | not-related-vat-supply-flexibility-lists-001 | vat | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | not-related-vat-private-use-list-use-case-002 | vat | not_related | not_related | PASS | yes | 1 |  | 14.6s |
| 3 | not-related-vat-rate-change-parameter-003 | vat | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | not-related-packaging-supplier-contract-004 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | not-related-packaging-age-restricted-005 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |
| 3 | not-related-packaging-scheduling-006 | packaging_waste | not_related | missing_obligation | FAIL | no | 0 | no_candidate_above_alignment_threshold | 0.0s |