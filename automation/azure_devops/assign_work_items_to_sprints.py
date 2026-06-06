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


STORY_TO_SPRINT: Dict[str, str] = {
    "Create Azure DevOps project structure for DT602 planning evidence": "Sprint 1 - Governance Foundation",
    "Create decision log and risk log documentation": "Sprint 1 - Governance Foundation",

    "Define synthetic data strategy for assistant learning data": "Sprint 2 - Data Strategy and Source Preparation",
    "Create first anonymised process learning data pack": "Sprint 2 - Data Strategy and Source Preparation",

    "Build source register and document preparation flow": "Sprint 3 - Ingestion and Section Building",
    "Build section builder and metadata tagging": "Sprint 3 - Ingestion and Section Building",

    "Create assistant API request handling flow": "Sprint 5 - Assistant API and RAG Flow",
    "Create RAG orchestration proof of concept": "Sprint 5 - Assistant API and RAG Flow",

    "Create validation rules for grounded answers": "Sprint 6 - Validation and Observability",
    "Create observability and audit trace records": "Sprint 6 - Validation and Observability",

    "Analyse assistant usage for knowledge gaps": "Sprint 7 - Analytics and Insight",
    "Create basic analytics output for DT603 evidence": "Sprint 7 - Analytics and Insight",

    "Prepare screenshots and build evidence for submission": "Sprint 9 - Final Evidence and Submission Pack",
    "Document limitations, lessons learned and next steps": "Sprint 9 - Final Evidence and Submission Pack",
}


def get_auth_header(content_type: str = "application/json") -> Dict[str, str]:
    if not PAT:
        raise ValueError("ADO_PAT is missing. Check your .env file.")

    token = base64.b64encode(f":{PAT}".encode("utf-8")).decode("utf-8")

    return {
        "Authorization": f"Basic {token}",
        "Content-Type": content_type,
        "Accept": "application/json",
    }


def run_wiql(query: str) -> List[int]:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/wiql?api-version=7.1"
    )

    response = requests.post(
        url,
        headers=get_auth_header(),
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

    id_text = ",".join(str(item_id) for item_id in ids)

    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/workitems?ids={id_text}&$expand=relations&api-version=7.1"
    )

    response = requests.get(
        url,
        headers=get_auth_header(),
        timeout=30,
    )

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


def get_child_task_ids(parent_item: Dict) -> List[int]:
    child_ids = []

    for relation in parent_item.get("relations", []):
        if relation.get("rel") == "System.LinkTypes.Hierarchy-Forward":
            url = relation.get("url", "")
            child_ids.append(int(url.rstrip("/").split("/")[-1]))

    return child_ids


def main() -> None:
    if not ORG or not PROJECT:
        raise ValueError("ADO_ORG or ADO_PROJECT_NAME missing. Check .env file.")

    story_ids = run_wiql(
        f"""
        SELECT [System.Id]
        FROM WorkItems
        WHERE [System.TeamProject] = '{PROJECT}'
        AND [System.WorkItemType] = 'User Story'
        ORDER BY [System.Id]
        """
    )

    stories = get_work_items(story_ids)

    for story in stories:
        story_id = story["id"]
        title = story["fields"].get("System.Title")
        sprint_name = STORY_TO_SPRINT.get(title)

        if not sprint_name:
            print(f"Skipping unmapped story {story_id}: {title}")
            continue

        iteration_path = f"{PROJECT}\\{sprint_name}"

        update_iteration_path(story_id, iteration_path)

        child_task_ids = get_child_task_ids(story)
        child_tasks = get_work_items(child_task_ids)

        for task in child_tasks:
            update_iteration_path(task["id"], iteration_path)

    print("Sprint assignment completed successfully.")


if __name__ == "__main__":
    main()
