# Supplier Setup Process Step Records

Ticket: #46

## Metadata

| Field | Value |
|---|---|
| source_pack | `Anonymised_Learning_Pack_1_End_to_End_Supplier_Setup_Process.md` |
| process_area | `supplier-onboarding` |
| record_type | `process_step` |
| sensitivity | `anonymised` |
| source_basis | `approved anonymised DT602 learning material` |
| validation_status | `validated_with_open_questions` |

## Step records

| record_id | sequence | activity | primary_role | input | output | control_or_gate | validation_status |
|---|---:|---|---|---|---|---|---|
| `SUP_STEP_001` | 1 | Trigger supplier setup or change | `commercial requester` | Business need for a new or changed supplier. | Formal setup need identified. | Request must be business-led. | `validated` |
| `SUP_STEP_002` | 2 | Prepare supplier request form | `commercial requester` | Supplier details available to requester. | Supplier setup form submitted to support. | Request must use a formal route. | `validated` |
| `SUP_STEP_003` | 3 | Review request for completeness | `support team` | Submitted setup form. | Complete request pack or returned query. | Completeness check before onward processing. | `validated` |
| `SUP_STEP_004` | 4 | Prepare due diligence pack | `support team` | Complete request and supporting information. | Due diligence pack available for checking. | Ownership of some fields needs confirmation. | `requires_validation` |
| `SUP_STEP_005` | 5 | Initiate due diligence and credit checks | `accounts payable role` | Due diligence pack and supplier details. | Risk and credit check result. | Mandatory gate before setup progression. | `validated` |
| `SUP_STEP_006` | 6 | Communicate failed checks where relevant | `support team` | Failed check outcome. | Requester informed; request paused or rejected. | Failed controls stop progression. | `validated` |
| `SUP_STEP_007` | 7 | Create supplier in operational master data tool | `master data operator` | Approved request and mandatory operational fields. | Operational supplier header record. | Header alone does not make supplier ready. | `validated` |
| `SUP_STEP_008` | 8 | Create supplier in finance master data environment | `finance master data role` | Finance setup request and supplier details. | Finance supplier identifier. | Sequence relative to operational setup needs confirmation. | `requires_validation` |
| `SUP_STEP_009` | 9 | Map supplier identifiers | `finance master data role` | Operational supplier ID and finance supplier ID. | Cross-system supplier mapping. | Mapping is required for payment and reconciliation. | `validated` |
| `SUP_STEP_010` | 10 | Complete contract links and readiness controls | `master data operator` | Supplier header, control outcomes, contract references. | Supplier readiness controls complete. | Mandatory contracts/readiness steps before activation. | `validated` |
| `SUP_STEP_011` | 11 | Activate supplier for use | `operational system owner` | Completed setup and readiness controls. | Supplier released for downstream use. | Status must prevent premature use. | `validated` |
| `SUP_STEP_012` | 12 | Confirm completion to requester | `support team` | Active supplier and completed readiness checks. | Requester receives completion confirmation. | Completion message closes the operational loop. | `validated_with_open_questions` |

## Exceptions and alternate outcomes

| record_id | trigger | expected_handling | validation_status |
|---|---|---|---|
| `SUP_EXC_001` | Request form missing required information. | Return query to requester and pause onward processing until corrected. | `validated` |
| `SUP_EXC_002` | Due diligence or credit checks fail. | Stop supplier setup and inform requester that setup cannot proceed. | `validated` |
| `SUP_EXC_003` | Finance-side supplier identifier is not available. | Do not treat supplier as payment-ready; maintain open mapping action. | `validated` |
| `SUP_EXC_004` | Contract links or readiness controls are incomplete. | Keep supplier non-operational or blocked from downstream use. | `validated` |

## Step-level business rules

- The process must start with a formal request.
- A support function must check the request before due diligence and setup activity.
- Due diligence and credit checks must pass before progression.
- Operational setup and finance setup are both required for readiness.
- Identifier mapping is mandatory before payment-related processes rely on the supplier.
- Activation should occur only after data, controls and contracts are complete.
