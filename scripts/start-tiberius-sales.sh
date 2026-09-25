#!/bin/sh
# Default: user-session background services. Use --foreground for terminal-owned processes.
set -eu
cd "$(dirname "$0")/.."
mkdir -p .runtime/opsatlas-sales-logs
export PYTHONPATH="$PWD/src:$PWD"
if [ "${1:-}" != "--foreground" ]; then
  exec .venv/bin/python -m services.opsatlas_sales.manage "${1:-start}"
fi
.venv/bin/python -c "from services.opsatlas_sales.workspace import workspace; workspace()"
started=''
stop_started() { for pid in $started; do kill "$pid" 2>/dev/null || true; done; }
trap stop_started EXIT INT TERM
if ! lsof -nP -iTCP:8780 -sTCP:LISTEN >/dev/null 2>&1; then
  .venv/bin/python -m services.opsatlas_sales.app > .runtime/opsatlas-sales-logs/core.log 2>&1 &
  started="$started $!"
fi
if ! lsof -nP -iTCP:8773 -sTCP:LISTEN >/dev/null 2>&1; then
  services/sme_interviewer/.venv/bin/python -m services.sme_interviewer.sales_preview > .runtime/opsatlas-sales-logs/voice.log 2>&1 &
  started="$started $!"
fi
.venv/bin/python - <<'PY'
import time
from pathlib import Path
import httpx
headers={'x-sales-token':Path('.runtime/opsatlas-sales/local-access.key').read_text().strip()}
with httpx.Client(trust_env=False,timeout=2) as client:
    for attempt in range(30):
        try:
            r=client.get('http://127.0.0.1:8780/api/sales/knowledge',headers=headers)
            r.raise_for_status()
            assert r.json()['workspace']=='opsatlas-sales'
            tibi=client.get('http://127.0.0.1:8773/api/health')
            tibi.raise_for_status()
            assert tibi.json()['service']=='tibi'
            break
        except (httpx.HTTPError,ValueError,AssertionError,KeyError):
            if attempt==29: raise SystemExit('Startup failed or ports belong to another service; inspect .runtime/opsatlas-sales-logs.')
            time.sleep(1)
print('OpsAtlas Sales: http://127.0.0.1:8780/\nTalk with Tibi: http://127.0.0.1:8780/#tibi\nTibi knowledge: http://127.0.0.1:8780/#tibi-knowledge')
PY
if [ -n "$started" ]; then wait; fi
