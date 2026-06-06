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

ORIGINAL_FEATURE_TITLE = "Add validation, observability and evaluation controls"
RENAMED_FEATURE_TITLE = "Add validation and observability controls"
NEW_FEATURE_TITLE = "Evaluate and harden assistant proof of concept"

SPRINT_6 = "Sprint 6 - Validation and Observability"
SPRINT_8 = "Sprint 8 - Evaluation and Hardening"

STORIES_TO_MOVE = [
    "Run end-to-end evaluation and regression checks",
    "Harden documentation, evidence and known limitations",
]

DEPENDENCY_CHAIN = [
    "Establish delivery governance and project controls",
    "Prepare anonymised and synthetic learning data",
    "Build ingestion and knowledge indexing capability",
    "Build grounded assistant and RAG response flow",
    RENAMED_FEATURE_TITLE,
    "Add analytics and insight capability",
    NEW_FEATURE_TITLE,
    "Prepare final evidence and DT603 delivery artefacts",
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


def get_work_items(ids: List[int], expand_relations: bool = True) -> List[Dict]:
    if not ids:
        return []

    expand = "&$expand=relations" if expand_relations else ""

    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/workitems?ids={','.join(map(str, ids))}{expand}&api-version=7.1"
    )

    response = requests.get(url, headers=get_auth_header(), timeout=30)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    return response.json().get("value", [])


def get_single_by_title(work_item_type: str, title: str) -> Optional[Dict]:
    ids = wiql(
        f"""
        SELECT [System.Id]
        FROM WorkItems
        WHERE [System.TeamProject] = '{PROJECT}'
        AND [System.WorkItemType] = '{work_item_type}'
        AND [System.Title] = '{title.replace("'", "''")}'
        ORDER BY [System.Id]
        """
    )

    if not ids:
        return None

    return get_work_items([ids[0]])[0]


def get_features_by_title() -> Dict[str, Dict]:
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

    print(f"Patch work item {work_item_id}: {response.status_code}")

    if response.status_code not in (200, 201):
        print(response.text)
        raise SystemExit(1)

    return response.json()


def create_feature(title: str, description: str, parent_epic_id: int, sprint_name: str) -> Dict:
    existing = get_single_by_title("Feature", title)
    if existing:
        print(f"Feature already exists: {title} | ID {existing['id']}")
        return existing

    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/workitems/$Feature?api-version=7.1"
    )

    payload = [
        {
            "op": "add",
            "path": "/fields/System.Title",
            "value": title,
        },
        {
            "op": "add",
            "path": "/fields/System.Description",
            "value": description,
        },
        {
            "op": "add",
            "path": "/fields/System.IterationPath",
            "value": f"{PROJECT}\\{sprint_name}",
        },
        {
            "op": "add",
            "path": "/fields/Microsoft.VSTS.Common.BusinessValue",
            "value": 82,
        },
        {
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "System.LinkTypes.Hierarchy-Reverse",
                "url": f"https://dev.azure.com/{ORG}/_apis/wit/workItems/{parent_epic_id}",
                "attributes": {
                    "comment": "Linked to parent Epic by automation"
                },
            },
        },
    ]

    response = requests.post(
        url,
        headers=get_auth_header("application/json-patch+json"),
        json=payload,
        timeout=30,
    )

    print(f"Create Feature '{title}': {response.status_code}")

    if response.status_code not in (200, 201):
        print(response.text)
        raise SystemExit(1)

    return response.json()


def get_parent_id(item: Dict) -> Optional[int]:
    for rel in item.get("relations", []):
        if rel.get("rel") == "System.LinkTypes.Hierarchy-Reverse":
            return int(rel["url"].rstrip("/").split("/")[-1])
    return None


def move_story_to_feature(story_title: str, new_feature_id: int, sprint_name: str) -> None:
    story = get_single_by_title("User Story", story_title)
    if not story:
        raise RuntimeError(f"Could not find User Story: {story_title}")

    story_id = story["id"]
    old_parent_id = get_parent_id(story)

    payload = []

    if old_parent_id:
        # Remove existing parent relation by index.
        for index, rel in enumerate(story.get("relations", [])):
            if rel.get("rel") == "System.LinkTypes.Hierarchy-Reverse":
                payload.append({
                    "op": "remove",
                    "path": f"/relations/{index}",
                })
                break

    payload.extend([
        {
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "System.LinkTypes.Hierarchy-Reverse",
                "url": f"https://dev.azure.com/{ORG}/_apis/wit/workItems/{new_feature_id}",
                "attributes": {
                    "comment": "Moved to evaluation/hardening Feature by automation"
                },
            },
        },
        {
            "op": "add",
            "path": "/fields/System.IterationPath",
            "value": f"{PROJECT}\\{sprint_name}",
        },
    ])

    print(f"Moving story '{story_title}' to Feature {new_feature_id}")
    patch_work_item(story_id, payload)


