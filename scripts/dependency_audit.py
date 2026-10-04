#!/usr/bin/env python3
"""The dependency audit that can fail the build (REF S6).

Runs pip-audit over requirements.lock and fails on any known vulnerability, unless config/dependency-audit-exceptions.json
lists it with a reason and an expiry date that has not passed. An expired exception fails the build too, so an exception
is reviewed rather than forgotten. pip-audit reports no severity for most advisories, so the rule is stricter than a
severity threshold: every advisory needs a fix or a dated, reasoned exception.

    python scripts/dependency_audit.py            # what the pipeline runs (pip-audit must be installed)
    python scripts/dependency_audit.py --report r.json   # check a saved pip-audit JSON report instead
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCEPTIONS = ROOT / "config/dependency-audit-exceptions.json"


def findings(report: dict) -> list[tuple[str, str, str]]:
    return [(dep["name"], dep.get("version", ""), vuln["id"]) for dep in report.get("dependencies", [])
            for vuln in dep.get("vulns", [])]


def verdict(report: dict, exceptions: list[dict], today: date) -> list[str]:
    """The reasons the build fails; empty when it passes."""
    problems, valid = [], set()
    for item in exceptions:
        if not item.get("reason") or not item.get("expires"):
            problems.append(f"exception {item.get('id')} needs a reason and an expiry date")
        elif date.fromisoformat(item["expires"]) < today:
            problems.append(f"exception {item['id']} ({item.get('package', '?')}) expired on {item['expires']}: review it")
        else:
            valid.add(item["id"])
    for name, version, vuln in findings(report):
        if vuln not in valid:
            problems.append(f"{name} {version}: {vuln} has no fix applied and no dated exception")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", help="a saved pip-audit JSON report")
    args = parser.parse_args()
    if args.report:
        report = json.loads(Path(args.report).read_text())
    else:
        run = subprocess.run(["pip-audit", "-r", str(ROOT / "requirements.lock"), "--desc", "--format", "json"],
                             capture_output=True, text=True)
        if not run.stdout.strip():
            print(run.stderr, file=sys.stderr)
            return 2
        report = json.loads(run.stdout)
    exceptions = json.loads(EXCEPTIONS.read_text()).get("exceptions", [])
    problems = verdict(report, exceptions, date.today())
    for name, version, vuln in findings(report):
        print(f"known vulnerability: {name} {version} {vuln}")
    for problem in problems:
        print(f"FAIL: {problem}")
    print("dependency audit:", "failed" if problems else f"passed ({len(report.get('dependencies', []))} packages)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
