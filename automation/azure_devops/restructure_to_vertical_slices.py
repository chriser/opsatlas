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


SPRINT = {
    "s1": "Sprint 1 - Governance Foundation",
    "s2": "Sprint 2 - Data Strategy and Source Preparation",
    "s3": "Sprint 3 - Ingestion and Section Building",
    "s4": "Sprint 4 - Knowledge Index and Retrieval",
    "s5": "Sprint 5 - Assistant API and RAG Flow",
    "s6": "Sprint 6 - Validation and Observability",
    "s7": "Sprint 7 - Analytics and Insight",
    "s8": "Sprint 8 - Evaluation and Hardening",
    "s9": "Sprint 9 - Final Evidence and Submission Pack",
}


EPIC_PLAN = {
    "Slice 0 - Architecture and Governance Foundation": {
        "sprint": SPRINT["s1"],
        "description": "Foundation slice for architecture, Azure DevOps governance, repository structure, delivery controls, ethics/data controls and planning evidence.",
        "tags": "Slice 0; Governance; Foundation",
    },
    "Slice 1 - MVP Grounded Q&A Path": {
        "sprint": SPRINT["s3"],
        "description": "First runtime slice proving the end-to-end MVP path: synthetic/anonymised source material, ingestion, sectioning, retrieval, grounded answer, citation, basic validation and trace logging.",
        "tags": "Slice 1; MVP; End-to-End",
    },
    "Slice 2 - RAG and Validation Hardening": {
        "sprint": SPRINT["s5"],
        "description": "Hardening slice for better retrieval, evidence assembly, query routing, constrained prompting, confidence rules, refusal behaviour and regression tests.",
        "tags": "Slice 2; RAG; Validation",
    },
    "Slice 3 - Usage Logging and Basic Analytics": {
        "sprint": SPRINT["s6"],
        "description": "Analytics slice for capturing usage events, grouping repeated questions, identifying failed retrievals and producing first knowledge-gap insight outputs.",
        "tags": "Slice 3; Analytics; Insight",
    },
    "Slice 4 - Voice Interaction Proof": {
        "sprint": SPRINT["s7"],
        "description": "Voice proof slice that adds speech-to-text and text-to-speech around the existing validated assistant API without changing the canonical answer pipeline.",
        "tags": "Slice 4; Voice; Interaction",
    },
    "Slice 5 - Evaluation and Evidence Hardening": {
        "sprint": SPRINT["s8"],
        "description": "Evaluation slice for end-to-end testing, regression checks, audit/observability evidence, limitations review and evidence hardening.",
        "tags": "Slice 5; Evaluation; Hardening",
    },
    "Slice 6 - Final Submission Pack": {
        "sprint": SPRINT["s9"],
        "description": "Final slice for screenshots, build evidence, final documentation, lessons learned, limitations and submission artefacts.",
        "tags": "Slice 6; Submission; Evidence",
    },
}


FEATURE_PLAN = {
    "Establish delivery governance and project controls": {
        "epic": "Slice 0 - Architecture and Governance Foundation",
        "sprint": SPRINT["s1"],
        "tags": "Slice 0; Governance",
    },
    "Prepare anonymised and synthetic learning data": {
        "epic": "Slice 1 - MVP Grounded Q&A Path",
        "sprint": SPRINT["s2"],
        "tags": "Slice 1; MVP; Data",
    },
    "Build ingestion and knowledge indexing capability": {
        "epic": "Slice 1 - MVP Grounded Q&A Path",
        "sprint": SPRINT["s3"],
        "tags": "Slice 1; MVP; Retrieval",
    },
    "Build grounded assistant and RAG response flow": {
        "epic": "Slice 1 - MVP Grounded Q&A Path",
        "sprint": SPRINT["s3"],
        "tags": "Slice 1; MVP; Q&A",
    },
    "Add validation and observability controls": {
        "epic": "Slice 2 - RAG and Validation Hardening",
        "sprint": SPRINT["s5"],
        "tags": "Slice 2; Validation; Observability",
    },
    "Add analytics and insight capability": {
        "epic": "Slice 3 - Usage Logging and Basic Analytics",
        "sprint": SPRINT["s6"],
        "tags": "Slice 3; Analytics",
    },
    "Voice interaction proof around existing assistant API": {
        "epic": "Slice 4 - Voice Interaction Proof",
        "sprint": SPRINT["s7"],
        "tags": "Slice 4; Voice",
    },
    "Evaluate and harden assistant proof of concept": {
        "epic": "Slice 5 - Evaluation and Evidence Hardening",
        "sprint": SPRINT["s8"],
        "tags": "Slice 5; Evaluation",
    },
    "Prepare final evidence and DT603 delivery artefacts": {
        "epic": "Slice 6 - Final Submission Pack",
        "sprint": SPRINT["s9"],
        "tags": "Slice 6; Submission",
    },
}


