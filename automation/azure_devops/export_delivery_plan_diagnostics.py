import base64
import json
import os
from pathlib import Path
from typing import Dict, List, Set
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

OUT_DIR = Path("automation/azure_devops/diagnostics")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def get_auth_header(content_type: str = "application/json") -> Dict[str, str]:
    if not PAT:
        raise ValueError("ADO_PAT is missing. Check your .env file.")

    token = base64.b64encode(f":{PAT}".encode("utf-8")).decode("utf-8")

    return {
        "Authorization": f"Basic {token}",
        "Content-Type": content_type,
        "Accept": "application/json",
    }


def request_get(url: str) -> Dict:
    response = requests.get(url, headers=get_auth_header(), timeout=30)

    if response.status_code != 200:
        raise RuntimeError(
            f"GET failed.\nURL: {url}\nStatus: {response.status_code}\nResponse: {response.text}"
        )

    return response.json()


def request_post(url: str, payload: Dict) -> Dict:
    response = requests.post(url, headers=get_auth_header(), json=payload, timeout=30)

    if response.status_code != 200:
        raise RuntimeError(
            f"POST failed.\nURL: {url}\nStatus: {response.status_code}\nResponse: {response.text}"
        )

    return response.json()


def find_plan() -> Dict:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/work/plans?api-version=7.1"
    )

    plans = request_get(url).get("value", [])

    for plan in plans:
        if plan.get("name") == PLAN_NAME:
            return plan

    available = [(p.get("name"), p.get("id")) for p in plans]
    raise RuntimeError(f"Plan not found: {PLAN_NAME}. Available plans: {available}")


def read_plan(plan_id: str) -> Dict:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/work/plans/{plan_id}?api-version=7.1"
    )

    return request_get(url)


def get_iteration_dates() -> Dict[str, Dict]:
    url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/classificationnodes/iterations?$depth=5&api-version=7.1"
    )

    root = request_get(url)
    result: Dict[str, Dict] = {}

    def walk(node: Dict, prefix: str = "") -> None:
        name = node.get("name")
        path = f"{prefix}\\{name}" if prefix else name

        attrs = node.get("attributes", {})
        result[path] = {
            "name": name,
            "path": path,
            "startDate": attrs.get("startDate"),
            "finishDate": attrs.get("finishDate"),
            "identifier": node.get("identifier"),
        }

        for child in node.get("children", []):
            walk(child, path)

    walk(root)
    return result


def get_all_relevant_work_item_ids() -> List[int]:
    wiql_url = (
        f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
        f"/_apis/wit/wiql?api-version=7.1"
    )

    query = {
        "query": f"""
        SELECT [System.Id]
        FROM WorkItems
        WHERE [System.TeamProject] = '{PROJECT}'
        AND [System.WorkItemType] IN ('Epic', 'Feature', 'User Story', 'Task', 'Test Case')
        ORDER BY [System.Id]
        """
    }

    result = request_post(wiql_url, query)
    return [item["id"] for item in result.get("workItems", [])]


def get_work_items(ids: List[int]) -> List[Dict]:
    if not ids:
        return []

    all_items: List[Dict] = []

    # Azure DevOps can be awkward with long ID lists, so batch safely.
    batch_size = 100
    for start in range(0, len(ids), batch_size):
        batch = ids[start:start + batch_size]
        ids_text = ",".join(str(i) for i in batch)

        url = (
            f"https://dev.azure.com/{ORG}/{quote(PROJECT, safe='')}"
            f"/_apis/wit/workitems?ids={ids_text}&$expand=relations&api-version=7.1"
        )

        result = request_get(url)
        all_items.extend(result.get("value", []))

    return all_items


def extract_relation_ids(item: Dict) -> Dict[str, List[int]]:
    relations = {
        "parents": [],
        "children": [],
        "successors": [],
        "predecessors": [],
        "related": [],
        "other": [],
    }

    for rel in item.get("relations", []):
        rel_type = rel.get("rel")
        url = rel.get("url", "")
        try:
            target_id = int(url.rstrip("/").split("/")[-1])
        except ValueError:
            continue

        if rel_type == "System.LinkTypes.Hierarchy-Reverse":
            relations["parents"].append(target_id)
        elif rel_type == "System.LinkTypes.Hierarchy-Forward":
            relations["children"].append(target_id)
        elif rel_type == "System.LinkTypes.Dependency-Forward":
            relations["successors"].append(target_id)
        elif rel_type == "System.LinkTypes.Dependency-Reverse":
            relations["predecessors"].append(target_id)
        elif rel_type == "System.LinkTypes.Related":
            relations["related"].append(target_id)
        else:
            relations["other"].append(target_id)

    return relations


def simplify_work_items(items: List[Dict], iteration_dates: Dict[str, Dict]) -> List[Dict]:
    simplified = []

    for item in items:
        fields = item.get("fields", {})
        iteration_path = fields.get("System.IterationPath")

        iteration_info = iteration_dates.get(iteration_path, {})

        simplified.append(
            {
                "id": item.get("id"),
                "type": fields.get("System.WorkItemType"),
                "title": fields.get("System.Title"),
                "state": fields.get("System.State"),
                "iterationPath": iteration_path,
                "iterationStartDate": iteration_info.get("startDate"),
                "iterationFinishDate": iteration_info.get("finishDate"),
                "areaPath": fields.get("System.AreaPath"),
                "tags": fields.get("System.Tags"),
                "businessValue": fields.get("Microsoft.VSTS.Common.BusinessValue"),
                "relations": extract_relation_ids(item),
                "url": item.get("url"),
            }
        )

    return simplified


