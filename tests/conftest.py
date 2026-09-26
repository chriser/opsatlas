"""Shared test settings."""
import os
import tempfile

# A proposed sales claim starts a statement-level review in the background; tests never call real models.
os.environ.setdefault('SALES_GOVERNANCE_AUTO_REVIEW', '0')

# Importing assistant.api.app builds its module-level app, which syncs the ontology and process registry into
# KP_DATA_DIR. Point it at a throwaway folder before any test module is imported, so a test run never creates
# or rewrites a data/ folder in the checkout (OpsAtlas Classic keeps the old knowledge base in its own folder).
os.environ['KP_DATA_DIR'] = tempfile.mkdtemp(prefix='opsatlas-test-data-')
