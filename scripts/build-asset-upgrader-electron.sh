#!/usr/bin/env bash
# Build the Electron-based Perfect Dark Kit Asset Upgrader macOS .app bundle.
#
# Outputs:
#   scripts/release/Perfect Dark Kit — Asset Upgrader.app
#
# Usage:
#   ./scripts/build-asset-upgrader-electron.sh --build [--no-symlink]
#   ./scripts/build-asset-upgrader-electron.sh --run

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pd-kit-common.sh
source "$SCRIPT_DIR/pd-kit-common.sh"
ROOT="$PD_KIT_REPO_ROOT"
ELECTRON_DIR="$ROOT/tools/asset_upgrader/electron"
VENV="$ROOT/.venv-asset-upgrader"
RELEASE_DIR="$PD_KIT_RELEASE_DIR"
APP_NAME="${PD_KIT_APP_ASSET_UPGRADER%.app}"
APP_BUNDLE="$RELEASE_DIR/${APP_NAME}.app"
SYMLINK_AT_ROOT=1

while [[ $# -gt 0 ]]; do
	case "$1" in
	--no-symlink)
		SYMLINK_AT_ROOT=0
		shift
		;;
	--build | --run)
		MODE="${1#--}"
		shift
		;;
	-h | --help)
		echo "Usage: $0 [--build|--run] [--no-symlink]"
		exit 0
		;;
	*)
		echo "Unknown option: $1" >&2
		exit 2
		;;
	esac
done

MODE="${MODE:-build}"

echo "==> Ensuring Python venv for asset upgrader"
if [[ ! -x "$VENV/bin/python3" ]]; then
	python3 -m venv "$VENV"
	"$VENV/bin/pip" install -r "$ROOT/tools/requirements-asset-upgrader.txt"
fi

echo "==> Baking repo root into Electron config"
python3 - <<PY
import json, pathlib
root = pathlib.Path("$ROOT").resolve()
cfg_path = root / "tools/asset_upgrader/electron/repo-config.json"
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
cfg["repoRoot"] = str(root)
cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
PY

echo "==> Installing Electron dependencies"
(cd "$ELECTRON_DIR" && npm install)

install_built_app() {
	local out_dir
	out_dir="$(cd "$ELECTRON_DIR" && node -p "require('./package.json').build.directories.output" 2>/dev/null || echo '../../../scripts/release/asset-upgrader-electron-dist')"
	out_dir="$(cd "$ELECTRON_DIR" && cd "$out_dir" && pwd)"

	local built=""
	if [[ -d "$out_dir/mac" ]]; then
		built="$(find "$out_dir/mac" -maxdepth 1 -name '*.app' -print -quit 2>/dev/null || true)"
	fi
	if [[ -z "$built" && -d "$out_dir" ]]; then
		built="$(find "$out_dir" -maxdepth 2 -name '*.app' -print -quit 2>/dev/null || true)"
	fi
	if [[ -z "$built" || ! -d "$built" ]]; then
		echo "electron-builder did not produce a .app under $out_dir" >&2
		exit 1
	fi

	mkdir -p "$RELEASE_DIR"
	rm -rf "$APP_BUNDLE" "$RELEASE_DIR/PD Asset Upgrader.app"
	cp -R "$built" "$APP_BUNDLE"

	mkdir -p "$APP_BUNDLE/Contents/Resources"
	printf '%s\n' "$ROOT" >"$APP_BUNDLE/Contents/Resources/repo_root.txt"
	cp "$ELECTRON_DIR/repo-config.json" "$APP_BUNDLE/Contents/Resources/repo-config.json" 2>/dev/null || true

	if command -v codesign >/dev/null 2>&1; then
		xattr -cr "$APP_BUNDLE" 2>/dev/null || true
		codesign --force --deep --sign - "$APP_BUNDLE" 2>&1 || true
	fi
}

if [[ "$MODE" == "run" ]]; then
	echo "==> Launching supervisor"
	(cd "$ELECTRON_DIR" && npm start)
	exit 0
fi

echo "==> Building macOS .app with electron-builder"
(cd "$ELECTRON_DIR" && npm run build)
install_built_app

rm -f "$ROOT/PD Asset Upgrader.app"
if [[ "$SYMLINK_AT_ROOT" -eq 1 ]]; then
	kit_symlink_app "${APP_NAME}.app"
fi

printf '\nBuilt Asset Upgrader app:\n  %s\n' "$APP_BUNDLE"
if [[ "$SYMLINK_AT_ROOT" -eq 1 ]]; then
	printf '  %s -> %s\n' "$ROOT/${APP_NAME}.app" "$APP_BUNDLE"
fi
