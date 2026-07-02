#!/usr/bin/env bash
# Launch the PD Map Launcher Electron app (dev mode).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="$REPO_ROOT/tools/map-launcher-electron"
ASSETS_DIR="$APP_DIR/assets"
ICON_ICNS="$ASSETS_DIR/MapLauncherAppIcon.icns"

if [[ ! -f "$ICON_ICNS" ]]; then
	echo "Generating Map Launcher icon assets…"
	"$SCRIPT_DIR/pd-kit-icons.sh" map-launcher
	mkdir -p "$ASSETS_DIR"
	cp "$REPO_ROOT/.tmp-map-editor-app-build/MapLauncherAppIcon.icns" "$ICON_ICNS"
	cp "$REPO_ROOT/.tmp-map-editor-app-build/map-launcher-1024.png" "$ASSETS_DIR/"
fi

if [[ ! -d "$APP_DIR" ]]; then
	echo "ERROR: map launcher app not found at $APP_DIR" >&2
	exit 1
fi

if [[ ! -d "$APP_DIR/node_modules/electron" ]]; then
	echo "Installing Electron dependencies…"
	(cd "$APP_DIR" && npm install)
fi

export PD_REPO_ROOT="$REPO_ROOT"
ELECTRON_BIN="$APP_DIR/node_modules/.bin/electron"
ELECTRON_APP="$APP_DIR/node_modules/electron/dist/Electron.app"
LOG_DIR="${HOME}/Library/Logs/PerfectDarkKit"
STDIO_LOG="$LOG_DIR/map-launcher-stdio.log"
mkdir -p "$LOG_DIR"

# open(1) does not inherit shell env; bake repo root for main.js resolveRepoRoot().
printf '{"repoRoot":"%s"}\n' "$REPO_ROOT" >"$APP_DIR/repo-config.json"

if [[ ! -d "$ELECTRON_APP" ]]; then
	echo "ERROR: Electron.app not found at $ELECTRON_APP (run npm install in $APP_DIR)" >&2
	exit 1
fi

# Foreground dev mode: logs on stdout, Ctrl+C stops the app.
if [[ "${1:-}" == "--foreground" ]]; then
	exec env PD_REPO_ROOT="$REPO_ROOT" "$ELECTRON_BIN" "$APP_DIR"
fi

# macOS GUI detach: nohup/node from Terminal exits in ~5s; open(1) keeps Electron alive.
RUNNING=$(
	pgrep -f "Electron.app/Contents/MacOS/Electron.*map-launcher-electron" 2>/dev/null || true
)
if [[ -n "$RUNNING" ]]; then
	echo "PD Map Launcher already running — focusing existing window."
fi

open --env PD_REPO_ROOT="$REPO_ROOT" -a "$ELECTRON_APP" --args "$APP_DIR"
echo "PD Map Launcher opening (PD_REPO_ROOT=${REPO_ROOT}). Log: ${LOG_DIR}/map-launcher.log"
