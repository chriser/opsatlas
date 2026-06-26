from __future__ import annotations

import sys
from pathlib import Path

PARKED_ROOT = Path(__file__).resolve().parents[1]
if str(PARKED_ROOT) in sys.path:
    sys.path.remove(str(PARKED_ROOT))
sys.path.insert(0, str(PARKED_ROOT))

# The active repository also has a `services` package. For explicit parked-test
# runs, force imports to resolve against this parked namespace first.
sys.modules.pop("services", None)
