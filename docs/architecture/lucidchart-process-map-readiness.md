# Lucidchart Process Map Integration

The platform can generate Lucidchart Standard Import files from approved Process Registry records, and can create
Lucidchart documents directly when Lucid API credentials are configured.

## Current export

Process maps are generated from approved Process Registry records. Each Lucid import includes:

- process identity and source title
- roles/owners
- systems
- controls
- dependencies
- open decisions flagged as requiring validation
- ordered BPMN task blocks from structured learning records or business rules
- connector lines between steps
- governance-context blocks with source metadata embedded as Lucid custom data and notes
- Mermaid text for quick inspection outside Lucid

## Local export command

```bash
.venv/bin/python scripts/export_process_maps.py --output-dir exports/process-maps
```

This writes one `.json`, one `.mmd` and one `.lucid` file per approved process record. The `.lucid` file is a ZIP with
`document.json` at the root, which follows Lucid Standard Import.

## API

- `GET /api/process/maps`
- `GET /api/process/maps/{process_id}`
- `GET /api/process/lucid/config`
- `GET /api/process/maps/{process_id}/lucid-import`
- `POST /api/process/maps/{process_id}/lucid`

All API endpoints require normal operator authentication.

## Environment

For live Lucid document creation:

- `LUCID_API_KEY` is required.
- `LUCID_PARENT_FOLDER_ID` is optional and places created diagrams in a specific Lucid folder.
- `LUCID_PRODUCT` is optional and defaults to `lucidchart`; `lucidspark` is also accepted by Lucid's API.

The download/import route works without credentials, so diagram quality can be tested before live API setup is complete.

## Next integration points

- Validate generated `.lucid` files against the premium Lucid account and tune layout/style based on real imports.
- Add Lucid document URLs to process records or analytics report exports once live creation is stable.
- Investigate embedding the generated Lucidchart next to the Avatar transcript for end-user process-map support.
- Consider a Lucid extension only if we need in-editor update/sync behaviour; the current Standard Import adapter is the
  right first step because it avoids re-parsing source documents.
