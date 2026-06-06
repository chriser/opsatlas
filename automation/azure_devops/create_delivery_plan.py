import base64
import os
from pathlib import Path
from typing import Dict
from urllib.parse import quote

import requests


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
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


def get_default_team() -> Dict:
    url = f"https://dev.azure.com/{ORG}/_apis/projects/{quote(PROJECT, safe='')}/teams?api-version=7.1"

    response = requests.get(url, headers=get_auth_header(), timeout=30)

    print("Get teams status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    teams = response.json().get("value", [])

    if not teams:
        raise RuntimeError("No team found for project.")

    return teams[0]


def list_plans() -> Dict:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/work/plans?api-version=7.1"
    )

    response = requests.get(url, headers=get_auth_header(), timeout=30)

    print("List plans status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    for plan in response.json().get("value", []):
        if plan.get("name") == PLAN_NAME:
            return plan

    return {}


def create_plan(team: Dict) -> Dict:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/work/plans?api-version=7.1"
    )

    team_id = team["id"]
    team_name = team["name"]

    payload = {
        "name": PLAN_NAME,
        "type": "deliveryTimelineView",
        "description": (
            "Delivery roadmap for the DT602/DT603 AI Knowledge and Analytics Assistant proof of concept. "
            "The plan shows User Stories, Features and Epics across the planned sprint timeline."
        ),
        "properties": {
            "teamBacklogMappings": [
                {
                    "teamId": team_id,
                    "categoryReferenceName": "Microsoft.RequirementCategory"
                },
                {
                    "teamId": team_id,
                    "categoryReferenceName": "Microsoft.FeatureCategory"
                },
                {
                    "teamId": team_id,
                    "categoryReferenceName": "Microsoft.EpicCategory"
                }
            ],
            "cardSettings": {
                "fields": {
                    "showId": False,
                    "showAssignedTo": True,
                    "assignedToDisplayFormat": "avatarAndFullName",
                    "showState": True,
                    "showTags": True,
                    "showParent": False,
                    "showEmptyFields": False,
                    "showChildRollup": False,
                    "additionalFields": None,
                    "coreFields": [
                        {
                            "referenceName": "System.AssignedTo",
                            "displayName": "Assigned To",
                            "fieldType": "string",
                            "isIdentity": True
                        },
                        {
                            "referenceName": "System.State",
                            "displayName": "State",
                            "fieldType": "string",
                            "isIdentity": False
                        },
                        {
                            "referenceName": "System.Tags",
                            "displayName": "Tags",
                            "fieldType": "plainText",
                            "isIdentity": False
                        }
                    ]
                }
            },
            "styleSettings": [],
            "tagStyleSettings": []
        }
    }

    print("Creating Delivery Plan for team:", team_name)

    response = requests.post(
        url,
        headers=get_auth_header(),
        json=payload,
        timeout=30,
    )

    print("Create plan status:", response.status_code)
    print(response.text)

    if response.status_code not in (200, 201):
        raise SystemExit(1)

    return response.json()


def main() -> None:
    if not ORG or not PROJECT:
        raise ValueError("ADO_ORG or ADO_PROJECT_NAME missing. Check .env file.")

    existing = list_plans()

    if existing:
        print("Delivery Plan already exists.")
        print("Plan ID:", existing.get("id"))
        print("Plan name:", existing.get("name"))
        return

    team = get_default_team()
    plan = create_plan(team)

    print()
    print("Delivery Plan created successfully.")
    print("Plan ID:", plan.get("id"))
    print("Plan name:", plan.get("name"))


if __name__ == "__main__":
    main()
