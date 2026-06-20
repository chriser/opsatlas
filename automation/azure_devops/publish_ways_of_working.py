"""Publish the Ways-of-Working governance pages to the project Wiki.

Reads staged Markdown from docs/ways-of-working/ and creates the pages under
/Ways-of-Working in the Azure DevOps project Wiki. Additive only: refuses to
overwrite a page that already exists (prints a warning and skips it).
"""

import base64
import os
from pathlib import Path
from urllib.parse import quote

import requests


def load_env(path: str = ".env") -> None:
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


load_env()
ORG = os.environ["ADO_ORG"].strip()
PAT = os.environ["ADO_PAT"].strip()
# Canonical project name (the projects API name, not the display name in .env).
PROJECT = "ai-knowledge-and-analytics-assistant"

STAGE_DIR = Path("docs/ways-of-working")

# (wiki path, staged file). Parent first so children attach cleanly.
PAGES = [
    ("/Ways-of-Working", "Ways-of-Working.md"),
    ("/Ways-of-Working/Agent-Collaboration", "Agent-Collaboration.md"),
    ("/Ways-of-Working/Agent-Handover-Log", "Agent-Handover-Log.md"),
    ("/Ways-of-Working/Definition-of-Done", "Definition-of-Done.md"),
    ("/Ways-of-Working/Effort-Sizing", "Effort-Sizing.md"),
    ("/Ways-of-Working/Build-Governance", "Build-Governance.md"),
]


def headers() -> dict:
    token = base64.b64encode(f":{PAT}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Accept": "application/json"}


def wiki_id() -> str:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wiki/wikis?api-version=7.1"
    )
    r = requests.get(url, headers=headers(), timeout=30)
    r.raise_for_status()
    return r.json()["value"][0]["id"]


def page_url(wid: str, path: str) -> str:
    return (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wiki/wikis/{wid}/pages?path={quote(path, safe='')}&api-version=7.1"
    )


def exists(wid: str, path: str) -> bool:
    r = requests.get(page_url(wid, path), headers=headers(), timeout=30)
    return r.status_code == 200


def put_page(wid: str, path: str, content: str) -> None:
    r = requests.put(
        page_url(wid, path),
        headers={**headers(), "Content-Type": "application/json"},
        json={"content": content},
        timeout=30,
    )
    print(f"  PUT {path} -> {r.status_code}")
    if r.status_code not in (200, 201):
        print("  !", r.text[:400])


def main() -> None:
    wid = wiki_id()
    print("Wiki id:", wid)
    for path, fname in PAGES:
        if exists(wid, path):
            print(f"  SKIP {path} (already exists — not overwriting)")
            continue
        content = (STAGE_DIR / fname).read_text()
        put_page(wid, path, content)


if __name__ == "__main__":
    main()
