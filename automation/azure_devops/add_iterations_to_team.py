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
TEAM = "AI Knowledge and Analytics Assistant Team"


SPRINT_NAMES: List[str] = [
    "Sprint 1 - Governance Foundation",
    "Sprint 2 - Data Strategy and Source Preparation",
    "Sprint 3 - Ingestion and Section Building",
    "Sprint 4 - Knowledge Index and Retrieval",
    "Sprint 5 - Assistant API and RAG Flow",
    "Sprint 6 - Validation and Observability",
    "Sprint 7 - Analytics and Insight",
    "Sprint 8 - Evaluation and Hardening",
    "Sprint 9 - Final Evidence and Submission Pack",
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


def get_project_iterations() -> Dict[str, str]:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/classificationnodes/iterations?$depth=5&api-version=7.1"
    )

    response = requests.get(url, headers=get_auth_header(), timeout=30)

    print("List project iterations status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    result = {}

    def walk(node: Dict) -> None:
        name = node.get("name")
        identifier = node.get("identifier")
        if name and identifier:
            result[name] = identifier

        for child in node.get("children", []):
            walk(child)

    walk(response.json())
    return result


def add_iteration_to_team(iteration_id: str, sprint_name: str) -> None:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}/{quote(TEAM, safe='')}"
        f"/_apis/work/teamsettings/iterations?api-version=7.1"
    )

    payload = {
        "id": iteration_id
    }

    response = requests.post(url, headers=get_auth_header(), json=payload, timeout=30)

    print(f"Add to team: {sprint_name}")
    print("Status:", response.status_code)

    if response.status_code in (200, 201):
        return

    if response.status_code == 400 and "already exists" in response.text.lower():
        print("Already added.")
        return

    print(response.text)
    raise SystemExit(1)


def main() -> None:
    if not ORG or not PROJECT:
        raise ValueError("ADO_ORG or ADO_PROJECT_NAME missing. Check .env file.")

    iterations = get_project_iterations()

    for sprint_name in SPRINT_NAMES:
        iteration_id = iterations.get(sprint_name)
        if not iteration_id:
            raise RuntimeError(f"Could not find project iteration: {sprint_name}")

        add_iteration_to_team(iteration_id, sprint_name)

    print("All sprint iterations added to team successfully.")


if __name__ == "__main__":
    main()
