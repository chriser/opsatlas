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

    for line in env_path.read_text().splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


load_env()

ORG = os.getenv("ADO_ORG")
PROJECT = os.getenv("ADO_PROJECT_NAME")
PAT = os.getenv("ADO_PAT")


SPRINT_RENAMES = {
    "Sprint 3 - Ingestion and Section Building": "Sprint 3 - MVP Grounded Q&A Path",
    "Sprint 4 - Knowledge Index and Retrieval": "Sprint 4 - Retrieval and Evidence Hardening",
    "Sprint 5 - Assistant API and RAG Flow": "Sprint 5 - Validation and Observability Controls",
    "Sprint 6 - Validation and Observability": "Sprint 6 - Usage Logging and Basic Analytics",
    "Sprint 7 - Analytics and Insight": "Sprint 7 - Voice Interaction Proof",
}


def auth_header(content_type: str = "application/json") -> Dict[str, str]:
    if not PAT:
        raise ValueError("ADO_PAT is missing. Check your .env file.")

    token = base64.b64encode(f":{PAT}".encode("utf-8")).decode("utf-8")

    return {
        "Authorization": f"Basic {token}",
        "Content-Type": content_type,
        "Accept": "application/json",
    }


def get_iterations() -> Dict[str, Dict]:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/classificationnodes/iterations?$depth=5&api-version=7.1"
    )

    response = requests.get(url, headers=auth_header(), timeout=30)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    nodes = {}

    def walk(node: Dict) -> None:
        path = node.get("path")
        if path:
            nodes[path] = node

        for child in node.get("children", []):
            walk(child)

    walk(response.json())
    return nodes


def rename_iteration(old_name: str, new_name: str) -> None:
    old_path = f"{PROJECT}\\{old_name}"
    new_path = f"{PROJECT}\\{new_name}"

    iterations = get_iterations()

    if new_path in iterations:
        print(f"Already renamed: {new_name}")
        return

    if old_path not in iterations:
        print(f"Old iteration not found: {old_name}")
        return

    node = iterations[old_path]
    attributes = node.get("attributes", {})

    # Azure DevOps expects the classification node path after /iterations/.
    # For a root-level sprint, the path is just the sprint name.
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/classificationnodes/iterations/{quote(old_name, safe='')}"
        f"?api-version=7.1"
    )

    payload = {
        "name": new_name,
        "attributes": {
            "startDate": attributes.get("startDate"),
            "finishDate": attributes.get("finishDate"),
        },
    }

    response = requests.patch(url, headers=auth_header(), json=payload, timeout=30)

    print(f"Rename '{old_name}' → '{new_name}': {response.status_code}")

    if response.status_code not in (200, 201):
        print(response.text)
        raise SystemExit(1)


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


def relation_target_id(relation: Dict) -> Optional[int]:
    try:
        return int(relation.get("url", "").rstrip("/").split("/")[-1])
    except ValueError:
        return None


def get_parent_id(item: Dict) -> Optional[int]:
    for relation in item.get("relations", []):
        if relation.get("rel") == "System.LinkTypes.Hierarchy-Reverse":
            return relation_target_id(relation)
    return None


def get_all_items() -> Dict[int, Dict]:
    ids = wiql(
        f"""
        SELECT [System.Id]
        FROM WorkItems
        WHERE [System.TeamProject] = '{PROJECT}'
        ORDER BY [System.Id]
        """
    )

    return {item["id"]: item for item in get_work_items(ids)}


def find_nearest_parent_tags(item: Dict, lookup: Dict[int, Dict]) -> Optional[str]:
    parent_id = get_parent_id(item)

    while parent_id:
        parent = lookup.get(parent_id)

        if not parent:
            return None

        parent_tags = parent.get("fields", {}).get("System.Tags")

        if parent_tags:
            return parent_tags

        parent_id = get_parent_id(parent)

    return None


def apply_tags_to_tasks() -> None:
    print()
    print("Applying inherited tags to Tasks...")

    lookup = get_all_items()

    for item in lookup.values():
        fields = item.get("fields", {})
        if fields.get("System.WorkItemType") != "Task":
            continue

        current_tags = fields.get("System.Tags")
        inherited_tags = find_nearest_parent_tags(item, lookup)

        if not inherited_tags:
            continue

        if current_tags == inherited_tags:
            continue

        print(f"Tagging Task {item['id']} | {fields.get('System.Title')} → {inherited_tags}")

        patch_work_item(
            item["id"],
            [
                {
                    "op": "add",
                    "path": "/fields/System.Tags",
                    "value": inherited_tags,
                }
            ],
        )


def main() -> None:
    print("Renaming sprint iterations with path-based Azure DevOps API call...")

    for old_name, new_name in SPRINT_RENAMES.items():
        rename_iteration(old_name, new_name)

    apply_tags_to_tasks()

    print()
    print("Done.")
    print("Now rerun:")
    print("python3 automation/azure_devops/list_project_iterations.py")
    print("python3 automation/azure_devops/export_delivery_plan_diagnostics.py")


if __name__ == "__main__":
    main()
