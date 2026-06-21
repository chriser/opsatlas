# Supplier setup and supplier master data maintenance — anonymised learning data pack

## Knowledge source card

- Knowledge record ID: PROC-SUP-SETUP-001
- Process area: Supplier setup and supplier master data maintenance
- Business domain: Retail backoffice / supplier master data
- Lifecycle phase: Planning and discovery
- Confidentiality: Anonymised learning data — no live supplier records, no personal data, no real system names
- Primary purpose: Help users understand the target supplier setup process, required approvals, system hand-offs and open design questions.
- Permitted use: Process clarification, onboarding, requirements drafting, test scenario preparation and gap analysis.
- Prohibited use: Do not infer real supplier details, approve onboarding, replace due diligence, expose source workshop material or make production system changes.

## Plain-English process narrative

Overview. Supplier setup is a controlled, multi-step process. It begins when a Business Requester decides to onboard a new supplier or amend an existing supplier record. The requester completes a supplier setup form and sends it to the process support team for review. The process support team checks whether the request is complete and asks the requester for corrections where information is missing or unclear.

Pre-setup controls. For new suppliers, due diligence and credit checks must be completed before the supplier can be enabled for operational use. These checks act as a gate. If either check fails, the supplier is not onboarded and the failure is communicated to the relevant requester. If the checks are approved, the process can move to supplier master data setup.

Operational setup. After approval, the Support Analyst creates or amends the supplier record in the Target Backoffice System. The system generates an operational supplier identifier, which is recorded against the supplier setup request. The request is then reviewed and submitted for supplier master data validation.

Finance mapping. The Finance Master Data Lead reviews the supplier master data changes and updates the finance interface or account mapping so that the operational supplier identifier is linked to the finance supplier identifier. This mapping is required because the operational system and finance system use different identifiers.

Validation and handover. Once the supplier record has been created or amended, and the operational-to-finance mapping is complete, the Process Support Lead validates the setup in the Target Backoffice System. The supplier setup or change is then treated as complete and can be handed over to downstream processes such as invoice reconciliation, ordering, receiving and payment processing.

## Structured process steps

1. Trigger supplier setup or change — Business Requester — supplier setup request initiated.
2. Complete supplier setup form — Business Requester — form completed (spreadsheet template).
3. Submit request to support team — Business Requester — request received by process support team.
4. Review supplier setup or change request — Process Support Lead / Support Analyst — accepted for checks or returned for correction.
5. Complete due diligence pack — Process Support Lead — due diligence pack submitted.
6. Request credit checks — Process Support Lead / Credit Control Role — credit check completed.
7. Decision: checks approved? — Process Support Lead — approved or rejected path selected.
8. If checks fail: reject onboarding — Finance / Process Support Lead — requester informed; supplier not onboarded.
9. If checks pass: request supplier master setup — Finance Master Data Lead / Support Analyst.
10. Create or amend supplier in Target Backoffice System — Support Analyst — operational supplier record created or amended.
11. Record operational supplier ID — Support Analyst.
12. Review and submit supplier master data request — Support Analyst / Supply Chain Analyst.
13. Review supplier master data changes — Finance Master Data Lead — finance mapping requirement confirmed.
14. Update account mapping — Finance Master Data Lead — operational ID mapped to finance supplier ID.
15. Inform relevant stakeholders — Finance Master Data Lead.
16. Validate supplier setup or change — Process Support Lead — setup validated in Target Backoffice System.
17. Handover to downstream process — Process Support Lead — supplier available for invoice reconciliation / ordering / receiving / payment.

## Roles and responsibilities

- Business Requester: Identifies the need for a new supplier or supplier detail change and provides the initial supplier setup information.
- Process Support Lead: Reviews the request, coordinates checks, ensures required information is complete, and validates the final setup.
- Support Analyst: Creates or amends the supplier in the Target Backoffice System and records the generated operational supplier ID.
- Finance Master Data Lead: Reviews supplier master data changes and maintains mapping between the operational supplier ID and finance supplier ID.
- Credit Control Role: Performs or supports credit checks before supplier onboarding can proceed.
- Supply Chain Analyst: Supports review of supplier master data where the supplier record affects supply chain or downstream operational processes.

## Business rules for assistant retrieval

- A supplier cannot be onboarded if mandatory due diligence or credit checks fail.
- Due diligence and credit checks are gating controls for new suppliers, not optional administrative tasks.
- Supplier setup is not complete when the operational supplier record is created; finance mapping and validation must also be completed.
- The operational supplier ID and finance supplier ID may be different, so mapping between them must be maintained.
- If the supplier record is created before all required setup elements are complete, downstream processes may fail or require manual correction.
- The future process should define whether operational setup and finance setup happen sequentially or in parallel.
- The future process should define the master system for each supplier data field to avoid duplicate manual maintenance.

## Open design decisions captured from the workshop

- Which system is the master for each supplier data field? — Avoids duplicate maintenance between operational and finance systems and reduces data inconsistency risk. Owner: business process owner with technology/data architecture support.
- Should supplier setup in the operational system happen before, after or in parallel with finance setup? — Sequencing affects when identifiers are available and when mapping can be completed. Owner: process owner and finance master data lead.
- Can supplier identifiers be generated automatically? — Manual identifier allocation creates duplication and control risk. Owner: system configuration lead.
- What is the required turnaround time for due diligence and credit checks? — Onboarding cannot progress until checks are complete. Owner: process owner and finance/control team.
- What evidence should be retained after setup? — The process needs a controlled audit trail. Owner: governance lead / records management owner.
- When should a supplier become active? — Activation should not happen before mandatory checks, mappings and required operational links are complete. Owner: process owner and system configuration lead.

## Example questions and approved answers

- Who starts the supplier setup process? The process starts when a Business Requester decides that a new supplier is needed or that an existing supplier record must be changed. The requester completes a supplier setup form and submits it to the process support team.
- Can a new supplier be created if due diligence has not passed? The supplier should not be enabled for operational use until due diligence and credit checks have been approved. If either check fails, onboarding is rejected and the requester is informed.
- Why is supplier ID mapping required? The Target Backoffice System and finance system can use different supplier identifiers. Mapping is required so that operational transactions can be linked to the correct finance supplier record for reconciliation, invoicing and payment.
- Is supplier setup complete once the supplier is created in the Target Backoffice System? No. Creation of the operational supplier record is only one part of the process. The setup also requires finance mapping, review and final validation before downstream processes can rely on it.
