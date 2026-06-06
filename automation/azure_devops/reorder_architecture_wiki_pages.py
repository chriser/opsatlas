import base64
import os
from pathlib import Path
from typing import Dict, List
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

ARCHITECTURE_PAGES: List[str] = [
    "/Architecture",
    "/Architecture/01-Executive-Summary",
    "/Architecture/02-Design-Principles",
    "/Architecture/03-High-Level-Diagram",
    "/Architecture/04-Diagram-Element-Glossary",
    "/Architecture/05-RAG-Framework",
    "/Architecture/06-Functional-Flow",
    "/Architecture/07-Core-Modules",
    "/Architecture/08-Iterative-Delivery-Slices",
    "/Architecture/09-Model-and-Voice-Decisions",
    "/Architecture/10-Technology-Approach",
    "/Architecture/11-Analytics-and-Insight",
    "/Architecture/12-Observability-Audit-Evaluation",
    "/Architecture/13-AI-Assisted-Development",
    "/Architecture/14-Modular-Build-Methodology",
    "/Architecture/15-Ethics-Security-Data-Controls",
    "/Architecture/16-Immediate-Build-Implications",
    "/Architecture/17-Conclusion",
]


def auth_header(content_type: str = "application/json") -> Dict[str, str]:
    if not PAT:
        raise ValueError("ADO_PAT is missing. Check your .env file.")

    token = base64.b64encode(f":{PAT}".encode("utf-8")).decode("utf-8")

    return {
        "Authorization": f"Basic {token}",
        "Content-Type": content_type,
        "Accept": "application/json",
    }


def get_or_create_wiki_id() -> str:
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
        raise RuntimeError("No Wiki found in this project.")

    wiki = wikis[0]
    print("Using Wiki:", wiki.get("name"), "|", wiki.get("id"))
    return wiki["id"]


def move_page_order(wiki_id: str, page_path: str, new_order: int) -> None:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wiki/wikis/{wiki_id}/pagemoves?api-version=7.1-preview.1"
    )

    payload = {
        "path": page_path,
        "newPath": page_path,
        "newOrder": new_order,
    }

    response = requests.post(
        url,
        headers=auth_header(),
        json=payload,
        timeout=30,
    )

    print(f"Set order {new_order}: {page_path}")
    print("Status:", response.status_code)

    if response.status_code not in (200, 201, 202):
        print(response.text)
        raise SystemExit(1)


def main() -> None:
    if not ORG or not PROJECT:
        raise ValueError("ADO_ORG or ADO_PROJECT_NAME missing. Check .env file.")

    wiki_id = get_or_create_wiki_id()

    # Start at 0 so Architecture remains first, then 01..17.
    for order, page_path in enumerate(ARCHITECTURE_PAGES):
        move_page_order(wiki_id, page_path, order)

    print()
    print("Architecture Wiki page order update completed.")
    print("Refresh Azure DevOps → Wiki → Architecture.")


if __name__ == "__main__":
    main()
