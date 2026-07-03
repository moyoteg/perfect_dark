#!/usr/bin/env bash
# Nuclear reset: purge all uff test-map assets and rebuild from src/levels/uff.py.
#
# Usage (from repo root):
#   ./scripts/reset-uff-test-map.sh
#
# Produces tiles-only play seg (~290 B, G_VTX=0) for --test-map / LLM Play Quick test.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

log() { printf '[reset-uff] %s\n' "$*"; }
fail() { printf '[reset-uff] FAIL: %s\n' "$*" >&2; exit 1; }

log "Stopping any running pd.arm64 (seg is mmap'd at boot)"
pkill -f "${REPO_ROOT}/build/pd.arm64" 2>/dev/null || true
sleep 1

log "Purging stale bg_uff assets"
rm -f mods/mod_allinone/files/bgdata/bg_uff*
rm -f build/ntsc-final/assets/files/bgdata/bg_uff*
rm -f scripts/bg_uff.seg
rm -f src/assets/ntsc-final/tiles/uff.json

log "Rebuilding Matrix Test Room from src/levels/uff.py (PDMAP_SEG_MODE=empty)"
export PDMAP_SEG_MODE=empty
if ! python3 tools/pdmap.py build uff --deploy; then
  fail "pdmap build uff --deploy failed"
fi

log "Syncing canonical empty play seg"
if ! python3 scripts/ensure-llm-map-assets.py; then
  fail "ensure-llm-map-assets.py failed"
fi

log "Inspecting deployed assets"
INSPECT_JSON="$(python3 scripts/inspect-llm-map-seg.py)" || {
  printf '%s\n' "$INSPECT_JSON" >&2
  fail "inspect-llm-map-seg.py failed"
}
printf '%s\n' "$INSPECT_JSON"

log "On-disk sizes (mod_allinone uff slot)"
ls -la mods/mod_allinone/files/bgdata/bg_uff.seg \
  mods/mod_allinone/files/bgdata/bg_uff_tilesZ \
  mods/mod_allinone/files/bgdata/bg_uff_padsZ \
  scripts/bg_uff.seg \
  src/assets/ntsc-final/tiles/uff.json 2>/dev/null || true

if ! python3 -c "import json,sys; d=json.loads(sys.argv[1]); sys.exit(0 if d.get('emptyPlaySeg') and d.get('tilesOk') else 1)" "$INSPECT_JSON"; then
  fail "deployed seg is not empty-play tiles-only"
fi

log "SUCCESS — uff test map reset complete (empty seg + floor tiles, no face G_VTX)"
