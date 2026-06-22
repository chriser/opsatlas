# Source Register Template

Ticket: #42

Use this template before uploading any source into the control panel. The running application stores its local source register under `data/source_register.json`, which is git-ignored. This template is the governed planning record that explains what a source is, why it is safe, and how it should be approved.

## Source record fields

| Field | Required | Example | Notes |
|---|---|---|---|
| `source_id` | Yes | `SRC_SUPPLIER_SETUP_PACK_001` | Stable human-readable planning ID. The app will also generate its own runtime UUID. |
| `title` | Yes | `Supplier setup learning pack` | Descriptive title shown to reviewers. |
| `filename` | Yes | `Anonymised_Learning_Pack_1_End_to_End_Supplier_Setup_Process.md` | Exact file or pack name. |
| `source_type` | Yes | `document` | Keep as `document` for Sprint 2 packs. |
| `sensitivity` | Yes | `anonymised` | Use `anonymised` or `synthetic`. |
| `source_basis` | Yes | `approved anonymised DT602 learning material` | Do not reference raw confidential source names. |
| `process_area` | Yes | `supplier-onboarding` | Main process taxonomy label. |
| `owner_role` | Yes | `process support lead` | Role, not a person. |
| `system_scope` | Yes | `operational master data tool; finance master data environment` | Generic capability labels only. |
| `validation_status` | Yes | `validated` | Use `validated` or `requires_validation`. |
| `approval_status` | Yes | `pending` | Mirrors the app gate: `pending`, `approved`, `rejected`. |
| `intended_use` | Yes | `retrieval, grounded Q&A, analytics event examples` | Explain the assistant purpose. |
| `restricted_use` | Yes | `no operational decisions; no confidential data reconstruction` | State what this source cannot be used for. |
| `reviewer` | Yes | `operator` | Role or agent, not a person. |
| `review_date` | Yes | `2026-06-22` | Date of safe-use review. |
| `notes` | No | `Open sequence question retained as requires_validation` | Any caveat that matters for UAT. |

## Markdown template

```markdown
## Source Register Entry

- source_id:
- title:
- filename:
- source_type: document
- sensitivity:
- source_basis:
- process_area:
- owner_role:
- system_scope:
- validation_status:
- approval_status: pending
- intended_use:
- restricted_use:
- reviewer:
- review_date:
- notes:
```

## JSON template

```json
{
  "source_id": "",
  "title": "",
  "filename": "",
  "source_type": "document",
  "sensitivity": "anonymised",
  "source_basis": "",
  "process_area": "",
  "owner_role": "",
  "system_scope": [],
  "validation_status": "requires_validation",
  "approval_status": "pending",
  "intended_use": [],
  "restricted_use": [],
  "reviewer": "operator",
  "review_date": "",
  "notes": ""
}
```

## Supplier setup starter entry

```json
{
  "source_id": "SRC_SUPPLIER_SETUP_PACK_001",
  "title": "Supplier setup learning pack",
  "filename": "Anonymised_Learning_Pack_1_End_to_End_Supplier_Setup_Process.md",
  "source_type": "document",
  "sensitivity": "anonymised",
  "source_basis": "approved anonymised DT602 learning material",
  "process_area": "supplier-onboarding",
  "owner_role": "process support lead",
  "system_scope": [
    "operational master data tool",
    "finance master data environment",
    "document repository"
  ],
  "validation_status": "validated",
  "approval_status": "pending",
  "intended_use": [
    "retrieval",
    "grounded Q&A",
    "governance checks",
    "analytics event examples"
  ],
  "restricted_use": [
    "operational decisioning",
    "real supplier onboarding",
    "confidential data reconstruction"
  ],
  "reviewer": "operator",
  "review_date": "2026-06-22",
  "notes": "Open process-design questions remain marked requires_validation inside the pack."
}
```

## Approval checklist

Before setting a source to `approved` in the control panel:

1. The source has a completed source-register entry.
2. The source has passed the anonymisation checklist.
3. The source has a clear process area and role owner.
4. Any uncertain fact is marked `requires_validation`.
5. The source can be ingested and sectioned cleanly.
6. The source is safe for retrieval, analytics and UAT evidence.
