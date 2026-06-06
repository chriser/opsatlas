import base64
import os
from pathlib import Path
from typing import Dict, List
from urllib.parse import quote

import requests


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    for line in env_path.read_text().splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


load_env()

ORG = os.getenv("ADO_ORG")
PROJECT = os.getenv("ADO_PROJECT_NAME")
PAT = os.getenv("ADO_PAT")


TITLE_TO_SPRINT = {
    "Deliver AI Knowledge and Analytics Assistant Proof of Concept": "Sprint 1 - Governance Foundation",
    "Establish delivery governance and project controls": "Sprint 1 - Governance Foundation",
    "Prepare anonymised and synthetic learning data": "Sprint 2 - Data Strategy and Source Preparation",
    "Build ingestion and knowledge indexing capability": "Sprint 4 - Knowledge Index and Retrieval",
    "Build grounded assistant and RAG response flow": "Sprint 5 - Assistant API and RAG Flow",
    "Add validation, observability and evaluation controls": "Sprint 8 - Evaluation and Hardening",
    "Add analytics and insight capability": "Sprint 7 - Analytics and Insight",
    "Prepare final evidence and DT603 delivery artefacts": "Sprint 9 - Final Evidence and Submission Pack",
}


def get_auth_header(content_type: str = "application/json") -> Dict[str, str]:
    token = base64.b64encode(f":{PAT}".encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": content_type,
        "Accept": "application/json",
    }


def run_wiql() -> List[int]:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/wiql?api-version=7.1"
    )

    query = {
        "query": f"""
        SELECT [System.Id], [System.WorkItemType], [System.Title]
        FROM WorkItems
        WHERE [System.TeamProject] = '{PROJECT}'
        AND [System.WorkItemType] IN ('Epic', 'Feature')
        ORDER BY [System.Id]
        """
    }

    response = requests.post(url, headers=get_auth_header(), json=query, timeout=30)

    print("WIQL status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    return [item["id"] for item in response.json().get("workItems", [])]


def get_work_items(ids: List[int]) -> List[Dict]:
    if not ids:
        return []

    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/workitems?ids={','.join(map(str, ids))}&api-version=7.1"
    )

    response = requests.get(url, headers=get_auth_header(), timeout=30)

    print("Get work items status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    return response.json().get("value", [])


def update_iteration_path(work_item_id: int, iteration_path: str) -> None:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/workitems/{work_item_id}?api-version=7.1"
    )

    payload = [
        {
            "op": "add",
            "path": "/fields/System.IterationPath",
            "value": iteration_path,
        }
    ]

    response = requests.patch(
        url,
        headers=get_auth_header("application/json-patch+json"),
        json=payload,
        timeout=30,
    )

    print(f"Update {work_item_id} → {iteration_path}")
    print("Status:", response.status_code)

    if response.status_code not in (200, 201):
        print(response.text)
        raise SystemExit(1)


def main() -> None:
    ids = run_wiql()
    items = get_work_items(ids)

    for item in items:
        title = item["fields"].get("System.Title")
        sprint = TITLE_TO_SPRINT.get(title)

        if not sprint:
            print(f"Skipping unmapped item: {item['id']} | {title}")
            continue

        update_iteration_path(item["id"], f"{PROJECT}\\{sprint}")

    print("Epic and Feature sprint assignment completed.")


if __name__ == "__main__":
    main()