def remove_existing_feature_dependencies(feature_items: Dict[str, Dict]) -> None:
    for title, item in feature_items.items():
        payload = []

        for index, rel in enumerate(item.get("relations", [])):
            if rel.get("rel") in (
                "System.LinkTypes.Dependency-Forward",
                "System.LinkTypes.Dependency-Reverse",
            ):
                payload.append({
                    "op": "remove",
                    "path": f"/relations/{index}",
                })

        # Remove from highest index first so relation indexes remain valid.
        payload = sorted(payload, key=lambda x: int(x["path"].split("/")[-1]), reverse=True)

        if payload:
            print(f"Removing dependency links from Feature {item['id']} | {title}")
            patch_work_item(item["id"], payload)


def add_dependency(source_id: int, target_id: int) -> None:
    payload = [
        {
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "System.LinkTypes.Dependency-Forward",
                "url": f"https://dev.azure.com/{ORG}/_apis/wit/workItems/{target_id}",
                "attributes": {
                    "comment": "Feature roadmap dependency rebuilt by automation"
                },
            },
        }
    ]

    print(f"Adding dependency {source_id} → {target_id}")
    patch_work_item(source_id, payload)


def main() -> None:
    print("Starting Feature split and dependency repair...")

    epic = get_single_by_title("Epic", "Deliver AI Knowledge and Analytics Assistant Proof of Concept")
    if not epic:
        raise RuntimeError("Could not find parent Epic.")

    original_feature = get_single_by_title("Feature", ORIGINAL_FEATURE_TITLE)
    renamed_feature = get_single_by_title("Feature", RENAMED_FEATURE_TITLE)

    if original_feature:
        print(f"Renaming Feature {original_feature['id']} to '{RENAMED_FEATURE_TITLE}' and moving to Sprint 6")
        patch_work_item(
            original_feature["id"],
            [
                {
                    "op": "add",
                    "path": "/fields/System.Title",
                    "value": RENAMED_FEATURE_TITLE,
                },
                {
                    "op": "add",
                    "path": "/fields/System.IterationPath",
                    "value": f"{PROJECT}\\{SPRINT_6}",
                },
            ],
        )
        validation_feature_id = original_feature["id"]
    elif renamed_feature:
        print(f"Feature already renamed: {RENAMED_FEATURE_TITLE} | ID {renamed_feature['id']}")
        validation_feature_id = renamed_feature["id"]
        patch_work_item(
            validation_feature_id,
            [
                {
                    "op": "add",
                    "path": "/fields/System.IterationPath",
                    "value": f"{PROJECT}\\{SPRINT_6}",
                }
            ],
        )
    else:
        raise RuntimeError("Could not find original or renamed validation Feature.")

    new_feature = create_feature(
        NEW_FEATURE_TITLE,
        (
            "Evaluation and hardening feature for Sprint 8. "
            "This separates end-to-end evaluation, regression checks, evidence hardening and limitations review "
            "from the earlier validation and observability implementation work."
        ),
        parent_epic_id=epic["id"],
        sprint_name=SPRINT_8,
    )

    for story_title in STORIES_TO_MOVE:
        move_story_to_feature(story_title, new_feature["id"], SPRINT_8)

    feature_items = get_features_by_title()

    # Refresh after rename/create.
    feature_items = get_features_by_title()

    missing = [title for title in DEPENDENCY_CHAIN if title not in feature_items]
    if missing:
        raise RuntimeError(f"Missing features for dependency chain: {missing}")

    remove_existing_feature_dependencies(feature_items)

    for source_title, target_title in zip(DEPENDENCY_CHAIN, DEPENDENCY_CHAIN[1:]):
        source_id = feature_items[source_title]["id"]
        target_id = feature_items[target_title]["id"]
        add_dependency(source_id, target_id)

    print()
    print("Feature split and dependency repair completed.")
    print(f"Validation Feature ID: {validation_feature_id}")
    print(f"Evaluation Feature ID: {new_feature['id']}")
    print()
    print("Next: refresh the Delivery Plan and rerun diagnostics.")


if __name__ == "__main__":
    main()
