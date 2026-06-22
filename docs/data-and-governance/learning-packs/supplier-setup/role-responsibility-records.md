# Supplier Setup Role and Responsibility Records

Ticket: #45

## Metadata

| Field | Value |
|---|---|
| source_pack | `Anonymised_Learning_Pack_1_End_to_End_Supplier_Setup_Process.md` |
| process_area | `supplier-onboarding` |
| record_type | `role_responsibility` |
| sensitivity | `anonymised` |
| source_basis | `approved anonymised DT602 learning material` |
| validation_status | `validated_with_open_questions` |

## Role records

| record_id | role | responsibility | key_inputs | key_outputs | validation_status |
|---|---|---|---|---|---|
| `SUP_ROLE_001` | `commercial requester` | Identifies the need for a new supplier or a change to supplier details and initiates the formal request. | Business need, supplier details known to requester. | Submitted supplier setup request. | `validated` |
| `SUP_ROLE_002` | `buyer` | Provides commercial context and may complete or support the supplier request form. | Supplier requirement, category context. | Completed request information. | `validated` |
| `SUP_ROLE_003` | `support team` | Reviews the request, checks completeness, follows up on missing information and coordinates hand-offs. | Supplier setup form, supporting information. | Complete request pack or returned query. | `validated` |
| `SUP_ROLE_004` | `process support lead` | Oversees process progression, readiness controls and communication back to the requester. | Request status, control outcomes, setup readiness. | Controlled progression and completion confirmation. | `validated_with_open_questions` |
| `SUP_ROLE_005` | `master data operator` | Creates or amends the supplier record in the operational master data tool. | Approved request details, mandatory operational fields. | Operational supplier record. | `validated` |
| `SUP_ROLE_006` | `accounts payable role` | Performs or triggers due diligence and credit checks and supports finance-side setup. | Due diligence pack, supplier details. | Check result and finance setup input. | `validated_with_open_questions` |
| `SUP_ROLE_007` | `finance master data role` | Creates or maintains finance supplier identifiers and maps them to operational identifiers. | Operational supplier ID, finance setup request. | Finance supplier ID and cross-system mapping. | `validated` |
| `SUP_ROLE_008` | `operational system owner` | Ensures status and configuration controls prevent incomplete suppliers being used downstream. | Readiness status, system configuration. | Stop-gate behaviour and controlled activation. | `validated` |
| `SUP_ROLE_009` | `requesting business team` | Receives completion confirmation and uses the supplier once setup is complete. | Completion notice, active supplier record. | Downstream use of supplier. | `validated` |

## Responsibility boundaries

- The requester owns the business need and initial request quality.
- The support function owns intake control, follow-up and coordination.
- The due diligence and credit-check owner must be confirmed where the source material was ambiguous.
- The operational master data owner creates the operational supplier record but does not alone make the supplier ready.
- The finance master data role owns finance identifier creation and mapping.
- Final readiness requires both data creation and control completion.

## Open role questions

| question_id | question | why_it_matters | validation_status |
|---|---|---|---|
| `SUP_ROLE_Q001` | Who is accountable for each part of the due diligence pack? | Accountability must be clear before the process can be operationalised. | `requires_validation` |
| `SUP_ROLE_Q002` | Who owns final readiness sign-off if finance setup and operational setup complete at different times? | Split ownership could create premature activation risk. | `requires_validation` |
| `SUP_ROLE_Q003` | Who owns evidence retention for failed checks? | Auditability depends on a named role or function. | `requires_validation` |
