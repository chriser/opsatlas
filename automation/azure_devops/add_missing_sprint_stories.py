import os
from pathlib import Path
from urllib.parse import quote

import requests
from requests.auth import HTTPBasicAuth


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    for line in env_path.read_text().splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


def auth():
    return HTTPBasicAuth("", os.environ["ADO_PAT"].strip())


def patch_headers():
    return {
        "Content-Type": "application/json-patch+json",
        "Accept": "application/json",
    }


def create_work_item(project: str, work_item_type: str, fields: dict, parent_id: int | None = None) -> dict:
    org = os.environ["ADO_ORG"].strip()
    encoded_project = quote(project, safe="")
    encoded_type = quote(work_item_type, safe="")

    url = f"https://dev.azure.com/{org}/{encoded_project}/_apis/wit/workitems/${encoded_type}?api-version=7.1"

    payload = []

    for field_name, value in fields.items():
        payload.append({
            "op": "add",
            "path": f"/fields/{field_name}",
            "value": value,
        })

    if parent_id is not None:
        payload.append({
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "System.LinkTypes.Hierarchy-Reverse",
                "url": f"https://dev.azure.com/{org}/_apis/wit/workItems/{parent_id}",
                "attributes": {
                    "comment": "Linked to parent work item by automation"
                }
            }
        })

    response = requests.post(
        url,
        json=payload,
        auth=auth(),
        headers=patch_headers(),
        timeout=30,
    )

    print(f"Create {work_item_type}: {fields.get('System.Title')}")
    print("Status:", response.status_code)

    if response.status_code not in (200, 201):
        print(response.text)
        raise SystemExit(1)

    item = response.json()
    print("Created ID:", item["id"])
    return item


def get_features(project: str) -> dict:
    org = os.environ["ADO_ORG"].strip()
    encoded_project = quote(project, safe="")

    wiql_url = f"https://dev.azure.com/{org}/{encoded_project}/_apis/wit/wiql?api-version=7.1"

    query = {
        "query": f"""
        SELECT [System.Id], [System.Title]
        FROM WorkItems
        WHERE [System.TeamProject] = '{project}'
        AND [System.WorkItemType] = 'Feature'
        ORDER BY [System.Id]
        """
    }

    response = requests.post(
        wiql_url,
        json=query,
        auth=auth(),
        headers={"Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()

    ids = [str(item["id"]) for item in response.json().get("workItems", [])]

    if not ids:
        raise RuntimeError("No Feature work items found.")

    detail_url = f"https://dev.azure.com/{org}/{encoded_project}/_apis/wit/workitems?ids={','.join(ids)}&api-version=7.1"

    details = requests.get(
        detail_url,
        auth=auth(),
        headers={"Accept": "application/json"},
        timeout=30,
    )
    details.raise_for_status()

    return {
        item["fields"]["System.Title"]: item["id"]
        for item in details.json().get("value", [])
    }


def main() -> None:
    load_env()
    project = os.environ["ADO_PROJECT_NAME"].strip()

    features = get_features(project)

    plan = [
        {
            "feature": "Build ingestion and knowledge indexing capability",
            "sprint": "Sprint 4 - Knowledge Index and Retrieval",
            "stories": [
                {
                    "title": "Build lexical and semantic retrieval index",
                    "description": "As a user, I want the assistant to retrieve relevant process evidence using both keyword and semantic search so that answers are grounded in the right source material.",
                    "criteria": "The retrieval layer supports keyword-style lookup and semantic-style matching; retrieved sections include source metadata; retrieval output can be inspected.",
                    "tasks": [
                        "Create retrieval index interface",
                        "Create lexical retrieval placeholder",
                        "Create semantic retrieval placeholder"
                    ],
                },
                {
                    "title": "Validate retrieval quality with golden questions",
                    "description": "As a project reviewer, I want retrieval tested against known questions so that the assistant can be evaluated before answer generation is trusted.",
                    "criteria": "Golden questions exist; expected evidence is documented; retrieval results are compared against expected source sections.",
                    "tasks": [
                        "Create golden question dataset",
                        "Create retrieval evaluation script",
                        "Document retrieval quality findings"
                    ],
                },
            ],
        },
        {
            "feature": "Add validation, observability and evaluation controls",
            "sprint": "Sprint 8 - Evaluation and Hardening",
            "stories": [
                {
                    "title": "Run end-to-end evaluation and regression checks",
                    "description": "As a project reviewer, I want the full assistant flow tested end to end so that DT603 evidence shows build quality and controlled evaluation.",
                    "criteria": "End-to-end tests cover ingestion, retrieval, RAG response, validation and logging; regression checks are documented.",
                    "tasks": [
                        "Create end-to-end test checklist",
                        "Run regression test suite",
                        "Capture pipeline and test evidence"
                    ],
                },
                {
                    "title": "Harden documentation, evidence and known limitations",
                    "description": "As a student, I want project limitations, risks and evidence organised before final submission so that the project is transparent and academically defensible.",
                    "criteria": "Known limitations are documented; evidence index is updated; risk and decision logs are reviewed; final screenshots are captured.",
                    "tasks": [
                        "Review risk and decision logs",
                        "Update evidence index",
                        "Capture final Azure DevOps screenshots"
                    ],
                },
            ],
        },
    ]

    for group in plan:
        feature_id = features.get(group["feature"])
        if not feature_id:
            raise RuntimeError(f"Feature not found: {group['feature']}")

        iteration_path = f"{project}\\{group['sprint']}"

        for story in group["stories"]:
            created_story = create_work_item(
                project,
                "User Story",
                {
                    "System.Title": story["title"],
                    "System.Description": story["description"],
                    "Microsoft.VSTS.Common.AcceptanceCriteria": story["criteria"],
                    "Microsoft.VSTS.Common.BusinessValue": 50,
                    "System.IterationPath": iteration_path,
                },
                parent_id=feature_id,
            )

            for task_title in story["tasks"]:
                create_work_item(
                    project,
                    "Task",
                    {
                        "System.Title": task_title,
                        "System.Description": f"Implementation task for user story: {story['title']}",
                        "System.IterationPath": iteration_path,
                    },
                    parent_id=created_story["id"],
                )

    print("Missing Sprint 4 and Sprint 8 stories created successfully.")


if __name__ == "__main__":
    main()
