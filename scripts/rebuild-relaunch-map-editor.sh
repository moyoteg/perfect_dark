#!/usr/bin/env bash
# Rebuild Perfect Dark Map Editor (Electron) and relaunch.
#
# Usage:
#   ./scripts/rebuild-relaunch-map-editor.sh
#
# Safe to invoke from Desktop shortcut — resolves repo root from this script's path.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_NAME="PD Map Editor"
WRAPPED_PATH="$REPO_ROOT/Perfect Dark Kit.app/Contents/Resources/Apps/PD Map Editor.app"
STANDALONE_PATH="$SCRIPT_DIR/release/PD Map Editor.app"
APP_PATH="$STANDALONE_PATH"

log() {
	printf '[rebuild-map-editor] %s\n' "$*"
}

fail() {
	printf '[rebuild-map-editor] FAIL: %s\n' "$*" >&2
	exit 1
}

kill_stale_processes() {
	log "Stopping stale Map Editor process (if running)"
	if command -v osascript >/dev/null 2>&1; then
		osascript -e "quit app \"${APP_NAME}\"" >/dev/null 2>&1 || true
		osascript -e 'quit app "Perfect Dark Map Editor"' >/dev/null 2>&1 || true
	fi
	pkill -9 -f "${APP_NAME}" 2>/dev/null || true
	pkill -9 -f "Perfect Dark Kit" 2>/dev/null || true
	pkill -9 -f "serve_editor.py" 2>/dev/null || true
	sleep 1
}

main() {
	cd "$REPO_ROOT"
	log "Repo: $REPO_ROOT"

	kill_stale_processes

	log "Regenerating uff_map.html …"
	if ! python3 "$REPO_ROOT/journal/uff_viewer/gen_uff_viewer.py"; then
		fail "gen_uff_viewer.py exited with an error"
	fi

	log "Building Map Editor.app (this may take a minute) …"
	if ! "$SCRIPT_DIR/build-map-editor-electron.sh" --no-symlink; then
		fail "build-map-editor-electron.sh exited with an error"
	fi

	# If the hub exists, we must sync the newly built standalone editor into the hub and prune standalone copies
	if [[ -d "$REPO_ROOT/Perfect Dark Kit.app" ]]; then
		# Source pd-kit-common.sh for path resolution and sync helper
		source "$SCRIPT_DIR/pd-kit-common.sh"
		kit_sync_wrapped_app "PD Map Editor.app"
		kit_prune_standalone_release_apps
		APP_PATH="$WRAPPED_PATH"
	else
		APP_PATH="$STANDALONE_PATH"
	fi

	if [[ ! -d "$APP_PATH" ]]; then
		fail "Expected app not found: $APP_PATH"
	fi

	log "Launching: $APP_PATH"
	if ! open "$APP_PATH"; then
		fail "open failed for $APP_PATH"
	fi

	log "SUCCESS — Map Editor rebuilt and launched."
}

main "$@"
