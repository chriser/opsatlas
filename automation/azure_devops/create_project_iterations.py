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

    for line in env_path.read_text().splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


load_env()

ORG = os.getenv("ADO_ORG")
PROJECT = os.getenv("ADO_PROJECT_NAME")
PAT = os.getenv("ADO_PAT")


SPRINTS: List[Dict[str, str]] = [
    {
        "name": "Sprint 1 - Governance Foundation",
        "startDate": "2026-06-15T00:00:00Z",
        "finishDate": "2026-06-21T23:59:59Z",
    },
    {
        "name": "Sprint 2 - Data Strategy and Source Preparation",
        "startDate": "2026-06-22T00:00:00Z",
        "finishDate": "2026-06-28T23:59:59Z",
    },
    {
        "name": "Sprint 3 - Ingestion and Section Building",
        "startDate": "2026-06-29T00:00:00Z",
        "finishDate": "2026-07-05T23:59:59Z",
    },
    {
        "name": "Sprint 4 - Knowledge Index and Retrieval",
        "startDate": "2026-07-06T00:00:00Z",
        "finishDate": "2026-07-12T23:59:59Z",
    },
    {
        "name": "Sprint 5 - Assistant API and RAG Flow",
        "startDate": "2026-07-13T00:00:00Z",
        "finishDate": "2026-07-19T23:59:59Z",
    },
    {
        "name": "Sprint 6 - Validation and Observability",
        "startDate": "2026-07-20T00:00:00Z",
        "finishDate": "2026-07-26T23:59:59Z",
    },
    {
        "name": "Sprint 7 - Analytics and Insight",
        "startDate": "2026-07-27T00:00:00Z",
        "finishDate": "2026-08-02T23:59:59Z",
    },
    {
        "name": "Sprint 8 - Evaluation and Hardening",
        "startDate": "2026-08-03T00:00:00Z",
        "finishDate": "2026-08-09T23:59:59Z",
    },
    {
        "name": "Sprint 9 - Final Evidence and Submission Pack",
        "startDate": "2026-08-10T00:00:00Z",
        "finishDate": "2026-08-14T23:59:59Z",
    },
]


def get_auth_header() -> Dict[str, str]:
    if not PAT:
        raise ValueError("ADO_PAT is missing. Check your .env file.")

    token = base64.b64encode(f":{PAT}".encode("utf-8")).decode("utf-8")

    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def create_iteration(sprint: Dict[str, str]) -> Dict:
    if not ORG or not PROJECT:
        raise ValueError("ADO_ORG or ADO_PROJECT_NAME is missing. Check your .env file.")

    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/classificationnodes/iterations?api-version=7.1"
    )

    payload = {
        "name": sprint["name"],
        "attributes": {
            "startDate": sprint["startDate"],
            "finishDate": sprint["finishDate"],
        },
    }

    response = requests.post(
        url,
        headers=get_auth_header(),
        json=payload,
        timeout=30,
    )

    print(f"Create iteration: {sprint['name']}")
    print("Status:", response.status_code)

    if response.status_code in (200, 201):
        return response.json()

    if response.status_code == 400 and "already exists" in response.text.lower():
        print(f"Already exists: {sprint['name']}")
        return {}

    raise RuntimeError(
        f"Failed to create iteration {sprint['name']}. "
        f"Status: {response.status_code}. Response: {response.text}"
    )


def main() -> None:
    for sprint in SPRINTS:
        result = create_iteration(sprint)
        if result:
            print(
                f"Created iteration: {result.get('name')} "
                f"({result.get('attributes', {}).get('startDate')} to "
                f"{result.get('attributes', {}).get('finishDate')})"
            )

    print("Project iterations created successfully.")


if __name__ == "__main__":
    main()
