"""Shared test settings."""
import os
import tempfile

# A proposed sales claim starts a statement-level review in the background; tests never call real models.
os.environ.setdefault('SALES_GOVERNANCE_AUTO_REVIEW', '0')

# Importing assistant.api.app builds its module-level app, which syncs the ontology and process registry into
# KP_DATA_DIR. Point it at a throwaway folder before any test module is imported, so a test run never creates
# or rewrites a data/ folder in the checkout (OpsAtlas Classic keeps the old knowledge base in its own folder).
os.environ['KP_DATA_DIR'] = tempfile.mkdtemp(prefix='opsatlas-test-data-')

# Every guard proven (REF F10): tests/test_guards_proven.py runs a guard's tests with this switch, which turns the guard
# off before any test module imports the code, and requires them to fail.
if os.environ.get('OPSATLAS_DISABLE_GUARD'):
    import sys

    sys.path.insert(0, os.path.dirname(__file__))
    from guard_register import switch_off

    switch_off(os.environ['OPSATLAS_DISABLE_GUARD'])


import pytest  # noqa: E402


@pytest.fixture
def sales_workspace(tmp_path, monkeypatch):
    """A hermetic Sales app, signed in, with one organisation space; set state up with its builders (tests/builders.py)."""
    import sys

    sys.path.insert(0, os.path.dirname(__file__))
    from builders import sales_workspace as build

    with build(tmp_path, monkeypatch) as workspace:
        yield workspace
