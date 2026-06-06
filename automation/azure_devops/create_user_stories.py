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


def get_existing_features(project: str) -> dict:
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

    refs = response.json().get("workItems", [])
    if not refs:
        raise RuntimeError("No Features found. Run create_backlog.py first.")

    ids = ",".join(str(item["id"]) for item in refs)
    detail_url = f"https://dev.azure.com/{org}/{encoded_project}/_apis/wit/workitems?ids={ids}&api-version=7.1"

    details = requests.get(
        detail_url,
        auth=auth(),
        headers={"Accept": "application/json"},
        timeout=30,
    )
    details.raise_for_status()

    features = {}
    for item in details.json().get("value", []):
        title = item["fields"]["System.Title"]
        features[title] = item["id"]

    return features


def main():
    load_env()
    project = os.environ["ADO_PROJECT_NAME"].strip()

    features = get_existing_features(project)

    story_plan = [
        {
            "feature": "Establish delivery governance and project controls",
            "stories": [
                {
                    "title": "Create Azure DevOps project structure for DT602 planning evidence",
                    "description": "As a project owner, I want a structured Azure DevOps space so that the project has a visible delivery, governance and evidence trail.",
                    "criteria": "Azure DevOps project exists; repo is connected; README and documentation structure are committed; backlog hierarchy is visible.",
                    "tasks": [
                        "Create local repository and connect Azure Repo",
                        "Commit initial README and documentation skeleton",
                        "Create Epic and Feature hierarchy"
                    ],
                },
                {
                    "title": "Create decision log and risk log documentation",
                    "description": "As a project owner, I want key decisions and risks documented so that DT602 and DT603 evidence is traceable.",
                    "criteria": "Decision log exists; risk log exists; each has owner, date, status and rationale fields.",
                    "tasks": [
                        "Create decision log template",
                        "Create risk log template",
                        "Publish documentation to repo and Wiki"
                    ],
                },
            ],
        },
        {
            "feature": "Prepare anonymised and synthetic learning data",
            "stories": [
                {
                    "title": "Define synthetic data strategy for assistant learning data",
                    "description": "As a governance reviewer, I want the project to use synthetic or anonymised data so that confidential organisational information is not exposed.",
                    "criteria": "Synthetic data strategy explains source boundaries, anonymisation approach, permitted use and restricted use.",
                    "tasks": [
                        "Document synthetic data rules",
                        "Document anonymisation rules",
                        "Create source register template"
                    ],
                },
                {
                    "title": "Create first anonymised process learning data pack",
                    "description": "As a business analyst, I want a safe process learning data pack so that the assistant can answer process questions without using raw confidential material.",
                    "criteria": "Learning data pack contains process overview, roles, steps, checks, exceptions, systems and open decisions.",
                    "tasks": [
                        "Create process overview record",
                        "Create role and responsibility records",
                        "Create process step records"
                    ],
                },
            ],
        },
        {
            "feature": "Build ingestion and knowledge indexing capability",
            "stories": [
                {
                    "title": "Build source register and document preparation flow",
                    "description": "As a developer, I want source documents registered and prepared so that only approved material enters the knowledge base.",
                    "criteria": "Source register captures source name, type, owner, sensitivity, approval state and processing state.",
                    "tasks": [
                        "Create source register schema",
                        "Create sample source register file",
                        "Create ingestion module placeholder"
                    ],
                },
                {
                    "title": "Build section builder and metadata tagging",
                    "description": "As a developer, I want documents split into meaningful sections so that retrieval returns useful evidence instead of arbitrary chunks.",
                    "criteria": "Sections preserve heading, source reference, process area and metadata tags.",
                    "tasks": [
                        "Create section data model",
                        "Create section builder function",
                        "Create unit tests for section output"
                    ],
                },
            ],
        },
        {
            "feature": "Build grounded assistant and RAG response flow",
            "stories": [
                {
                    "title": "Create assistant API request handling flow",
                    "description": "As a user, I want to submit a process question so that the assistant can route and answer it using controlled evidence.",
                    "criteria": "API accepts a question; returns structured response fields; handles unsupported input gracefully.",
                    "tasks": [
                        "Create FastAPI skeleton",
                        "Create request and response schema",
                        "Create route classification placeholder"
                    ],
                },
                {
                    "title": "Create RAG orchestration proof of concept",
                    "description": "As a user, I want answers based on retrieved evidence so that the assistant does not rely on unsupported model memory.",
                    "criteria": "Question retrieves relevant sections; evidence pack is assembled; answer includes source references.",
                    "tasks": [
                        "Create retrieval placeholder",
                        "Create evidence pack structure",
                        "Create constrained prompt template"
                    ],
                },
            ],
        },
        {
            "feature": "Add validation, observability and evaluation controls",
            "stories": [
                {
                    "title": "Create validation rules for grounded answers",
                    "description": "As a governance reviewer, I want generated answers checked against retrieved evidence so that unsupported certainty is reduced.",
                    "criteria": "Validation checks citation presence, evidence support, confidence and refusal conditions.",
                    "tasks": [
                        "Create validation rule list",
                        "Create validation module placeholder",
                        "Create refusal response examples"
                    ],
                },
                {
                    "title": "Create observability and audit trace records",
                    "description": "As a project reviewer, I want query, retrieval and response traces so that the assistant behaviour can be audited.",
                    "criteria": "Trace record captures question, retrieved evidence IDs, model route, prompt version, validation result and timestamp.",
                    "tasks": [
                        "Create trace schema",
                        "Create logging placeholder",
                        "Create example audit trace"
                    ],
                },
            ],
        },
        {
            "feature": "Add analytics and insight capability",
            "stories": [
                {
                    "title": "Analyse assistant usage for knowledge gaps",
                    "description": "As a project stakeholder, I want to analyse repeated questions and failed answers so that documentation gaps can be identified.",
                    "criteria": "Usage data can be grouped by topic, process area, failed retrieval and repeated question pattern.",
                    "tasks": [
                        "Create usage log schema",
                        "Create sample usage data",
                        "Create first analytics notebook or script"
                    ],
                },
                {
                    "title": "Create basic analytics output for DT603 evidence",
                    "description": "As a student, I want analytics outputs that demonstrate data extraction, cleaning, analysis and evaluation.",
                    "criteria": "Analytics output includes cleaned dataset, summary metrics and interpretation of knowledge-gap patterns.",
                    "tasks": [
                        "Create analytics metrics list",
                        "Create sample output table",
                        "Document interpretation approach"
                    ],
                },
            ],
        },
        {
            "feature": "Prepare final evidence and DT603 delivery artefacts",
            "stories": [
                {
                    "title": "Prepare screenshots and build evidence for submission",
                    "description": "As a student, I want delivery evidence collected throughout the build so that DT603 can explain execution clearly.",
                    "criteria": "Evidence folder contains screenshots, pipeline runs, backlog views, test results and architecture updates.",
                    "tasks": [
                        "Create final evidence folder",
                        "Create screenshot checklist",
                        "Create build evidence index"
                    ],
                },
                {
                    "title": "Document limitations, lessons learned and next steps",
                    "description": "As a student, I want limitations and lessons recorded so that DT604 can evaluate the project honestly.",
                    "criteria": "Documentation covers what worked, what did not, constraints, risks, unresolved decisions and future improvements.",
                    "tasks": [
                        "Create limitations document",
                        "Create lessons learned document",
                        "Create next steps document"
                    ],
                },
            ],
        },
    ]

    for feature_group in story_plan:
        feature_title = feature_group["feature"]
        feature_id = features.get(feature_title)

        if not feature_id:
            raise RuntimeError(f"Feature not found: {feature_title}")

        for story in feature_group["stories"]:
            created_story = create_work_item(
                project,
                "User Story",
                {
                    "System.Title": story["title"],
                    "System.Description": story["description"],
                    "Microsoft.VSTS.Common.AcceptanceCriteria": story["criteria"],
                    "Microsoft.VSTS.Common.BusinessValue": 50,
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
                    },
                    parent_id=created_story["id"],
                )

    print("User Stories and Tasks created successfully.")


if __name__ == "__main__":
    main()
