"""REF S7: the release facts on the status page match the engine registry, the Sales profile, the routes and the
catalogue; a stale page fails here, in CI, instead of misleading a reader."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_facts", ROOT / "scripts/release_facts.py")
facts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(facts)


def test_the_status_pages_release_facts_are_current(monkeypatch):
    import os
    monkeypatch.setattr(os, "environ", os.environ.copy())
    page = (ROOT / "ARCHITECTURE_STATUS.md").read_text()
    assert facts.page_with(page, facts.block()) == page, "run: python scripts/release_facts.py --write"
