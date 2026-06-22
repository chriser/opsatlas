# Bulk Learning Pack Import

Use the bulk importer when onboarding many anonymised learning materials, such as the 52-pack source set.

## Folder convention

Place source files under a local, git-ignored folder:

```bash
packs/incoming/learning-materials/
```

Supported file types match the normal UI upload path: `.md`, `.txt`, `.json`, `.pdf` and `.docx`.

## Dry run

Run a dry-run first. This scans the folder, detects duplicates already in the source register, and writes JSON plus Markdown reports without changing the knowledge base.

```bash
.venv/bin/python scripts/import_packs.py packs/incoming/learning-materials \
  --dry-run \
  --report data/import_reports/learning-materials-dry-run.json
```

## Import

When the dry-run report looks clean, import the folder. Use `--approve` only when the source set is ready to become queryable after ingestion.

```bash
.venv/bin/python scripts/import_packs.py packs/incoming/learning-materials \
  --approve \
  --report data/import_reports/learning-materials-import.json
```

## Report checks

Review the Markdown report before UAT:

- `imported`: files registered and ingested successfully.
- `duplicate`: content hash already exists in the source register.
- `failed`: file was registered or scanned but could not be ingested.
- `skipped`: unsupported file type.
- `process_records`: approved process records rebuilt after the import.

Failed rows include an error and, when registration succeeded, the source id to inspect in the app.
