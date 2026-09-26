"""Shared test settings."""
import os

# A proposed sales claim starts a statement-level review in the background; tests never call real models.
os.environ.setdefault('SALES_GOVERNANCE_AUTO_REVIEW', '0')
