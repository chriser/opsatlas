#!/usr/bin/env bash
# This folder is OpsAtlas Sales. The stack this script used to start is OpsAtlas Classic: compliance reasoning on
# :5310, the core API over data/ on :8010, and the control panel on :5200. Since 26 September 2026 Classic runs from
# its own folder, with its own data. See docs/opsatlas-classic-and-sales.md.
cat <<'MSG'
This folder is OpsAtlas Sales.

  Start OpsAtlas Sales:    scripts/start-tiberius-sales.sh      (http://127.0.0.1:8780)
  Start OpsAtlas Classic:  cd ~/Dev/opsatlas-classic && ./scripts/dev.sh   (http://localhost:5200)

See docs/opsatlas-classic-and-sales.md.
MSG
exit 1
