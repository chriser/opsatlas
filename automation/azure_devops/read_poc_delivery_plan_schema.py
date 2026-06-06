import base64
import json
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
PAT = os.getenv("ADO_PAT")

POC_PROJECT = "AI Assistant DevOps PoC"
POC_PLAN_ID = "22606b0c-7170-45d7-bd60-4a820fbf0e9b"


def get_auth_header() -> Dict[str, str]:
    if not PAT:
        raise ValueError("ADO_PAT is missing. Check your .env file.")

    token = base64.b64encode(f":{PAT}".encode("utf-8")).decode("utf-8")

    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def main() -> None:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(POC_PROJECT, safe='')}"
        f"/_apis/work/plans/{POC_PLAN_ID}?api-version=7.1"
    )

    response = requests.get(url, headers=get_auth_header(), timeout=30)

    print("Status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    plan = response.json()

    out_path = Path("automation/azure_devops/poc_delivery_plan_schema.json")
    out_path.write_text(json.dumps(plan, indent=2))

    print("Saved:", out_path)
    print()
    print("Plan name:", plan.get("name"))
    print("Plan type:", plan.get("type"))
    print("Revision:", plan.get("revision"))
    print()
    print("Property keys:")
    for key in plan.get("properties", {}).keys():
        print("-", key)

    print()
    print("teamBacklogMappings:")
    print(json.dumps(plan.get("properties", {}).get("teamBacklogMappings"), indent=2))

    print()
    print("cardSettings:")
    print(json.dumps(plan.get("properties", {}).get("cardSettings"), indent=2))


if __name__ == "__main__":
    main()
