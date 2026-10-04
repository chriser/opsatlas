"""Aliases come out in one order whatever the hash seed (AUDIT F10): case variants used to tie in a case-insensitive
sort and follow the set's order, so a facts-map line, and the prompts quoting it, changed between processes."""
import json
import os
import subprocess
import sys
from pathlib import Path

from assistant.ontology.reconciliation import alias_order, reconcile_entity_name

SRC = str(Path(__file__).resolve().parents[1] / "src")
CODE = ("import json; from assistant.ontology.reconciliation import alias_order; "
        "print(json.dumps(alias_order({'Payment contract', 'Payment Contract', 'payment contract', 'Contract'})))")


def test_case_variants_keep_one_order():
    assert alias_order(["Payment contract", "Payment Contract"]) == ["Payment Contract", "Payment contract"]
    assert alias_order(["Payment Contract", "Payment contract", "Payment Contract"]) == ["Payment Contract", "Payment contract"]
    reconciled = reconcile_entity_name("system", "Payment contract")
    assert reconciled is not None and reconciled.aliases == alias_order(reconciled.aliases)


def test_the_order_does_not_depend_on_the_hash_seed():
    orders = set()
    for seed in ("1", "2", "3", "42"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": SRC}
        out = subprocess.run([sys.executable, "-c", CODE], env=env, capture_output=True, text=True, check=True).stdout
        orders.add(tuple(json.loads(out)))
    assert orders == {("Contract", "Payment Contract", "Payment contract", "payment contract")}
