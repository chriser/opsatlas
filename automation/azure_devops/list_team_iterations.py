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
TEAM = "AI Knowledge and Analytics Assistant Team"


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
    if not ORG or not PROJECT:
        raise ValueError("ADO_ORG or ADO_PROJECT_NAME missing. Check .env file.")

    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}/{quote(TEAM, safe='')}"
        f"/_apis/work/teamsettings/iterations?api-version=7.1"
    )

    response = requests.get(url, headers=get_auth_header(), timeout=30)

    print("Status:", response.status_code)

    if response.status_code != 200:
        print(response.text)
        raise SystemExit(1)

    iterations = response.json().get("value", [])

    print("Team iterations:")
    for iteration in iterations:
        attrs = iteration.get("attributes", {})
        print(
            "-",
            iteration.get("name"),
            "|",
            attrs.get("startDate"),
            "→",
            attrs.get("finishDate"),
        )


if __name__ == "__main__":
    main()
