#!/usr/bin/env bash
# Free local texture upgrade — no OpenAI API billing.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOD_PATH="${1:-mods}"
shift || true
VENV="$ROOT/.venv-asset-upgrader"

if [[ ! -x "$VENV/bin/python3" ]]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -r "$ROOT/tools/requirements-asset-upgrader.txt"
fi

exec "$VENV/bin/python" "$ROOT/tools/asset_upgrader.py" run \
  --path "$MOD_PATH" \
  --backend local \
  --deploy-dir mods/mod_upgraded \
  --no-resume \
  "$@"
