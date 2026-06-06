import base64
import os
from pathlib import Path
from typing import Dict
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
PLAN_NAME = "AI Knowledge and Analytics Assistant Delivery Plan"


def get_auth_header() -> Dict[str, str]:
    if not PAT:
        raise ValueError("ADO_PAT is missing. Check your .env file.")

    token = base64.b64encode(f":{PAT}".encode("utf-8")).decode("utf-8")

    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def find_plan_id() -> str:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/work/plans?api-version=7.1"
    )

    response = requests.get(url, headers=get_auth_header(), timeout=30)

    print("List plans status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    plans = response.json().get("value", [])

    print("Available plans:")
    for plan in plans:
        print("-", plan.get("name"), "|", plan.get("id"))

    for plan in plans:
        if plan.get("name") == PLAN_NAME:
            return plan["id"]

    raise RuntimeError(f"Could not find Delivery Plan named: {PLAN_NAME}")


def read_plan(plan_id: str) -> Dict:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/work/plans/{plan_id}?api-version=7.1"
    )

    response = requests.get(url, headers=get_auth_header(), timeout=30)

    print("Read plan status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    return response.json()


def update_plan(plan: Dict) -> Dict:
    plan_id = plan["id"]

    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/work/plans/{plan_id}?api-version=7.1"
    )

    properties = plan.get("properties", {})

    properties["styleSettings"] = [
        {
            "name": "Closed",
            "isEnabled": "True",
            "filter": "[System.State] = 'Closed'",
            "clauses": [
                {
                    "fieldName": "System.State",
                    "logicalOperator": "AND",
                    "operator": "=",
                    "value": "Closed",
                }
            ],
            "settings": {
                "background-color": "#339947",
                "title-color": "#000000",
            },
        },
        {
            "name": "Epic",
            "isEnabled": "True",
            "filter": "[System.WorkItemType] = 'Epic'",
            "clauses": [
                {
                    "fieldName": "System.WorkItemType",
                    "logicalOperator": "AND",
                    "operator": "=",
                    "value": "Epic",
                }
            ],
            "settings": {
                "background-color": "#FBD0A5",
                "title-color": "#E87025",
            },
        },
        {
            "name": "Feature",
            "isEnabled": "True",
            "filter": "[System.WorkItemType] = 'Feature'",
            "clauses": [
                {
                    "fieldName": "System.WorkItemType",
                    "logicalOperator": "AND",
                    "operator": "=",
                    "value": "Feature",
                }
            ],
            "settings": {
                "background-color": "#C7ABD0",
                "title-color": "#000000",
            },
        },
        {
            "name": "User Story",
            "isEnabled": "True",
            "filter": "[System.WorkItemType] = 'User Story'",
            "clauses": [
                {
                    "fieldName": "System.WorkItemType",
                    "logicalOperator": "AND",
                    "operator": "=",
                    "value": "User Story",
                }
            ],
            "settings": {
                "background-color": "#7FBCE5",
                "title-color": "#000000",
            },
        },
        {
            "name": "Risk tagged work",
            "isEnabled": "True",
            "filter": "[System.Tags] Contains 'Risk'",
            "clauses": [
                {
                    "fieldName": "System.Tags",
                    "logicalOperator": "AND",
                    "operator": "Contains",
                    "value": "Risk",
                }
            ],
            "settings": {
                "background-color": "#FFD6D6",
                "title-color": "#000000",
            },
        },
    ]

    payload = {
        "id": plan["id"],
        "revision": plan["revision"],
        "name": plan["name"],
        "type": plan["type"],
        "description": plan.get("description"),
        "properties": properties,
    }

    response = requests.put(
        url,
        headers=get_auth_header(),
        json=payload,
        timeout=30,
    )

    print("Update plan styles status:", response.status_code)
    print(response.text)

    if response.status_code not in (200, 201):
        raise SystemExit(1)

    return response.json()


def main() -> None:
    plan_id = find_plan_id()
    print("Target Plan ID:", plan_id)

    plan = read_plan(plan_id)
    updated = update_plan(plan)

    style_count = len(updated.get("properties", {}).get("styleSettings", []))

    print()
    print("Updated Delivery Plan:")
    print("Plan ID:", updated.get("id"))
    print("Revision:", updated.get("revision"))
    print("Style settings count:", style_count)


if __name__ == "__main__":
    main()
