#!/usr/bin/env bash
# Release QA smoke checks for Perfect Dark Kit (SPEC V-1..V-4 subset).
#
# Usage:
#   ./scripts/kit-smoke.sh              # hub log + health endpoints only
#   ./scripts/kit-smoke.sh --launch   # also open Anim Lab .app (macOS)
#
# Exit 0 when all gates pass; non-zero on first failure.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pd-kit-common.sh
source "$SCRIPT_DIR/pd-kit-common.sh"

LAUNCH=0
while [[ $# -gt 0 ]]; do
	case "$1" in
	--launch) LAUNCH=1; shift ;;
	-h | --help)
		echo "Usage: $0 [--launch]"
		exit 0
		;;
	*) echo "Unknown option: $1" >&2; exit 2 ;;
	esac
done

LOG_ROOT="${HOME}/Library/Logs/PerfectDarkKit"
HUB_LOG="${LOG_ROOT}/kit-hub.log"
ANIM_LOG="${LOG_ROOT}/anim-lab.log"
HUB_APP="${PD_KIT_REPO_ROOT}/${PD_KIT_APP_HUB}"
ANIM_APP="${PD_KIT_REPO_ROOT}/${PD_KIT_APP_HUB}/Contents/Resources/Apps/${PD_KIT_APP_ANIM_LAB}"

fail() {
	echo "FAIL: $*" >&2
	exit 1
}

pass() {
	echo "PASS: $*"
}

[[ -d "$HUB_APP" ]] || fail "Hub not built: $HUB_APP (run ./scripts/build-pd-kit.sh --apps-only)"

python3 - "$PD_KIT_REPO_ROOT" <<'PY'
import json
import sys
from pathlib import Path

repo = Path(sys.argv[1])
sys.path.insert(0, str(repo))
from tools.pd_kit.hub_surface import validate_kit_hub_manifest

manifest = json.loads((repo / "tools" / "pd_kit" / "kit.json").read_text(encoding="utf-8"))
violations = validate_kit_hub_manifest(manifest)
if violations:
    print("FAIL: kit.json hub invariants:", "; ".join(violations), file=sys.stderr)
    sys.exit(1)
print("PASS: kit.json hub invariants")
PY

node "$PD_KIT_REPO_ROOT/tests/test_kit_launch_policy.js" || fail "Kit launch policy tests failed"

node "$PD_KIT_REPO_ROOT/tests/test_kit_get_info_invariants.js" || fail "Kit get-info invariant tests failed"

node "$PD_KIT_REPO_ROOT/tests/test_kit_game_action_policy.js" || fail "Kit game/action policy tests failed"

if [[ -f "$HUB_LOG" ]] && grep -qi 'Unhandled rejection' "$HUB_LOG" 2>/dev/null; then
	fail "Unhandled rejection in $HUB_LOG"
fi
pass "No unhandled rejection in hub log (if log exists)"

if [[ "$LAUNCH" -eq 1 ]]; then
	[[ -d "$ANIM_APP" ]] || fail "Anim Lab not built: $ANIM_APP"
	before=0
	if [[ -f "$ANIM_LOG" ]]; then
		before="$(grep -c 'electron anim-lab start' "$ANIM_LOG" 2>/dev/null || true)"
	fi
	open "$ANIM_APP"
	sleep 8
	after=0
	if [[ -f "$ANIM_LOG" ]]; then
		after="$(grep -c 'electron anim-lab start' "$ANIM_LOG" 2>/dev/null || true)"
	fi
	delta=$((after - before))
	[[ "$delta" -le 1 ]] || fail "Expected ≤1 new anim-lab start marker; got +$delta"
	pass "Anim Lab bootstrap markers +$delta"
fi

# Health scan: any anim-lab / uff-editor server on canonical port ranges.
python3 - <<'PY'
import json
import sys
import urllib.error
import urllib.request

def probe(port, service):
    url = f"http://127.0.0.1:{port}/api/health"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            data = json.loads(resp.read().decode())
        return data.get("ok") is True and data.get("service") == service
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return False

anim = any(probe(p, "anim-lab") for p in range(8776, 8796))
editor = any(probe(p, "uff-editor") for p in range(8765, 8776))
if not anim and not editor:
    print("WARN: no local anim-lab or uff-editor health endpoint (start apps first)", file=sys.stderr)
else:
    if anim:
        print("PASS: anim-lab /api/health reachable")
    if editor:
        print("PASS: uff-editor /api/health reachable")
PY

pass "kit-smoke completed"
