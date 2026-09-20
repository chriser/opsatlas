#!/bin/sh
set -eu
service_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$service_dir/../.."
exec "$service_dir/.venv/bin/python" -m uvicorn services.sme_interviewer.app:app --host 127.0.0.1 --port 8767 --ws-max-size 8000000
