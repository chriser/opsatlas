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

FEATURE_TAGS = {
    "Establish delivery governance and project controls": "Governance; Slice 0",
    "Prepare anonymised and synthetic learning data": "Data; MVP; Slice 1",
    "Build ingestion and knowledge indexing capability": "Ingestion; MVP; Retrieval; Slice 1",
    "Build grounded assistant and RAG response flow": "MVP; Q&A; RAG; Slice 1",
    "Improve retrieval quality and evidence assembly": "Evidence; Hardening; Retrieval; Slice 2",
    "Add validation and observability controls": "Observability; Slice 2; Validation",
    "Add analytics and insight capability": "Analytics; Insight; Slice 3",
    "Voice interaction proof around existing assistant API": "Interaction; Slice 4; Voice",
    "Evaluate and harden assistant proof of concept": "Evaluation; Hardening; Slice 5",
    "Prepare final evidence and DT603 delivery artefacts": "Evidence; Slice 6; Submission",
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
    iterations = get_iterations()
    node = iterations.get(old_path)

    if not node:
        print(f"Iteration not found or already renamed: {old_name}")
        return

    identifier = node["identifier"]

    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/classificationnodes/iterations/{identifier}?api-version=7.1"
    )

    payload = {
        "name": new_name,
        "attributes": node.get("attributes", {}),
    }

    response = requests.patch(
        url,
        headers=auth_header(),
        json=payload,
        timeout=30,
    )

    print(f"Rename iteration '{old_name}' → '{new_name}': {response.status_code}")

    if response.status_code not in (200, 201):
        print(response.text)
        raise SystemExit(1)


def get_all_work_items() -> List[Dict]:
    ids = wiql(
        f"""
        SELECT [System.Id]
        FROM WorkItems
        WHERE [System.TeamProject] = '{PROJECT}'
        ORDER BY [System.Id]
        """
    )
    return get_work_items(ids)


def relation_target_id(relation: Dict) -> Optional[int]:
    try:
        return int(relation.get("url", "").rstrip("/").split("/")[-1])
    except ValueError:
        return None


def build_item_lookup(items: List[Dict]) -> Dict[int, Dict]:
    return {item["id"]: item for item in items}


def get_parent_id(item: Dict) -> Optional[int]:
    for relation in item.get("relations", []):
        if relation.get("rel") == "System.LinkTypes.Hierarchy-Reverse":
            return relation_target_id(relation)
    return None


def apply_tags_to_features_stories_and_tasks() -> None:
    print()
    print("Applying inherited tags...")

    items = get_all_work_items()
    lookup = build_item_lookup(items)

    # First apply/repair Feature tags.
    for item in items:
        fields = item.get("fields", {})
        if fields.get("System.WorkItemType") != "Feature":
            continue

        title = fields.get("System.Title")
        target_tags = FEATURE_TAGS.get(title)

        if not target_tags:
            continue

        if fields.get("System.Tags") == target_tags:
            print(f"Feature tags already correct: {item['id']} | {title}")
            continue

        print(f"Tagging Feature {item['id']} | {title} → {target_tags}")
        patch_work_item(
            item["id"],
            [
                {
                    "op": "add",
                    "path": "/fields/System.Tags",
                    "value": target_tags,
                }
            ],
        )

    # Refresh after Feature updates.
    items = get_all_work_items()
    lookup = build_item_lookup(items)

    for item in items:
        fields = item.get("fields", {})
        item_type = fields.get("System.WorkItemType")

        if item_type not in {"User Story", "Task"}:
            continue

        parent_id = get_parent_id(item)
        if not parent_id:
            continue

        parent = lookup.get(parent_id)
        if not parent:
            continue

        parent_type = parent.get("fields", {}).get("System.WorkItemType")
        parent_tags = parent.get("fields", {}).get("System.Tags")

        if not parent_tags:
            continue

        # Tasks inherit from their User Story if present; User Stories inherit from Feature.
        current_tags = fields.get("System.Tags")

        if current_tags == parent_tags:
            continue

        title = fields.get("System.Title")
        print(f"Tagging {item_type} {item['id']} | {title} → {parent_tags}")

        patch_work_item(
            item["id"],
            [
                {
                    "op": "add",
                    "path": "/fields/System.Tags",
                    "value": parent_tags,
                }
            ],
        )


def main() -> None:
    print("Renaming sprint iterations...")

    for old_name, new_name in SPRINT_RENAMES.items():
        rename_iteration(old_name, new_name)

    apply_tags_to_features_stories_and_tasks()

    print()
    print("Done.")
    print("Now rerun:")
    print("python3 automation/azure_devops/list_project_iterations.py")
    print("python3 automation/azure_devops/export_delivery_plan_diagnostics.py")


if __name__ == "__main__":
    main()
