#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir/.."
export PYTHONDONTWRITEBYTECODE=1
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s static/code/sim -p 'test_*.py' -v
python3 scripts/cloud/verify-local.py
python3 scripts/build_handbook.py
python3 scripts/validate_workshop.py
if command -v cfn-lint >/dev/null 2>&1; then
  cfn-lint static/workshop.yaml static/workshop-existing-network.json
else
  echo "NOT RUN: cfn-lint is not installed; validate both static/workshop templates separately."
fi
echo "Local checks finished. No AWS deployment, Isaac Sim GPU run, or physical robot test was performed."
