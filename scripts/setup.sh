#!/usr/bin/env bash
# One-time setup: python venv, deps, Verilator (local build), ORFS check.
set -euo pipefail
cd "$(dirname "$0")/.."
CUDA=${TORCH_CUDA:-cu128}            # cpu | cu121 | cu124 | cu128 ...
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q torch --index-url "https://download.pytorch.org/whl/${CUDA}"
.venv/bin/pip install -q -r requirements.txt
command -v verilator >/dev/null || ./scripts/install_verilator.sh
.venv/bin/python - <<'PY'
from snn2gds.pnr import orfs_home
try:
    print("ORFS:", orfs_home())
except FileNotFoundError as e:
    print("WARNING:", e)
PY
echo "setup done"
