#!/usr/bin/env bash
# One-time / occasional setup: venv, deps, optional API key provisioning, Electron deps.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv-asset-upgrader"
ENV_FILE="$ROOT/work/asset_upgrader/.env"
PROVISION=0

for arg in "$@"; do
  case "$arg" in
    --provision-key) PROVISION=1 ;;
  esac
done

echo "==> Python venv + packages"
if [[ ! -x "$VENV/bin/python3" ]]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install -q -r "$ROOT/tools/requirements-asset-upgrader.txt"

mkdir -p "$ROOT/work/asset_upgrader"

if [[ -n "${OPENAI_API_KEY:-}" && ! -f "$ENV_FILE" ]]; then
  echo "OPENAI_API_KEY=${OPENAI_API_KEY}" > "$ENV_FILE"
  echo "==> Saved existing OPENAI_API_KEY to work/asset_upgrader/.env"
fi

if [[ "$PROVISION" -eq 1 ]]; then
  if [[ -z "${OPENAI_ADMIN_KEY:-}" ]]; then
    echo "OPENAI_ADMIN_KEY is required for --provision-key (org admin key from platform.openai.com)." >&2
    exit 1
  fi
  if ! command -v openai >/dev/null 2>&1; then
    echo "==> Installing OpenAI CLI (npm)"
    npm install -g @openai/cli
  fi
  echo "==> Creating project service account + API key"
  PROJECT_JSON="$(mktemp)"
  SA_JSON="$(mktemp)"
  openai admin:organization:projects create --name "pd-asset-upgrader" --format json > "$PROJECT_JSON"
  PROJECT_ID="$(python3 -c "import json; print(json.load(open('$PROJECT_JSON'))['id'])")"
  openai admin:organization:projects:service-accounts create \
    --project-id "$PROJECT_ID" \
    --name "pd-upgrader-bot" \
    --format json > "$SA_JSON"
  python3 - <<PY
import json, pathlib
data = json.load(open("$SA_JSON"))
key = data["api_key"]["value"]
path = pathlib.Path("$ENV_FILE")
path.write_text(f"OPENAI_API_KEY={key}\n")
print(f"==> Wrote new API key to {path}")
PY
  rm -f "$PROJECT_JSON" "$SA_JSON"
fi

echo "==> Validating OpenAI key"
if ! "$VENV/bin/python" "$ROOT/tools/asset_upgrader.py" snapshot >/dev/null 2>&1; then
  :
fi
if "$VENV/bin/python" - <<PY
from pathlib import Path
from tools.asset_upgrader.auth import ensure_openai_key, validate_openai_key
import sys
sys.path.insert(0, "$ROOT")
try:
    key = ensure_openai_key(Path("$ROOT/work/asset_upgrader"))
    validate_openai_key(key)
    print("OpenAI key OK")
except Exception as e:
    print(e, file=sys.stderr)
    raise SystemExit(1)
PY
then
  echo "==> Auth OK"
else
  echo ""
  echo "No valid API key yet. OpenAI cannot mint billing keys without an account."
  echo "Create one at https://platform.openai.com/api-keys then either:"
  echo "  export OPENAI_API_KEY=sk-..."
  echo "  or paste into $ENV_FILE"
  echo ""
  echo "Or re-run with OPENAI_ADMIN_KEY set: $0 --provision-key"
  exit 1
fi

echo "==> Electron deps"
"$ROOT/scripts/build-asset-upgrader-electron.sh"
echo "Setup complete."
