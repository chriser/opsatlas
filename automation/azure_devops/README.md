# Azure DevOps utilities

This directory contains the small reusable, read-only utilities retained from
the OpsAtlas delivery automation. Historical project-bootstrap, sprint-rewrite,
and one-off backlog scripts are preserved in Git history rather than the final
assessor-facing tree.

## Configuration

The scripts read the following values from an uncommitted repository-root
`.env` file:

```text
ADO_ORG
ADO_PROJECT_NAME
ADO_PAT
ADO_TEAM_NAME       # optional; defaults to "<project> Team"
```

Never commit the `.env` file or print its values into reports.

## Retained commands

| Script | Purpose |
|---|---|
| `check_connection.py` | Verify authenticated Azure DevOps API access. |
| `check_repos.py` | List repositories available to the configured project. |
| `list_work_items.py` | List project work items for inspection. |
| `list_project_iterations.py` | Inspect project iteration definitions. |
| `list_team_iterations.py` | Inspect iterations assigned to a team. |
| `export_wiki.py` | Export a local Markdown snapshot to the git-ignored working path `exports/wiki/`. |

These utilities do not define the current backlog, sprint plan, or product
architecture. Azure DevOps remains the authoritative delivery record.
