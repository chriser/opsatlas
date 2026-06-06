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

FEATURE_ITERATION_FIXES = {
    "Establish delivery governance and project controls": "Sprint 1 - Governance Foundation",
    "Prepare anonymised and synthetic learning data": "Sprint 2 - Data Strategy and Source Preparation",
    "Build ingestion and knowledge indexing capability": "Sprint 4 - Knowledge Index and Retrieval",
    "Build grounded assistant and RAG response flow": "Sprint 5 - Assistant API and RAG Flow",
    "Add validation and observability controls": "Sprint 6 - Validation and Observability",
    "Add analytics and insight capability": "Sprint 7 - Analytics and Insight",
    "Evaluate and harden assistant proof of concept": "Sprint 8 - Evaluation and Hardening",
    "Prepare final evidence and DT603 delivery artefacts": "Sprint 9 - Final Evidence and Submission Pack",
}

DEPENDENCY_CHAIN = [
    "Establish delivery governance and project controls",
    "Prepare anonymised and synthetic learning data",
    "Build ingestion and knowledge indexing capability",
    "Build grounded assistant and RAG response flow",
    "Add validation and observability controls",
    "Add analytics and insight capability",
    "Evaluate and harden assistant proof of concept",
    "Prepare final evidence and DT603 delivery artefacts",
]

ORPHAN_STORY_REPAIR = {
    "Create first anonymised process learning data pack": "Prepare anonymised and synthetic learning data",
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


def get_all_features() -> Dict[str, Dict]:
    ids = wiql(
        f"""
        SELECT [System.Id]
        FROM WorkItems
        WHERE [System.TeamProject] = '{PROJECT}'
        AND [System.WorkItemType] = 'Feature'
        ORDER BY [System.Id]
        """
    )

    items = get_work_items(ids)
    return {item["fields"]["System.Title"]: item for item in items}


def get_story_by_title(title: str) -> Optional[Dict]:
    ids = wiql(
        f"""
        SELECT [System.Id]
        FROM WorkItems
        WHERE [System.TeamProject] = '{PROJECT}'
        AND [System.WorkItemType] = 'User Story'
        AND [System.Title] = '{title.replace("'", "''")}'
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


def relation_target_id(relation: Dict) -> Optional[int]:
    try:
        return int(relation.get("url", "").rstrip("/").split("/")[-1])
    except ValueError:
        return None


def remove_dependency_links_from_features(features: Dict[str, Dict]) -> None:
    for title, item in features.items():
        removals = []

        for index, relation in enumerate(item.get("relations", [])):
            if relation.get("rel") in {
                "System.LinkTypes.Dependency-Forward",
                "System.LinkTypes.Dependency-Reverse",
            }:
                removals.append(
                    {
                        "op": "remove",
                        "path": f"/relations/{index}",
                    }
                )

        # Remove high indexes first so Azure DevOps relation indexes do not shift.
        removals.sort(key=lambda op: int(op["path"].split("/")[-1]), reverse=True)

        if removals:
            print(f"Removing existing dependency links from {item['id']} | {title}")
            patch_work_item(item["id"], removals)


def add_dependency(source_id: int, target_id: int) -> None:
    payload = [
        {
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "System.LinkTypes.Dependency-Forward",
                "url": f"https://dev.azure.com/{ORG}/_apis/wit/workItems/{target_id}",
                "attributes": {
                    "comment": "Clean delivery roadmap dependency chain rebuilt by automation"
                },
            },
        }
    ]

    print(f"Adding dependency {source_id} → {target_id}")
    patch_work_item(source_id, payload)


def update_feature_iterations(features: Dict[str, Dict]) -> None:
    for title, sprint_name in FEATURE_ITERATION_FIXES.items():
        item = features.get(title)

        if not item:
            raise RuntimeError(f"Missing Feature: {title}")

        target_iteration = f"{PROJECT}\\{sprint_name}"
        current_iteration = item["fields"].get("System.IterationPath")

        if current_iteration == target_iteration:
            print(f"Iteration already correct: {item['id']} | {title}")
            continue

        print(f"Moving Feature {item['id']} | {title} → {target_iteration}")
        patch_work_item(
            item["id"],
            [
                {
                    "op": "add",
                    "path": "/fields/System.IterationPath",
                    "value": target_iteration,
                }
            ],
        )


def reparent_orphan_stories(features: Dict[str, Dict]) -> None:
    for story_title, parent_feature_title in ORPHAN_STORY_REPAIR.items():
        story = get_story_by_title(story_title)

        if not story:
            raise RuntimeError(f"Missing User Story: {story_title}")

        parent_feature = features.get(parent_feature_title)

        if not parent_feature:
            raise RuntimeError(f"Missing parent Feature: {parent_feature_title}")

        existing_parent_relation_indexes = []
        existing_parent_ids = []

        for index, relation in enumerate(story.get("relations", [])):
            if relation.get("rel") == "System.LinkTypes.Hierarchy-Reverse":
                existing_parent_relation_indexes.append(index)
                target_id = relation_target_id(relation)
                if target_id:
                    existing_parent_ids.append(target_id)

        if parent_feature["id"] in existing_parent_ids:
            print(f"Story already has correct parent: {story['id']} | {story_title}")
            continue

        payload = []

        # Remove any wrong parent relations first, high indexes first.
        for index in sorted(existing_parent_relation_indexes, reverse=True):
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
                    "url": f"https://dev.azure.com/{ORG}/_apis/wit/workItems/{parent_feature['id']}",
                    "attributes": {
                        "comment": "Repaired missing parent Feature relationship"
                    },
                },
            }
        )

        print(f"Reparenting story {story['id']} | {story_title} → Feature {parent_feature['id']}")
        patch_work_item(story["id"], payload)


def rebuild_dependency_chain(features: Dict[str, Dict]) -> None:
    for title in DEPENDENCY_CHAIN:
        if title not in features:
            raise RuntimeError(f"Missing Feature in dependency chain: {title}")

    remove_dependency_links_from_features(features)

    # Refresh features after dependency removal.
    features = get_all_features()

    for source_title, target_title in zip(DEPENDENCY_CHAIN, DEPENDENCY_CHAIN[1:]):
        source = features[source_title]
        target = features[target_title]
        add_dependency(source["id"], target["id"])


def main() -> None:
    print("Repairing delivery plan dependencies and feature timing...")

    features = get_all_features()

    print()
    print("Step 1: update Feature iteration paths")
    update_feature_iterations(features)

    print()
    print("Step 2: reparent orphaned User Stories")
    features = get_all_features()
    reparent_orphan_stories(features)

    print()
    print("Step 3: rebuild dependency chain")
    features = get_all_features()
    rebuild_dependency_chain(features)

    print()
    print("Repair completed.")
    print("Now rerun:")
    print("python3 automation/azure_devops/export_delivery_plan_diagnostics.py")


if __name__ == "__main__":
    main()
