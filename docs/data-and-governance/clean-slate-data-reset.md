# Clean-Slate Data Reset

## Purpose

OpsAtlas has a gated local-data reset path for controlled evaluation and corpus replacement. The reset clears local runtime data after experimentation, preserves code and validation evidence, and creates a backup before any destructive change.

An operator should run the reset only when ready to begin a controlled corpus load. The tool does not run automatically.

## Tool

Script: `scripts/data_reset.py`

Safety gates:

- Every destructive command requires `--confirm-gated RESET_OPSATLAS_DATA`.
- Reset and restore create a timestamped backup first unless `--dry-run` is used.
- The script refuses unsafe data directories such as the repository root, parent folder, filesystem root or home directory.
- Backups are local runtime artefacts and should stay out of git.

## What Gets Wiped

A full reset clears the local `data/` runtime state:

- Uploaded source register and source file copies.
- Ingested sections.
- Ontology database and generated runtime state.
- Embeddings and review caches.
- Governance re-analysis and internal/external review job state.
- Compliance reasoning latest review, pair cache and resolution state.
- Public external source snapshots and source registry.
- Analytics, audit, usage, agent run and action logs.
- Simulator, regulatory review and process registry runtime outputs.

After reset, the script recreates the expected empty baseline JSON files and runtime folders.

## What Is Preserved

The reset does not touch:

- Application code.
- Git history.
- Configuration files.
- Documentation.
- External delivery records or Wiki pages.
- Benchmark evidence under `docs/benchmark/`.
- Product validation files under `docs/validation/`.
- Source packs outside `data/`.
- Exported reports outside `data/`, unless manually deleted.

## Commands

Run all commands from the repository root.

Dry-run a full reset:

```bash
.venv/bin/python scripts/data_reset.py --data-dir data --backup-root backups/data-reset reset --confirm-gated RESET_OPSATLAS_DATA --dry-run
```

Create a backup without changing data:

```bash
.venv/bin/python scripts/data_reset.py --data-dir data --backup-root backups/data-reset backup --label before-final-reset
```

Run the clean-slate reset:

```bash
.venv/bin/python scripts/data_reset.py --data-dir data --backup-root backups/data-reset reset --confirm-gated RESET_OPSATLAS_DATA --label fresh-corpus-start
```

Clear review and embedding caches while preserving loaded sources:

```bash
.venv/bin/python scripts/data_reset.py --data-dir data --backup-root backups/data-reset reset-caches --confirm-gated RESET_OPSATLAS_DATA
```

Restore a previous backup:

```bash
.venv/bin/python scripts/data_reset.py --data-dir data --backup-root backups/data-reset restore backups/data-reset/<backup-folder> --confirm-gated RESET_OPSATLAS_DATA
```

Plan staged final-corpus loading:

```bash
.venv/bin/python scripts/data_reset.py plan-tranches "/path/to/final-corpus" --batch-size 10 --output output/final-corpus-tranches.json --materialise-dir output/final-corpus-tranches
```

Load one materialised tranche:

```bash
.venv/bin/python scripts/import_packs.py output/final-corpus-tranches/tranche-01 --approve --report output/final-load-tranche-01.json
```

## Recommended corpus procedure

1. Stop the local dev server and confirm no governance or reasoning jobs are running.
2. Run the full-reset dry run and review the paths that would be cleared.
3. Run an explicit backup.
4. Run the clean-slate reset only when ready to start controlled testing.
5. Start the app and confirm the source, governance and analytics pages show an empty baseline.
6. Create tranche folders from the final source corpus.
7. Load tranche 1, then inspect Knowledge Sources, Governance and Enterprise Activity Model outputs.
8. Resolve obvious source-quality issues before loading the next tranche.
9. Repeat tranche loading until the intended corpus is complete.
10. Run the proportionate Governance review and acceptance checks defined for the corpus.

The staged-tranche approach gives the dataset a clean audit trail and avoids hiding ingestion or ontology-quality issues inside one large import.
