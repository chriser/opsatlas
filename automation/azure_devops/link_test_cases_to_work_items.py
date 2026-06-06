import base64
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import requests


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(".env file not found")

    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


load_env()

ORG = os.getenv("ADO_ORG")
PROJECT = os.getenv("ADO_PROJECT_NAME")
PAT = os.getenv("ADO_PAT")


# Test Case title -> target work item type/title
TEST_LINKS: List[Tuple[str, str, str]] = [
    (
        "Verify source register captures required governance fields",
        "User Story",
        "Build source register and document preparation flow",
    ),
    (
        "Verify synthetic data contains no confidential identifiers",
        "Feature",
        "Prepare anonymised and synthetic learning data",
    ),
    (
        "Verify section builder creates meaningful process sections",
        "User Story",
        "Build section builder and metadata tagging",
    ),
    (
        "Verify retrieval returns expected evidence for golden questions",
        "Feature",
        "Improve retrieval quality and evidence assembly",
    ),
    (
        "Verify grounded answer includes source evidence",
        "Feature",
        "Build grounded assistant and RAG response flow",
    ),
    (
        "Verify unsupported question is refused or qualified",
        "Feature",
        "Add validation and observability controls",
    ),
    (
        "Verify observability trace is created for each assistant interaction",
        "User Story",
        "Create observability and audit trace records",
    ),
    (
        "Verify analytics output identifies repeated knowledge gaps",
        "Feature",
        "Add analytics and insight capability",
    ),
    (
        "Verify end-to-end assistant flow",
        "Feature",
        "Evaluate and harden assistant proof of concept",
    ),
]


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


def relation_target_id(relation: Dict) -> Optional[int]:
    try:
        return int(relation.get("url", "").rstrip("/").split("/")[-1])
    except ValueError:
        return None


def patch_work_item(work_item_id: int, payload: List[Dict]) -> Dict:
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

    print(f"Patch {work_item_id}: {response.status_code}")

    if response.status_code not in (200, 201):
        print(response.text)
        raise SystemExit(1)

    return response.json()


def already_linked(test_case: Dict, target_id: int) -> bool:
    for relation in test_case.get("relations", []):
        if relation_target_id(relation) == target_id:
            rel = relation.get("rel", "")
            if rel in {
                "Microsoft.VSTS.Common.TestedBy-Forward",
                "Microsoft.VSTS.Common.TestedBy-Reverse",
                "System.LinkTypes.Related",
            }:
                return True

    return False


def link_test_case_to_target(test_case: Dict, target: Dict) -> None:
    test_case_id = test_case["id"]
    target_id = target["id"]

    if already_linked(test_case, target_id):
        print(f"Already linked: Test Case {test_case_id} → Work Item {target_id}")
        return

    # Link from requirement/capability to test case using TestedBy-Forward.
    # This normally appears in Azure DevOps as Tested By / Tests relationship.
    payload = [
        {
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "Microsoft.VSTS.Common.TestedBy-Forward",
                "url": f"https://dev.azure.com/{ORG}/_apis/wit/workItems/{test_case_id}",
                "attributes": {
                    "comment": "Linked test case to requirement/capability by automation"
                },
            },
        }
    ]

    print(
        f"Linking target {target_id} '{target['fields']['System.Title']}' "
        f"→ Test Case {test_case_id} '{test_case['fields']['System.Title']}'"
    )

    patch_work_item(target_id, payload)


def main() -> None:
    print("Linking Test Cases to relevant work items...")

    for test_title, target_type, target_title in TEST_LINKS:
        test_case = get_by_title("Test Case", test_title)
        target = get_by_title(target_type, target_title)

        link_test_case_to_target(test_case, target)

    print()
    print("Test Case linking completed.")
    print("Check Azure DevOps → Boards → Work Items → open a User Story/Feature → Links section")


if __name__ == "__main__":
    main()
