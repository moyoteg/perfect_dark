#!/usr/bin/env bash
# Launch Virtual Agent Office Electron app (dev mode).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pd-kit-common.sh
source "$SCRIPT_DIR/pd-kit-common.sh"
REPO_ROOT="$PD_KIT_REPO_ROOT"
APP_DIR="$REPO_ROOT/tools/agent-office-electron"
ASSETS_DIR="$APP_DIR/assets"
ICON_ICNS="$ASSETS_DIR/AgentOfficeAppIcon.icns"
BUILD_DIR="$REPO_ROOT/.tmp-map-editor-app-build"

if [[ ! -f "$ICON_ICNS" ]]; then
	echo "Generating Virtual Agent Office icon assets…"
	"$SCRIPT_DIR/pd-kit-icons.sh" agent-office
	mkdir -p "$ASSETS_DIR" "$APP_DIR/build"
	cp "$BUILD_DIR/AgentOfficeAppIcon.icns" "$ICON_ICNS"
	cp "$BUILD_DIR/agent-office-1024.png" "$ASSETS_DIR/"
	cp "$BUILD_DIR/AgentOfficeAppIcon.icns" "$APP_DIR/build/icon.icns"
fi

if [[ ! -d "$APP_DIR/node_modules/electron" ]]; then
	echo "Installing Electron dependencies…"
	(cd "$APP_DIR" && npm install)
fi

export PD_REPO_ROOT="$REPO_ROOT"
printf '{"repoRoot":"%s"}\n' "$REPO_ROOT" >"$APP_DIR/repo-config.json"

ELECTRON_BIN="$APP_DIR/node_modules/.bin/electron"
ELECTRON_APP="$APP_DIR/node_modules/electron/dist/Electron.app"

if [[ ! -d "$ELECTRON_APP" ]]; then
	echo "ERROR: Electron.app not found (run npm install in $APP_DIR)" >&2
	exit 1
fi

if [[ "${1:-}" == "--foreground" ]]; then
	exec env PD_REPO_ROOT="$REPO_ROOT" "$ELECTRON_BIN" "$APP_DIR"
fi

open --env PD_REPO_ROOT="$REPO_ROOT" -a "$ELECTRON_APP" --args "$APP_DIR"
echo "Virtual Agent Office opening (PD_REPO_ROOT=${REPO_ROOT})."
