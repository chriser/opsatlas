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

SPRINT_4 = "Sprint 4 - Knowledge Index and Retrieval"

NEW_FEATURE_TITLE = "Improve retrieval quality and evidence assembly"
PARENT_EPIC_TITLE = "Slice 2 - RAG and Validation Hardening"

PREDECESSOR_FEATURE_TITLE = "Build grounded assistant and RAG response flow"
SUCCESSOR_FEATURE_TITLE = "Add validation and observability controls"

STORIES = [
    {
        "title": "Improve evidence selection for process questions",
        "description": (
            "As a user, I want the assistant to retrieve the most relevant process evidence "
            "so that the answer is based on the correct section of the controlled learning material."
        ),
        "criteria": (
            "Golden questions return relevant evidence sections; retrieved evidence includes source metadata; "
            "irrelevant or weak evidence is visibly reduced compared with the Sprint 3 MVP."
        ),
        "tasks": [
            "Review Sprint 3 retrieval results",
            "Tune lexical retrieval ranking",
            "Tune semantic retrieval ranking",
        ],
    },
    {
        "title": "Create evidence assembly rules for cited answers",
        "description": (
            "As a project reviewer, I want retrieved sections assembled into a controlled evidence pack "
            "so that the assistant can generate a grounded answer with traceable citations."
        ),
        "criteria": (
            "Evidence pack has a stable schema; answer generation receives only selected source sections; "
            "citation metadata is preserved in the response payload."
        ),
        "tasks": [
            "Create evidence pack schema",
            "Add citation metadata mapping",
            "Create evidence assembly unit test",
        ],
    },
    {
        "title": "Add retrieval confidence and fallback behaviour",
        "description": (
            "As a user, I want the assistant to avoid weak or unsupported answers when retrieval confidence is low "
            "so that the PoC demonstrates safer grounded-answer behaviour."
        ),
        "criteria": (
            "Low-confidence retrieval is detected; fallback behaviour is documented; "
            "unsupported questions are routed towards refusal or qualified answer handling."
        ),
        "tasks": [
            "Define retrieval confidence thresholds",
            "Create low-confidence fallback rule",
            "Add fallback test examples",
        ],
    },
]


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


def get_by_title(work_item_type: str, title: str) -> Optional[Dict]:
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
        return None

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


def create_work_item(work_item_type: str, title: str, fields: Dict, parent_id: Optional[int] = None) -> Dict:
    existing = get_by_title(work_item_type, title)

    if existing:
        print(f"{work_item_type} already exists: {title} | ID {existing['id']}")
        return existing

    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/workitems/${quote(work_item_type, safe='')}?api-version=7.1"
    )

    payload = [
        {
            "op": "add",
            "path": "/fields/System.Title",
            "value": title,
        }
    ]

    for field_name, value in fields.items():
        payload.append(
            {
                "op": "add",
                "path": f"/fields/{field_name}",
                "value": value,
            }
        )

    if parent_id is not None:
        payload.append(
            {
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": "System.LinkTypes.Hierarchy-Reverse",
                    "url": f"https://dev.azure.com/{ORG}/_apis/wit/workItems/{parent_id}",
                    "attributes": {
                        "comment": "Linked by Sprint 4 retrieval hardening automation"
                    },
                },
            }
        )

    response = requests.post(
        url,
        headers=get_auth_header("application/json-patch+json"),
        json=payload,
        timeout=30,
    )

    print(f"Create {work_item_type}: {title} | {response.status_code}")

    if response.status_code not in (200, 201):
        print(response.text)
        raise SystemExit(1)

    return response.json()


def relation_target_id(relation: Dict) -> Optional[int]:
    try:
        return int(relation.get("url", "").rstrip("/").split("/")[-1])
    except ValueError:
        return None