def build_dependency_analysis(items: List[Dict]) -> List[Dict]:
    by_id = {item["id"]: item for item in items}
    dependency_rows = []

    for item in items:
        for successor_id in item["relations"]["successors"]:
            successor = by_id.get(successor_id)

            if not successor:
                dependency_rows.append(
                    {
                        "sourceId": item["id"],
                        "sourceTitle": item["title"],
                        "sourceType": item["type"],
                        "sourceFinishDate": item["iterationFinishDate"],
                        "targetId": successor_id,
                        "targetTitle": "UNKNOWN / not in fetched set",
                        "targetType": None,
                        "targetStartDate": None,
                        "targetFinishDate": None,
                        "status": "Target not found in exported work item set",
                    }
                )
                continue

            source_finish = item["iterationFinishDate"]
            target_finish = successor["iterationFinishDate"]
            target_start = successor["iterationStartDate"]

            status = "OK"

            if source_finish and target_finish and source_finish > target_finish:
                status = "WARNING: predecessor iteration finishes after successor iteration finishes"
            elif source_finish and target_start and source_finish > target_start:
                status = "NOTE: predecessor overlaps successor start"

            dependency_rows.append(
                {
                    "sourceId": item["id"],
                    "sourceTitle": item["title"],
                    "sourceType": item["type"],
                    "sourceIterationPath": item["iterationPath"],
                    "sourceFinishDate": source_finish,
                    "targetId": successor["id"],
                    "targetTitle": successor["title"],
                    "targetType": successor["type"],
                    "targetIterationPath": successor["iterationPath"],
                    "targetStartDate": target_start,
                    "targetFinishDate": target_finish,
                    "status": status,
                }
            )

    return dependency_rows


def build_parent_child_summary(items: List[Dict]) -> List[Dict]:
    by_id = {item["id"]: item for item in items}
    rows = []

    for item in items:
        for child_id in item["relations"]["children"]:
            child = by_id.get(child_id)
            rows.append(
                {
                    "parentId": item["id"],
                    "parentTitle": item["title"],
                    "parentType": item["type"],
                    "parentIterationPath": item["iterationPath"],
                    "parentFinishDate": item["iterationFinishDate"],
                    "childId": child_id,
                    "childTitle": child["title"] if child else "UNKNOWN / not in fetched set",
                    "childType": child["type"] if child else None,
                    "childIterationPath": child["iterationPath"] if child else None,
                    "childFinishDate": child["iterationFinishDate"] if child else None,
                }
            )

    return rows


def main() -> None:
    if not ORG or not PROJECT:
        raise ValueError("ADO_ORG or ADO_PROJECT_NAME missing. Check .env file.")

    plan_summary = find_plan()
    plan = read_plan(plan_summary["id"])

    iteration_dates = get_iteration_dates()
    work_item_ids = get_all_relevant_work_item_ids()
    raw_work_items = get_work_items(work_item_ids)
    simplified_items = simplify_work_items(raw_work_items, iteration_dates)

    dependency_analysis = build_dependency_analysis(simplified_items)
    parent_child_summary = build_parent_child_summary(simplified_items)

    export = {
        "project": PROJECT,
        "plan": plan,
        "iterationDates": iteration_dates,
        "workItems": simplified_items,
        "dependencyAnalysis": dependency_analysis,
        "parentChildSummary": parent_child_summary,
    }

    export_path = OUT_DIR / "delivery_plan_diagnostics.json"
    export_path.write_text(json.dumps(export, indent=2))

    plan_path = OUT_DIR / "delivery_plan_raw.json"
    plan_path.write_text(json.dumps(plan, indent=2))

    work_items_path = OUT_DIR / "delivery_plan_work_items.json"
    work_items_path.write_text(json.dumps(simplified_items, indent=2))

    dependencies_path = OUT_DIR / "delivery_plan_dependencies.json"
    dependencies_path.write_text(json.dumps(dependency_analysis, indent=2))

    print("Diagnostics export completed.")
    print("Plan ID:", plan.get("id"))
    print("Plan name:", plan.get("name"))
    print("Plan revision:", plan.get("revision"))
    print("Work items exported:", len(simplified_items))
    print("Dependencies found:", len(dependency_analysis))
    print()
    print("Files created:")
    print("-", export_path)
    print("-", plan_path)
    print("-", work_items_path)
    print("-", dependencies_path)

    print()
    print("Dependency analysis:")
    if not dependency_analysis:
        print("No dependency links found.")
    else:
        for row in dependency_analysis:
            print(
                f"- {row['sourceId']} {row['sourceTitle']} "
                f"→ {row['targetId']} {row['targetTitle']} | {row['status']}"
            )


if __name__ == "__main__":
    main()
