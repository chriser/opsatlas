import base64
import os
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

import requests


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(".env file not found")

    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


load_env()

ORG = os.getenv("ADO_ORG")
PROJECT = os.getenv("ADO_PROJECT_NAME")
PAT = os.getenv("ADO_PAT")

MODULE_STATUS_PAGE = "/Delivery-Management/Module-Status"

WORK_ITEMS_TO_CLOSE = [
    "Create Azure DevOps project structure for DT602 planning evidence",
    "Create decision log and risk log documentation",
    "Create local repository and connect Azure Repo",
    "Commit initial README and documentation skeleton",
    "Create Epic and Feature hierarchy",
    "Create decision log template",
    "Create risk log template",
    "Publish documentation to repo and Wiki",
]

COMMENT_TARGET_TITLE = "Create Azure DevOps project structure for DT602 planning evidence"

PIPELINE_COMMENT = (
    "First placeholder Azure DevOps pipeline run completed successfully on 06 Jun 2026 "
    "against the main branch, commit 4ba44694. Evidence has been captured in the "
    "Final-Evidence / Evidence-Index Wiki page."
)

UPDATED_MODULE_STATUS_CONTENT = """# Module Status

This page tracks the maturity of each architecture module across the delivery slices.

## Purpose

The module status page prevents the project from becoming unclear as the build grows. It shows what exists, what is planned, what is blocked and what evidence is available.

## Status scale

| Status | Meaning |
|---|---|
| Not started | No implementation or evidence yet |
| Planned | Backlog item exists but no build evidence yet |
| In progress | Work has started |
| MVP | Basic working version exists |
| Hardened | Tested and improved version exists |
| Evidence captured | Screenshots, logs or tests are available |
| Deferred | Out of scope for current submission |

## Module status table

| Module | Related slice | Current status | Target outcome | Evidence location |
|---|---|---|---|---|
| Source and Data Governance | Slice 0 / Slice 1 | Planned | Source register, data rules, anonymised/synthetic data controls | Evidence Index |
| Ingestion and Preparation | Slice 1 | Planned | Source loading, section builder and metadata tagging | Evidence Index |
| Knowledge and Indexing | Slice 1 / Slice 2 | Planned | Basic retrieval index, then retrieval quality improvement | Evidence Index |
| Assistant API and UI | Slice 1 | Planned | User can ask a process question and receive structured answer | Evidence Index |
| RAG Orchestration | Slice 1 / Slice 2 | Planned | Evidence pack, constrained prompt and grounded answer | Evidence Index |
| Model Runtime | Slice 1 / Slice 2 | Planned | Provider abstraction and draft answer generation | Evidence Index |
| Validation and Safety | Slice 2 | Planned | Citation support checks, confidence and refusal handling | Evidence Index |
| Observability and Audit | Slice 2 / Slice 5 | Planned | Trace logs, model/prompt version and validation outcomes | Evidence Index |
| Analytics and Insight | Slice 3 | Planned | Usage logs and knowledge-gap analysis | Evidence Index |
| Voice Services | Slice 4 | Planned | Speech-to-text and text-to-speech around canonical answer | Evidence Index |
| Build and Evaluation | Slice 0 / Slice 5 | Planned | Test cases, golden questions, regression checks | Evidence Index |
| Delivery Governance | Slice 0 | Evidence captured | Azure DevOps backlog, Wiki, repo, Delivery Plan and first pipeline run are available | Evidence Index |

## Slice 0 evidence note

The initial Azure DevOps governance baseline has been created. This includes the project, repository, Wiki, architecture pages, Evidence Index, Decision Log, Risk Log, AI-Assisted Development Log, Module Status page, Test Cases, Delivery Plan, dependency chain and first successful placeholder pipeline run.

## Review notes

Update this page after each sprint review. The status should reflect actual evidence, not optimistic intent.
"""


def auth_header(content_type: str = "application/json", extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    if not PAT:
        raise ValueError("ADO_PAT is missing. Check your .env file.")

    token = base64.b64encode(f":{PAT}".encode("utf-8")).decode("utf-8")

    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": content_type,
        "Accept": "application/json",
    }

    if extra:
        headers.update(extra)

    return headers


def wiql(query: str) -> List[int]:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/wiql?api-version=7.1"
    )

    response = requests.post(
        url,
        headers=auth_header(),
        json={"query": query},
        timeout=30,
    )

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    return [item["id"] for item in response.json().get("workItems", [])]


def get_work_items(ids: List[int]) -> List[Dict]:
    if not ids:
        return []

    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/workitems?ids={','.join(map(str, ids))}&$expand=relations&api-version=7.1"
    )

    response = requests.get(url, headers=auth_header(), timeout=30)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    return response.json().get("value", [])


