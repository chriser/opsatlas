# Bulk Learning Pack Import

Use the bulk importer when onboarding a larger staged set of anonymised or generalised learning materials.

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

When the dry-run report looks clean, import the folder. Imported sources arrive pending: approve each one in the
panel, where approval runs through the audited action. The import has no option to approve (REF S1, 2 October 2026).

```bash
.venv/bin/python scripts/import_packs.py packs/incoming/learning-materials \
  --report data/import_reports/learning-materials-import.json
```

## Report checks

Review the Markdown report before operator acceptance:

- `imported`: files registered and ingested successfully.
- `duplicate`: content hash already exists in the source register.
- `failed`: file was registered or scanned but could not be ingested.
- `skipped`: unsupported file type.
- `process_records`: process records rebuilt after the import, from the sources already approved.

Failed rows include an error and, when registration succeeded, the source id to inspect in the app.
