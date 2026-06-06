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


REPAIR_PARENTS = {
    "Create RAG orchestration proof of concept": "Build grounded assistant and RAG response flow",
    "Create observability and audit trace records": "Add validation and observability controls",
}

REMOVE_DEPENDENCY = {
    "source": "Build ingestion and knowledge indexing capability",
    "target": "Build grounded assistant and RAG response flow",
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


def wiql(query: str) -> List[int]:
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

    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/workitems?ids={','.join(map(str, ids))}&$expand=relations&api-version=7.1"
    )

    response = requests.get(url, headers=get_auth_header(), timeout=30)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    return response.json().get("value", [])


def get_by_title(work_item_type: str, title: str) -> Dict:
    safe_title = title.replace("'", "''")

    ids = wiql(
        f"""
        SELECT [System.Id]
        FROM WorkItems
        WHERE [System.TeamProject] = '{PROJECT}'
        AND [System.WorkItemType] = '{work_item_type}'
        AND [System.Title] = '{safe_title}'
        ORDER BY [System.Id]
        """
    )

    if not ids:
        raise RuntimeError(f"Could not find {work_item_type}: {title}")

    return get_work_items([ids[0]])[0]


def patch_work_item(work_item_id: int, payload: List[Dict]) -> Dict:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/workitems/{work_item_id}?api-version=7.1"
    )

    response = requests.patch(
        url,
        headers=get_auth_header("application/json-patch+json"),
        json=payload,
        timeout=30,
    )

    print(f"Patch {work_item_id}: {response.status_code}")

    if response.status_code not in (200, 201):
        print(response.text)
        raise SystemExit(1)

    return response.json()


def relation_target_id(relation: Dict) -> Optional[int]:
    try:
        return int(relation.get("url", "").rstrip("/").split("/")[-1])
    except ValueError:
        return None


def reparent_story(story_title: str, parent_feature_title: str) -> None:
    story = get_by_title("User Story", story_title)
    parent = get_by_title("Feature", parent_feature_title)

    current_parent_ids = []
    parent_relation_indexes = []

    for index, relation in enumerate(story.get("relations", [])):
        if relation.get("rel") == "System.LinkTypes.Hierarchy-Reverse":
            parent_relation_indexes.append(index)
            target_id = relation_target_id(relation)
            if target_id:
                current_parent_ids.append(target_id)

    if parent["id"] in current_parent_ids:
        print(f"Already correctly parented: {story_title}")
        return

    payload = []

    for index in sorted(parent_relation_indexes, reverse=True):
        payload.append(
            {
                "op": "remove",
                "path": f"/relations/{index}",
            }
        )

    payload.append(
        {
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "System.LinkTypes.Hierarchy-Reverse",
                "url": f"https://dev.azure.com/{ORG}/_apis/wit/workItems/{parent['id']}",
                "attributes": {
                    "comment": "Final vertical-slice cleanup: repaired parent Feature"
                },
            },
        }
    )

    print(f"Reparenting '{story_title}' → '{parent_feature_title}'")
    patch_work_item(story["id"], payload)


def remove_specific_dependency(source_title: str, target_title: str) -> None:
    source = get_by_title("Feature", source_title)
    target = get_by_title("Feature", target_title)

    removals = []

    for index, relation in enumerate(source.get("relations", [])):
        if relation.get("rel") != "System.LinkTypes.Dependency-Forward":
            continue

        if relation_target_id(relation) == target["id"]:
            removals.append(
                {
                    "op": "remove",
                    "path": f"/relations/{index}",
                }
            )

    if not removals:
        print(f"No dependency found to remove: {source_title} → {target_title}")
        return

    removals.sort(key=lambda op: int(op["path"].split("/")[-1]), reverse=True)

    print(f"Removing same-sprint dependency: {source_title} → {target_title}")
    patch_work_item(source["id"], removals)


def main() -> None:
    print("Finalising vertical-slice cleanup...")

    for story_title, parent_feature_title in REPAIR_PARENTS.items():
        reparent_story(story_title, parent_feature_title)

    remove_specific_dependency(
        REMOVE_DEPENDENCY["source"],
        REMOVE_DEPENDENCY["target"],
    )

    print()
    print("Cleanup completed.")
    print("Now rerun:")
    print("python3 automation/azure_devops/export_delivery_plan_diagnostics.py")


if __name__ == "__main__":
    main()