STORY_ITERATION_FIXES = {
    # Slice 1 - MVP should be runnable by the end of Sprint 3.
    "Define synthetic data strategy for assistant learning data": SPRINT["s2"],
    "Create first anonymised process learning data pack": SPRINT["s2"],
    "Build source register and document preparation flow": SPRINT["s2"],
    "Build section builder and metadata tagging": SPRINT["s2"],
    "Build lexical and semantic retrieval index": SPRINT["s3"],
    "Validate retrieval quality with golden questions": SPRINT["s3"],
    "Create assistant API request handling flow": SPRINT["s3"],
    "Create RAG orchestration proof of concept": SPRINT["s3"],

    # Slice 2 - hardening.
    "Create validation rules for grounded answers": SPRINT["s5"],
    "Create observability and audit trace records": SPRINT["s5"],

    # Slice 3 - analytics.
    "Analyse assistant usage for knowledge gaps": SPRINT["s6"],
    "Create basic analytics output for DT603 evidence": SPRINT["s6"],

    # Slice 5 and 6.
    "Run end-to-end evaluation and regression checks": SPRINT["s8"],
    "Harden documentation, evidence and known limitations": SPRINT["s8"],
    "Prepare screenshots and build evidence for submission": SPRINT["s9"],
    "Document limitations, lessons learned and next steps": SPRINT["s9"],
}


VOICE_FEATURE = {
    "title": "Voice interaction proof around existing assistant API",
    "description": (
        "Adds optional voice input and voice output around the existing validated assistant API. "
        "The voice flow must reuse the canonical text request and final validated answer rather than creating a separate answer path."
    ),
    "stories": [
        {
            "title": "Convert spoken process question into canonical text request",
            "description": "As a user, I want to ask a process question by voice so that the assistant can process it through the same pipeline as typed questions.",
            "criteria": "Speech input is converted into a canonical text request; the assistant receives the same request schema used by typed questions; a voice input test case is documented.",
            "tasks": [
                "Create speech-to-text adapter placeholder",
                "Create canonical voice request schema",
                "Create voice input contract test",
            ],
        },
        {
            "title": "Return validated canonical answer through text-to-speech",
            "description": "As a user, I want to hear the validated assistant answer so that voice output remains consistent with the cited text answer.",
            "criteria": "Text-to-speech uses the final validated answer; voice output does not invent or paraphrase beyond the canonical response; a voice output test is documented.",
            "tasks": [
                "Create text-to-speech adapter placeholder",
                "Add speakable answer field to response schema",
                "Create voice output contract test",
            ],
        },
        {
            "title": "Verify voice flow reuses existing validated Q&A pipeline",
            "description": "As a project reviewer, I want the voice proof to reuse the existing assistant pipeline so that it does not bypass retrieval, validation or citation controls.",
            "criteria": "Voice question produces the same answer path as typed question; trace log records voice channel; validation and citation evidence are preserved.",
            "tasks": [
                "Create typed versus voice comparison test",
                "Capture voice proof evidence screenshot",
                "Document voice limitation and next-step notes",
            ],
        },
    ],
}


FEATURE_DEPENDENCY_CHAIN = [
    "Establish delivery governance and project controls",
    "Prepare anonymised and synthetic learning data",
    "Build ingestion and knowledge indexing capability",
    "Build grounded assistant and RAG response flow",
    "Add validation and observability controls",
    "Add analytics and insight capability",
    "Voice interaction proof around existing assistant API",
    "Evaluate and harden assistant proof of concept",
    "Prepare final evidence and DT603 delivery artefacts",
]