def remove_dependency(source: Dict, target: Dict) -> None:
    removals = []

    for index, relation in enumerate(source.get("relations", [])):
        if relation.get("rel") == "System.LinkTypes.Dependency-Forward" and relation_target_id(relation) == target["id"]:
            removals.append(
                {
                    "op": "remove",
                    "path": f"/relations/{index}",
                }
            )

    if not removals:
        print(f"No existing dependency to remove: {source['id']} → {target['id']}")
        return

    removals.sort(key=lambda op: int(op["path"].split("/")[-1]), reverse=True)
    print(f"Removing dependency: {source['fields']['System.Title']} → {target['fields']['System.Title']}")
    patch_work_item(source["id"], removals)


def add_dependency(source: Dict, target: Dict) -> None:
    source = get_work_items([source["id"]])[0]

    for relation in source.get("relations", []):
        if relation.get("rel") == "System.LinkTypes.Dependency-Forward" and relation_target_id(relation) == target["id"]:
            print(f"Dependency already exists: {source['id']} → {target['id']}")
            return

    payload = [
        {
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "System.LinkTypes.Dependency-Forward",
                "url": f"https://dev.azure.com/{ORG}/_apis/wit/workItems/{target['id']}",
                "attributes": {
                    "comment": "Inserted Sprint 4 retrieval hardening dependency"
                },
            },
        }
    ]

    print(f"Adding dependency: {source['fields']['System.Title']} → {target['fields']['System.Title']}")
    patch_work_item(source["id"], payload)


def main() -> None:
    print("Filling Sprint 4 with retrieval hardening work...")

    parent_epic = get_by_title("Epic", PARENT_EPIC_TITLE)
    predecessor = get_by_title("Feature", PREDECESSOR_FEATURE_TITLE)
    successor = get_by_title("Feature", SUCCESSOR_FEATURE_TITLE)

    if not parent_epic:
        raise RuntimeError(f"Missing parent Epic: {PARENT_EPIC_TITLE}")
    if not predecessor:
        raise RuntimeError(f"Missing predecessor Feature: {PREDECESSOR_FEATURE_TITLE}")
    if not successor:
        raise RuntimeError(f"Missing successor Feature: {SUCCESSOR_FEATURE_TITLE}")

    new_feature = create_work_item(
        "Feature",
        NEW_FEATURE_TITLE,
        {
            "System.Description": (
                "Sprint 4 hardening feature for improving retrieval quality, evidence assembly, "
                "citation metadata and low-confidence fallback behaviour before validation and observability controls are added."
            ),
            "System.IterationPath": f"{PROJECT}\\{SPRINT_4}",
            "System.Tags": "Slice 2; Retrieval; Evidence; Hardening",
            "Microsoft.VSTS.Common.BusinessValue": 84,
        },
        parent_id=parent_epic["id"],
    )

    for story in STORIES:
        created_story = create_work_item(
            "User Story",
            story["title"],
            {
                "System.Description": story["description"],
                "Microsoft.VSTS.Common.AcceptanceCriteria": story["criteria"],
                "System.IterationPath": f"{PROJECT}\\{SPRINT_4}",
                "System.Tags": "Slice 2; Retrieval; Evidence",
                "Microsoft.VSTS.Common.BusinessValue": 50,
            },
            parent_id=new_feature["id"],
        )

        for task_title in story["tasks"]:
            create_work_item(
                "Task",
                task_title,
                {
                    "System.Description": f"Implementation task for user story: {story['title']}",
                    "System.IterationPath": f"{PROJECT}\\{SPRINT_4}",
                    "System.Tags": "Slice 2; Retrieval; Evidence",
                },
                parent_id=created_story["id"],
            )

    # Refresh items before dependency changes.
    predecessor = get_by_title("Feature", PREDECESSOR_FEATURE_TITLE)
    new_feature = get_by_title("Feature", NEW_FEATURE_TITLE)
    successor = get_by_title("Feature", SUCCESSOR_FEATURE_TITLE)

    # Replace 27 → 28 with 27 → new Sprint 4 feature → 28.
    remove_dependency(predecessor, successor)
    add_dependency(predecessor, new_feature)
    add_dependency(new_feature, successor)

    print()
    print("Sprint 4 retrieval hardening work added.")
    print("Now rerun:")
    print("python3 automation/azure_devops/export_delivery_plan_diagnostics.py")


if __name__ == "__main__":
    main()
