#!/usr/bin/env bash
# Regenerate curriculum-manifest.json from tools/pdmap/learn/curriculum.py
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$APP_DIR/../.." && pwd)"
OUT="$APP_DIR/curriculum-manifest.json"

cd "$REPO_ROOT"
python3 - <<'PY' >"$OUT"
import json
from tools.pdmap.learn.curriculum import curriculum_steps

rows = []
for step in curriculum_steps():
    rows.append({
        "step": step.step,
        "name": step.name,
        "title": step.title,
        "expected": step.expected,
        "scenario": step.scenario,
        "segMode": step.seg_mode,
        "jsonPath": f"journal/map_learn/maps/{step.name}.json",
    })
print(json.dumps(rows, indent=2))
PY

count="$(python3 -c "import json; print(len(json.load(open('$OUT'))))")"
echo "Wrote $OUT ($count steps)"
