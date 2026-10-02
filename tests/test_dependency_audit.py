"""REF S6: the dependency audit fails on any known vulnerability without a dated, reasoned exception."""
import importlib.util
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dependency_audit", ROOT / "scripts/dependency_audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

REPORT = {"dependencies": [{"name": "fastapi", "version": "1.0", "vulns": [{"id": "GHSA-aaaa"}]},
                           {"name": "pydantic", "version": "2.0", "vulns": []}]}
TODAY = date(2026, 10, 2)


def test_a_known_vulnerability_fails_the_build():
    assert audit.verdict(REPORT, [], TODAY) == ["fastapi 1.0: GHSA-aaaa has no fix applied and no dated exception"]
    assert audit.verdict({"dependencies": [{"name": "x", "vulns": []}]}, [], TODAY) == []


def test_a_dated_reasoned_exception_passes_until_it_expires():
    live = [{"id": "GHSA-aaaa", "package": "fastapi", "reason": "no fix released; not reachable", "expires": "2026-10-31"}]
    assert audit.verdict(REPORT, live, TODAY) == []
    expired = [{**live[0], "expires": "2026-10-01"}]
    assert "expired on 2026-10-01" in audit.verdict(REPORT, expired, TODAY)[0]
    assert "needs a reason" in audit.verdict(REPORT, [{"id": "GHSA-aaaa", "expires": "2026-12-31"}], TODAY)[0]


def test_the_exceptions_file_is_valid_and_has_no_expired_entry():
    import json
    exceptions = json.loads((ROOT / "config/dependency-audit-exceptions.json").read_text())["exceptions"]
    assert [p for p in audit.verdict({"dependencies": []}, exceptions, date.today())] == []
