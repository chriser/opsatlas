import os
from pathlib import Path
from urllib.parse import quote

import requests
from requests.auth import HTTPBasicAuth


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(".env file not found")

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


def main() -> None:
    load_env()

    project = os.environ["ADO_PROJECT_NAME"].strip()

    epic = create_work_item(
        project,
        "Epic",
        {
            "System.Title": "Deliver AI Knowledge and Analytics Assistant Proof of Concept",
            "System.Description": (
                "Overall delivery epic for the DT602/DT603 AI Knowledge and Analytics Assistant project. "
                "The epic covers planning, governance, synthetic data preparation, ingestion, retrieval, RAG response, "
                "validation, observability, analytics, testing and final academic evidence."
            ),
            "Microsoft.VSTS.Common.BusinessValue": 100,
        },
    )

    features = [
        {
            "title": "Establish delivery governance and project controls",
            "description": "Create Azure DevOps delivery structure, repository, pipeline skeleton, wiki, decision log, risk log, sprint plan and documentation controls.",
            "business_value": 95,
        },
        {
            "title": "Prepare anonymised and synthetic learning data",
            "description": "Create safe process learning data using anonymised and synthetic content aligned to DT602 ethics, confidentiality and data minimisation principles.",
            "business_value": 90,
        },
        {
            "title": "Build ingestion and knowledge indexing capability",
            "description": "Prepare source register, document extraction, sanitisation, section building, metadata tagging and searchable knowledge indexes.",
            "business_value": 85,
        },
        {
            "title": "Build grounded assistant and RAG response flow",
            "description": "Create assistant request handling, retrieval-augmented generation orchestration, evidence assembly and grounded response generation.",
            "business_value": 90,
        },
        {
            "title": "Add validation, observability and evaluation controls",
            "description": "Add citation support checks, refusal handling, query logs, evidence traces, model/prompt tracking, golden questions and regression evidence.",
            "business_value": 85,
        },
        {
            "title": "Add analytics and insight capability",
            "description": "Analyse question logs, repeated knowledge gaps, onboarding friction, documentation gaps and potential process improvement indicators.",
            "business_value": 80,
        },
        {
            "title": "Prepare final evidence and DT603 delivery artefacts",
            "description": "Prepare build evidence, screenshots, pipeline evidence, test evidence, evaluation notes, limitations and next-step documentation.",
            "business_value": 75,
        },
    ]

    for feature in features:
        create_work_item(
            project,
            "Feature",
            {
                "System.Title": feature["title"],
                "System.Description": feature["description"],
                "Microsoft.VSTS.Common.BusinessValue": feature["business_value"],
            },
            parent_id=epic["id"],
        )

    print("Backlog hierarchy created successfully.")


if __name__ == "__main__":
    main()
