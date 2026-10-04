"""Every guard proven (REF F10): each guard in tests/guard_register.py, switched off, makes at least one of its tests
fail. Its tests pass with it on in the ordinary run of the suite, so together these say the tests do check the guard."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from guard_register import GUARDS

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", sorted(GUARDS))
def test_switching_the_guard_off_fails_its_tests(name):
    env = {**os.environ, "OPSATLAS_DISABLE_GUARD": name, "OPSATLAS_SCENARIO_RUNS": "300"}
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "-p", "no:warnings",
                           *GUARDS[name]["tests"]], cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    assert done.returncode == 1, f"{name}: its tests did not fail with it off (exit {done.returncode})\n{done.stdout[-1500:]}"
