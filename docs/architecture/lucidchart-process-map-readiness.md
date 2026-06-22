# Lucidchart Process Map Readiness

The platform can now export process-map drafts before Lucidchart credentials are available.

## Current export

Process maps are generated from approved Process Registry records. Each draft includes:

- process identity and source title
- roles/owners
- systems
- controls
- dependencies
- open decisions flagged as requiring validation
- ordered steps from structured learning records or business rules
- edges between steps
- Mermaid text for quick inspection

## Local export command

```bash
.venv/bin/python scripts/export_process_maps.py --output-dir exports/process-maps
```

This writes one `.json` and one `.mmd` file per approved process record.

## API

- `GET /api/process/maps`
- `GET /api/process/maps/{process_id}`

Both endpoints require normal operator authentication.

## Lucidchart subscription point

Premium/API access is needed only when we move from local draft export to creating or updating diagrams inside Lucidchart. The future adapter should consume the JSON export rather than re-parsing source documents.