EPIC_DEPENDENCY_CHAIN = [
    "Slice 0 - Architecture and Governance Foundation",
    "Slice 1 - MVP Grounded Q&A Path",
    "Slice 2 - RAG and Validation Hardening",
    "Slice 3 - Usage Logging and Basic Analytics",
    "Slice 4 - Voice Interaction Proof",
    "Slice 5 - Evaluation and Evidence Hardening",
    "Slice 6 - Final Submission Pack",
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


def get_all_by_type(work_item_type: str) -> Dict[str, Dict]:
    ids = wiql(
        f"""
        SELECT [System.Id]
        FROM WorkItems
        WHERE [System.TeamProject] = '{PROJECT}'
        AND [System.WorkItemType] = '{work_item_type}'
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
                        "comment": "Linked by vertical slice restructuring automation"
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


def remove_parent_relations(item: Dict) -> List[Dict]:
    removals = []

    for index, relation in enumerate(item.get("relations", [])):
        if relation.get("rel") == "System.LinkTypes.Hierarchy-Reverse":
            removals.append(
                {
                    "op": "remove",
                    "path": f"/relations/{index}",
                }
            )

    removals.sort(key=lambda op: int(op["path"].split("/")[-1]), reverse=True)
    return removals


def reparent_item(item: Dict, parent_id: int) -> None:
    payload = remove_parent_relations(item)

    payload.append(
        {
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "System.LinkTypes.Hierarchy-Reverse",
                "url": f"https://dev.azure.com/{ORG}/_apis/wit/workItems/{parent_id}",
                "attributes": {
                    "comment": "Reparented by vertical slice restructuring automation"
                },
            },
        }
    )

    patch_work_item(item["id"], payload)


def update_fields(item: Dict, field_values: Dict[str, object]) -> None:
    payload = []

    for field_name, value in field_values.items():
        current_value = item.get("fields", {}).get(field_name)

        if current_value == value:
            continue

        payload.append(
            {
                "op": "add",
                "path": f"/fields/{field_name}",
                "value": value,
            }
        )

    if payload:
        patch_work_item(item["id"], payload)
    else:
        print(f"No field updates needed for {item['id']} | {item['fields'].get('System.Title')}")


def create_or_update_epics() -> Dict[str, Dict]:
    print("\nCreating/updating Slice Epics...")

    original = get_by_title("Epic", "Deliver AI Knowledge and Analytics Assistant Proof of Concept")
    slice0 = get_by_title("Epic", "Slice 0 - Architecture and Governance Foundation")

    if original and not slice0:
        print(f"Renaming original Epic {original['id']} to Slice 0")
        patch_work_item(
            original["id"],
            [
                {
                    "op": "add",
                    "path": "/fields/System.Title",
                    "value": "Slice 0 - Architecture and Governance Foundation",
                },
                {
                    "op": "add",
                    "path": "/fields/System.Description",
                    "value": EPIC_PLAN["Slice 0 - Architecture and Governance Foundation"]["description"],
                },
                {
                    "op": "add",
                    "path": "/fields/System.IterationPath",
                    "value": f"{PROJECT}\\{EPIC_PLAN['Slice 0 - Architecture and Governance Foundation']['sprint']}",
                },
                {
                    "op": "add",
                    "path": "/fields/System.Tags",
                    "value": EPIC_PLAN["Slice 0 - Architecture and Governance Foundation"]["tags"],
                },
            ],
        )

    for epic_title, plan in EPIC_PLAN.items():
        create_work_item(
            "Epic",
            epic_title,
            {
                "System.Description": plan["description"],
                "System.IterationPath": f"{PROJECT}\\{plan['sprint']}",
                "System.Tags": plan["tags"],
                "Microsoft.VSTS.Common.BusinessValue": 100,
            },
        )

    epics = get_all_by_type("Epic")

    for epic_title, plan in EPIC_PLAN.items():
        epic = epics[epic_title]
        update_fields(
            epic,
            {
                "System.Description": plan["description"],
                "System.IterationPath": f"{PROJECT}\\{plan['sprint']}",
                "System.Tags": plan["tags"],
            },
        )

    return get_all_by_type("Epic")


def create_voice_feature(epics: Dict[str, Dict]) -> Dict:
    parent_epic = epics["Slice 4 - Voice Interaction Proof"]

    feature = create_work_item(
        "Feature",
        VOICE_FEATURE["title"],
        {
            "System.Description": VOICE_FEATURE["description"],
            "System.IterationPath": f"{PROJECT}\\{SPRINT['s7']}",
            "System.Tags": "Slice 4; Voice",
            "Microsoft.VSTS.Common.BusinessValue": 70,
        },
        parent_id=parent_epic["id"],
    )

    for story in VOICE_FEATURE["stories"]:
        created_story = create_work_item(
            "User Story",
            story["title"],
            {
                "System.Description": story["description"],
                "Microsoft.VSTS.Common.AcceptanceCriteria": story["criteria"],
                "System.IterationPath": f"{PROJECT}\\{SPRINT['s7']}",
                "System.Tags": "Slice 4; Voice",
                "Microsoft.VSTS.Common.BusinessValue": 45,
            },
            parent_id=feature["id"],
        )

        for task_title in story["tasks"]:
            create_work_item(
                "Task",
                task_title,
                {
                    "System.Description": f"Implementation task for user story: {story['title']}",
                    "System.IterationPath": f"{PROJECT}\\{SPRINT['s7']}",
                    "System.Tags": "Slice 4; Voice",
                },
                parent_id=created_story["id"],
            )

    return get_by_title("Feature", VOICE_FEATURE["title"])


def reparent_and_update_features(epics: Dict[str, Dict]) -> Dict[str, Dict]:
    print("\nReparenting Features under Slice Epics...")

    create_voice_feature(epics)

    features = get_all_by_type("Feature")

    for feature_title, plan in FEATURE_PLAN.items():
        feature = features.get(feature_title)

        if not feature:
            raise RuntimeError(f"Missing Feature: {feature_title}")

        target_epic = epics[plan["epic"]]

        print(f"Feature {feature['id']} | {feature_title} → {plan['epic']}")

        reparent_item(feature, target_epic["id"])

        # Refresh feature after reparent before field update.
        feature = get_by_title("Feature", feature_title)

        update_fields(
            feature,
            {
                "System.IterationPath": f"{PROJECT}\\{plan['sprint']}",
                "System.Tags": plan["tags"],
            },
        )

    return get_all_by_type("Feature")


def update_story_and_task_iterations() -> None:
    print("\nUpdating User Story and child Task iterations...")

    for story_title, sprint_name in STORY_ITERATION_FIXES.items():
        story = get_by_title("User Story", story_title)

        if not story:
            print(f"Skipping missing story: {story_title}")
            continue

        target_iteration = f"{PROJECT}\\{sprint_name}"
        update_fields(
            story,
            {
                "System.IterationPath": target_iteration,
            },
        )

        for relation in story.get("relations", []):
            if relation.get("rel") != "System.LinkTypes.Hierarchy-Forward":
                continue

            try:
                task_id = int(relation["url"].rstrip("/").split("/")[-1])
            except ValueError:
                continue

            task = get_work_items([task_id])[0]
            if task["fields"].get("System.WorkItemType") == "Task":
                update_fields(
                    task,
                    {
                        "System.IterationPath": target_iteration,
                    },
                )


def remove_dependency_links(items: Dict[str, Dict]) -> None:
    for title, item in items.items():
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

        removals.sort(key=lambda op: int(op["path"].split("/")[-1]), reverse=True)

        if removals:
            print(f"Removing dependency links from {item['id']} | {title}")
            patch_work_item(item["id"], removals)


def add_dependency(source_id: int, target_id: int) -> None:
    patch_work_item(
        source_id,
        [
            {
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": "System.LinkTypes.Dependency-Forward",
                    "url": f"https://dev.azure.com/{ORG}/_apis/wit/workItems/{target_id}",
                    "attributes": {
                        "comment": "Vertical slice delivery dependency"
                    },
                },
            }
        ],
    )


def rebuild_dependencies() -> None:
    print("\nRebuilding Epic and Feature dependency chains...")

    epics = get_all_by_type("Epic")
    features = get_all_by_type("Feature")

    remove_dependency_links(epics)
    remove_dependency_links(features)

    epics = get_all_by_type("Epic")
    features = get_all_by_type("Feature")

    for source_title, target_title in zip(EPIC_DEPENDENCY_CHAIN, EPIC_DEPENDENCY_CHAIN[1:]):
        print(f"Epic dependency: {source_title} → {target_title}")
        add_dependency(epics[source_title]["id"], epics[target_title]["id"])

    for source_title, target_title in zip(FEATURE_DEPENDENCY_CHAIN, FEATURE_DEPENDENCY_CHAIN[1:]):
        print(f"Feature dependency: {source_title} → {target_title}")
        add_dependency(features[source_title]["id"], features[target_title]["id"])


def main() -> None:
    if not ORG or not PROJECT:
        raise ValueError("ADO_ORG or ADO_PROJECT_NAME missing. Check .env file.")

    print("Starting vertical-slice backlog restructuring...")

    epics = create_or_update_epics()
    reparent_and_update_features(epics)
    update_story_and_task_iterations()
    rebuild_dependencies()

    print()
    print("Vertical-slice restructuring completed.")
    print()
    print("Next checks:")
    print("1. Refresh Azure DevOps → Boards → Delivery Plans")
    print("2. Rerun: python3 automation/azure_devops/export_delivery_plan_diagnostics.py")
    print("3. Confirm dependency chain now follows Slice 0 → Slice 6 and MVP is visible by Sprint 3")


if __name__ == "__main__":
    main()
