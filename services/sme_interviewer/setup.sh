#!/bin/sh
# Explicit ONLINE provisioning; serving itself requires no downloads.
set -eu
service_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$service_dir/../.."
uv venv --python 3.12 "$service_dir/.venv"
uv pip sync --python "$service_dir/.venv/bin/python" --require-hashes "$service_dir/requirements.lock"
"$service_dir/.venv/bin/python" "$service_dir/provision.py"
"$service_dir/.venv/bin/python" -m services.sme_interviewer.benchmark --count 23
