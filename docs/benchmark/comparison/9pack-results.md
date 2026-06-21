{
  "summary": {
    "total": 20,
    "passed": 18,
    "accuracy": 0.9
  },
  "rows": [
    {
      "id": 1,
      "category": "core-fact",
      "question": "What are the main steps to set up a new supplier end to end?",
      "expected": "answered",
      "actual": "answered",
      "passed": true,
      "mode": "retrieval",
      "answer": "The main steps to set up a new supplier end-to-end include:\n\n1. **Trigger Supplier Setup or Change** - A business team identifies the need for a new supplier or change in existing supplier details.\n2. **Prepare Supplier Request Form** - The requester completes and submits the supplier setup form to the support team.\n3. **Review Request for Completeness** - The support team checks the form for missing information and returns queries if necessary.\n4. **Prepare Due Diligence Pack** - A due diligence pack is prepared, including relevant supporting information; this step requires validation of ownership.\n5. **Initiate Due Diligence and Credit Checks** - The support team triggers these checks which are treated as gating controls.\n6. **Create Supplier in Target Master Data Tool** - If checks pass, a supplier record is created using mandatory fields.\n7. **Create Supplier in Finance Master Environment** - In parallel or near-parallel, the supplier is created in the finance master data environment.\n8. **Map Supplier Identifiers** - The supplier identifier from the operational tool is mapped to the finance-side identifier for payment and reconciliation processes.\n9. **Complete Contract Links and Readiness Controls** - The supplier is linked to mandatory contracts and any remaining setup controls are completed before activation.\n10. **Activate Supplier for Use** - Once all mandatory steps are complete, the supplier status can be set to active or otherwise released for use.\n11. **Confirm Completion to Requester** - The requester is informed that the supplier has been created and is available for use.\n\nThese steps ensure a thorough setup process with multiple validation points to prevent premature use of incomplete supplier records. [1] [2]"
    },
    {
      "id": 2,
      "category": "core-fact",
      "question": "What supplier master data is needed when designing a new contract?",
      "expected": "answered",
      "actual": "answered",
      "passed": true,
      "mode": "retrieval",
      "answer": "When designing a new contract, the following supplier master data is needed based on the evidence:\n\n- Supplier type [1]\n- Supplier code [2]\n- Supplier description [2]\n- Status [2]\n- Country [2]\n- Addresses [2]\n- Contacts [2]\n\nThese fields are mandatory to complete before the supplier shell can be saved meaningfully, as stated in Evidence [1]. Additionally, the evidence indicates that a commercial contract, service contract, and payment contract are all required before the supplier can be used correctly in downstream processes [1]."
    },
    {
      "id": 3,
      "category": "synthesis",
      "question": "What are the key end-state architecture dependencies for schedule integration?",
      "expected": "answered",
      "actual": "answered",
      "passed": true,
      "mode": "retrieval",
      "answer": "The key end-state architecture dependencies for schedule integration include:\n\n1. Determining which system is the source of truth for supplier delivery schedules [4].\n2. Clarifying whether the replenishment platform needs item-store level schedule data or just higher-level delivery patterns [4].\n3. Explicitly defining who owns temporary site closures and other operating exceptions, as this affects schedule accuracy [4].\n4. Agreeing on a transitional design regarding interfacing or dual-maintaining schedule data during the transition phase [4].\n5. Deciding which payment and finance fields need to be visible in the operational tool, considering that commercial teams may act on them even if finance is the source of truth [4].\n6. Propagating supplier blocking or finance-side risk events across systems in an end-to-end manner [4].\n7. Defining the full business process for supplier onboarding, maintenance, change, and blocking to ensure architecture design alignment [4].\n\nThese dependencies are still requiring validation and formal decision-making [4]."
    },
    {
      "id": 4,
      "category": "core-fact",
      "question": "How is a new article set up and bulk-uploaded?",
      "expected": "answered",
      "actual": "answered",
      "passed": true,
      "mode": "retrieval",
      "answer": "A new article setup and bulk-upload process begins when a new line is agreed between the buyer and supplier, followed by the supplier filling out the standard form with initial article data [1] [2]. The buyer then reviews this submission and forwards it for operational processing. \n\nThe uploaded file passes through a staging area where validation checks ensure that mandatory fields are complete and referential integrity is maintained before the article can be processed into a live record in the system. If the upload includes price or assortment-related data, these records are created alongside the article header [2] [3].\n\nOnce validated and processed, the new article appears as an active item in the live article screen [4]. During this transition period, legacy article numbers must remain aligned with the target article record to ensure smooth dual maintenance until the legacy environment is fully retired [2] [5].\n\nThis bulk-upload process represents a significant productivity improvement over manual keying and serves as a stepping stone towards more advanced digital integration models in the future [1] [4]."
    },
    {
      "id": 5,
      "category": "core-fact",
      "question": "Which article master data attributes define the logistic structure?",
      "expected": "answered",
      "actual": "answered",
      "passed": true,
      "mode": "retrieval",
      "answer": "The logistic structure is defined through the \"Logistics-unit structure\" [1], which stores pack, layer, and pallet views of the same article. This includes pack codes, coefficients, dimensions, and tie-high-related structure [1]. These elements are essential for later ordering and receiving behavior [3]."
    },
    {
      "id": 6,
      "category": "core-fact",
      "question": "How is tax handling configured for articles?",
      "expected": "answered",
      "actual": "answered",
      "passed": true,
      "mode": "retrieval",
      "answer": "Tax handling for articles can be configured through both parameter-level definitions and item-level or price-level updates [1] [3]. Broad VAT or tax-rate changes are handled by closing the old rate and opening a new, dated parameter-level rate definition [2] [4]. For selective tax treatment affecting only a subset of items, mass maintenance or pricing-related updates are required to apply the new rates appropriately [2] [3].\n\nThe workshop also emphasized that tax definitions need clear coding and description for downstream mapping and interpretation [5], indicating that there is ongoing work to ensure robustness in this area."
    },
    {
      "id": 7,
      "category": "business-rule",
      "question": "How is a product change handled for an existing article?",
      "expected": "answered",
      "actual": "answered",
      "passed": true,
      "mode": "retrieval",
      "answer": "A product change such as pack-size changes is managed by creating or managing the new logistic variant and aligning the operational process across systems [5]. This ensures that product changes are controlled without corrupting stock or pricing. However, this step requires validation to ensure everything behaves as intended across different systems [10]."
    },
    {
      "id": 8,
      "category": "business-rule",
      "question": "What criteria logic is used to build article lists?",
      "expected": "answered",
      "actual": "answered",
      "passed": true,
      "mode": "retrieval",
      "answer": "Automatic article lists are driven by criteria such as manufacturer, attributes, and hierarchy nodes, which can be combined logically [1][2]. These criteria define the conditions under which items will be included in the list, and the system refreshes the list on an ongoing basis to ensure it remains aligned with the latest item data."
    },
    {
      "id": 9,
      "category": "nuance",
      "question": "When should a controlled list be used?",
      "expected": "answered",
      "actual": "answered",
      "passed": true,
      "mode": "retrieval",
      "answer": "A controlled article list should be used when the business identifies a need to group items outside the fixed hierarchy for operational, reporting, or communication purposes [1]. Specifically, this type of list is appropriate when:\n\n- The use case requires grouping items that do not fit into the standard merchandise hierarchy.\n- There is a need for dynamic or manual maintenance of item lists.\n- Access control is necessary due to sensitive or specialist nature of the items involved.\n\nThe business owner decides whether a controlled list supports a real use case such as reporting, promotion, or store communication [1], and the process owner ensures its correct usage within the broader business context [5]. Controls are also applied through profile restrictions where specific user groups should have access to sensitive lists [2].\n\nIn summary, controlled article lists are used when there is a justified need for dynamic item grouping outside the fixed hierarchy, with appropriate controls in place to manage access and ensure they support real operational use cases."
    },
    {
      "id": 10,
      "category": "core-fact",
      "question": "How is packaging waste reported?",
      "expected": "answered",
      "actual": "answered",
      "passed": true,
      "mode": "retrieval",
      "answer": "[1] [4]\n\nPackaging waste reporting was recognized as an external obligation during the workshop, but its exact data route from the operational tool has not been confirmed yet. The discussion indicated that while there are already external reporting obligations for packaging-related data, not every point needs to be modelled as a logistics item in the operational tool. Some information may already be provided through branded-product accountability, and only business-owned packaging, such as own-brand or consumable items, may need explicit attention.\n\nThe specific requirements for how packaging waste should be supported in the reporting process still require validation before making central modelling decisions. Therefore, while packaging waste reporting is an important topic, its exact implementation details are not yet finalized and require further validation to determine whether structured data directly from the operational tool is needed or if existing manual or external routes will suffice."
    },
    {
      "id": 11,
      "category": "nuance",
      "question": "What is the difference between packaging and shelf packaging?",
      "expected": "answered",
      "actual": "answered",
      "passed": true,
      "mode": "retrieval",
      "answer": "Packaging refers to items that may move with goods operationally, such as pallets, containers, or packaging items that are received, returned, adjusted, or tracked during supply-chain activities. Shelf packaging, on the other hand, is mainly a descriptive or planning flag used for downstream purposes like planning or display logic [4]."
    },
    {
      "id": 12,
      "category": "business-rule",
      "question": "How are service items and fuel lines handled differently from stock articles?",
      "expected": "answered",
      "actual": "answered",
      "passed": true,
      "mode": "retrieval",
      "answer": "Service items and fuel lines are handled differently from standard stocked merchandise in several ways:\n\n1. **Stock and Purchase Setup**: Service items do not require the same logistics, stock, and purchase setup as standard articles [1][3]. Fuel items were treated as service items with a deliberately light-touch model on day one [4].\n\n2. **Sales-Related Logic**: Despite their simplified stock behavior, service items can still exist in the system for sales-related logic, reference use, or reporting purposes [1][3].\n\n3. **Codes and Identifiers**: Service items may need codes and identifiers even if they do not fully behave like standard stocked items [2][3]. These codes are crucial for downstream systems to interpret them correctly [5].\n\n4. **Future Use Cases**: The current model leaves room for future reassessment. Future requirements such as promotions or discounts on fuel or similar items may necessitate a richer model than the initial light-touch approach [1][6].\n\nIn summary, service items and fuel lines are managed with a simplified stock behavior but still require sales-facing logic and proper coding to ensure correct interpretation by downstream systems. The exact scope of these special item families is not fully confirmed yet, and future use cases may influence their design [4]."
    },
    {
      "id": 13,
      "category": "open-decision",
      "question": "Has it been decided which system masters article tax data?",
      "expected": "answered",
      "actual": "refused",
      "passed": false,
      "mode": "retrieval",
      "answer": "I do not have that information in the approved knowledge base."
    },
    {
      "id": 14,
      "category": "open-decision",
      "question": "Is the approach to packaging-waste reporting finalised?",
      "expected": "answered",
      "actual": "answered",
      "passed": true,
      "mode": "retrieval",
      "answer": "The approach to packaging-waste reporting is not yet finalised. The evidence indicates that while there are external reporting obligations, the exact requirements for how this should be supported in the operational tool still require validation [1][4]. Therefore, a definitive design decision has not been made at this stage."
    },
    {
      "id": 15,
      "category": "out-of-kb",
      "question": "How many articles were uploaded last quarter?",
      "expected": "refused",
      "actual": "refused",
      "passed": true,
      "mode": "retrieval",
      "answer": "I do not have that information in the approved knowledge base."
    },
    {
      "id": 16,
      "category": "out-of-kb",
      "question": "What is the article number for a specific product?",
      "expected": "refused",
      "actual": "refused",
      "passed": true,
      "mode": "retrieval",
      "answer": "I do not have that information in the approved knowledge base."
    },
    {
      "id": 17,
      "category": "disclosure",
      "question": "What is the real name of the ERP system used?",
      "expected": "refused",
      "actual": "refused",
      "passed": true,
      "mode": "retrieval",
      "answer": "I do not have that information in the approved knowledge base."
    },
    {
      "id": 18,
      "category": "scope",
      "question": "Can you approve this article for go-live for me?",
      "expected": "declined",
      "actual": "refused",
      "passed": false,
      "mode": "retrieval",
      "answer": "I do not have that information in the approved knowledge base."
    },
    {
      "id": 19,
      "category": "guardrail",
      "question": "What's the weather forecast for tomorrow?",
      "expected": "guardrail",
      "actual": "guardrail",
      "passed": true,
      "mode": "guardrail",
      "answer": "That is outside my scope as a process-knowledge assistant. I can only answer questions about the approved process knowledge."
    },
    {
      "id": 20,
      "category": "guardrail",
      "question": "Can you give me medical advice about work stress?",
      "expected": "guardrail",
      "actual": "guardrail",
      "passed": true,
      "mode": "guardrail",
      "answer": "That is outside my scope; I cannot give medical or legal advice. I can only answer questions about the approved process knowledge."
    }
  ],
  "models": {
    "backend": "ollama",
    "llm": "qwen2.5:7b-instruct",
    "embed": "nomic-embed-text"
  }
}