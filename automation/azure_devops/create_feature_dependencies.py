import base64
import os
from pathlib import Path
from typing import Dict, List, Tuple
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


DEPENDENCIES: List[Tuple[str, str]] = [
    (
        "Establish delivery governance and project controls",
        "Prepare anonymised and synthetic learning data",
    ),
    (
        "Prepare anonymised and synthetic learning data",
        "Build ingestion and knowledge indexing capability",
    ),
    (
        "Build ingestion and knowledge indexing capability",
        "Build grounded assistant and RAG response flow",
    ),
    (
        "Build grounded assistant and RAG response flow",
        "Add validation, observability and evaluation controls",
    ),
    (
        "Add validation, observability and evaluation controls",
        "Add analytics and insight capability",
    ),
    (
        "Add analytics and insight capability",
        "Prepare final evidence and DT603 delivery artefacts",
    ),
]


def get_auth_header(content_type: str = "application/json") -> Dict[str, str]:
    token = base64.b64encode(f":{PAT}".encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": content_type,
        "Accept": "application/json",
    }


def get_features() -> Dict[str, int]:
    wiql_url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/wiql?api-version=7.1"
    )

    query = {
        "query": f"""
        SELECT [System.Id], [System.Title]
        FROM WorkItems
        WHERE [System.TeamProject] = '{PROJECT}'
        AND [System.WorkItemType] = 'Feature'
        ORDER BY [System.Id]
        """
    }

    response = requests.post(wiql_url, headers=get_auth_header(), json=query, timeout=30)

    print("WIQL status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    ids = [str(item["id"]) for item in response.json().get("workItems", [])]

    details_url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/workitems?ids={','.join(ids)}&api-version=7.1"
    )

    details = requests.get(details_url, headers=get_auth_header(), timeout=30)

    print("Details status:", details.status_code)

    if details.status_code != 200:
        print(details.text)
        raise SystemExit(1)

    return {
        item["fields"]["System.Title"]: item["id"]
        for item in details.json().get("value", [])
    }


def add_successor_link(source_id: int, target_id: int) -> None:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/workitems/{source_id}?api-version=7.1"
    )

    target_url = f"https://dev.azure.com/{ORG}/_apis/wit/workItems/{target_id}"

    payload = [
        {
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "System.LinkTypes.Dependency-Forward",
                "url": target_url,
                "attributes": {
                    "comment": "Roadmap dependency created by automation"
                },
            },
        }
    ]

    response = requests.patch(
        url,
        headers=get_auth_header("application/json-patch+json"),
        json=payload,
        timeout=30,
    )

    print(f"Dependency {source_id} → {target_id}")
    print("Status:", response.status_code)

    if response.status_code in (200, 201):
        return

    if response.status_code == 400 and "already exists" in response.text.lower():
        print("Dependency already exists.")
        return

    print(response.text)
    raise SystemExit(1)


def main() -> None:
    features = get_features()

    for source_title, target_title in DEPENDENCIES:
        source_id = features.get(source_title)
        target_id = features.get(target_title)

        if not source_id or not target_id:
            raise RuntimeError(f"Missing dependency item: {source_title} → {target_title}")

        add_successor_link(source_id, target_id)

    print("Feature dependencies created successfully.")


if __name__ == "__main__":
    main()