def get_by_title(title: str) -> Optional[Dict]:
    safe_title = title.replace("'", "''")

    ids = wiql(
        f"""
        SELECT [System.Id]
        FROM WorkItems
        WHERE [System.TeamProject] = '{PROJECT}'
        AND [System.Title] = '{safe_title}'
        ORDER BY [System.Id]
        """
    )

    if not ids:
        return None

    return get_work_items([ids[0]])[0]


def patch_work_item(work_item_id: int, payload: List[Dict]) -> None:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/workitems/{work_item_id}?api-version=7.1"
    )

    response = requests.patch(
        url,
        headers=auth_header("application/json-patch+json"),
        json=payload,
        timeout=30,
    )

    print(f"Patch work item {work_item_id}: {response.status_code}")

    if response.status_code not in (200, 201):
        print(response.text)
        raise SystemExit(1)


def close_work_item(item: Dict) -> None:
    item_id = item["id"]
    fields = item.get("fields", {})
    title = fields.get("System.Title")
    state = fields.get("System.State")

    if state == "Closed":
        print(f"Already closed: {item_id} | {title}")
        return

    payload = [
        {
            "op": "add",
            "path": "/fields/System.State",
            "value": "Closed",
        }
    ]

    print(f"Closing: {item_id} | {title}")
    patch_work_item(item_id, payload)


def add_comment(work_item_id: int, comment_text: str) -> None:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/workItems/{work_item_id}/comments?api-version=7.1-preview.4"
    )

    response = requests.post(
        url,
        headers=auth_header(),
        json={"text": comment_text},
        timeout=30,
    )

    print(f"Add comment to work item {work_item_id}: {response.status_code}")

    if response.status_code not in (200, 201):
        print(response.text)
        raise SystemExit(1)


def get_wiki_id() -> str:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wiki/wikis?api-version=7.1"
    )

    response = requests.get(url, headers=auth_header(), timeout=30)

    print("List wikis status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    wikis = response.json().get("value", [])

    if not wikis:
        raise RuntimeError("No Wiki found.")

    wiki = wikis[0]
    print("Using Wiki:", wiki.get("name"))
    return wiki["id"]


def get_existing_etag(wiki_id: str, path: str) -> Optional[str]:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wiki/wikis/{wiki_id}/pages"
        f"?path={quote(path, safe='/')}&includeContent=true&api-version=7.1"
    )

    response = requests.get(url, headers=auth_header(), timeout=30)

    if response.status_code == 404:
        return None

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    return response.headers.get("ETag")


def put_wiki_page(wiki_id: str, path: str, content: str) -> None:
    etag = get_existing_etag(wiki_id, path)

    extra_headers = {}
    if etag:
        extra_headers["If-Match"] = etag

    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wiki/wikis/{wiki_id}/pages"
        f"?path={quote(path, safe='/')}&api-version=7.1"
    )

    response = requests.put(
        url,
        headers=auth_header(extra=extra_headers),
        json={"content": content},
        timeout=30,
    )

    print(f"Create/update Wiki page: {path}")
    print("Status:", response.status_code)

    if response.status_code not in (200, 201):
        print(response.text)
        raise SystemExit(1)


def main() -> None:
    if not ORG or not PROJECT:
        raise ValueError("ADO_ORG or ADO_PROJECT_NAME missing. Check .env file.")

    print("Step 1: Update Module Status Wiki page")
    wiki_id = get_wiki_id()
    put_wiki_page(wiki_id, MODULE_STATUS_PAGE, UPDATED_MODULE_STATUS_CONTENT)

    print()
    print("Step 2: Close completed Slice 0 governance work items")

    for title in WORK_ITEMS_TO_CLOSE:
        item = get_by_title(title)

        if not item:
            print(f"Not found, skipping: {title}")
            continue

        close_work_item(item)

    print()
    print("Step 3: Add pipeline evidence comment")

    target = get_by_title(COMMENT_TARGET_TITLE)

    if not target:
        raise RuntimeError(f"Could not find comment target: {COMMENT_TARGET_TITLE}")

    add_comment(target["id"], PIPELINE_COMMENT)

    print()
    print("Slice 0 governance evidence finalisation completed.")
    print()
    print("Recommended checks:")
    print("- Azure DevOps > Wiki > Delivery-Management > Module-Status")
    print("- Azure DevOps > Boards > Work Items")
    print("- Open 'Create Azure DevOps project structure for DT602 planning evidence' and check comments")


if __name__ == "__main__":
    main()
