#!/usr/bin/env bash
# Build Virtual Agent Office macOS .app bundle.
#
# Outputs:
#   scripts/release/Virtual Agent Office.app
#
# Usage:
#   ./scripts/build-agent-office-electron.sh
#   ./scripts/build-agent-office-electron.sh --dev
#   ./scripts/build-agent-office-electron.sh --no-symlink
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pd-kit-common.sh
source "$SCRIPT_DIR/pd-kit-common.sh"
REPO_ROOT="$PD_KIT_REPO_ROOT"
ELECTRON_DIR="$REPO_ROOT/tools/agent-office-electron"
RELEASE_DIR="$PD_KIT_RELEASE_DIR"
APP_NAME="Virtual Agent Office"
APP_BUNDLE="$RELEASE_DIR/${APP_NAME}.app"
BUILD_DIR="$REPO_ROOT/.tmp-map-editor-app-build"
SYMLINK_AT_ROOT=1
DEV_ONLY=0

while [[ $# -gt 0 ]]; do
	case "$1" in
	--no-symlink) SYMLINK_AT_ROOT=0; shift ;;
	--dev) DEV_ONLY=1; shift ;;
	-h | --help)
		echo "Usage: $0 [--no-symlink] [--dev]"
		exit 0
		;;
	*)
		echo "Unknown option: $1" >&2
		exit 2
		;;
	esac
done

write_repo_config() {
	printf '{"repoRoot": "%s"}\n' "$REPO_ROOT" >"$ELECTRON_DIR/repo-config.json"
}

prepare_icon() {
	"$SCRIPT_DIR/pd-kit-icons.sh" agent-office
	mkdir -p "$ELECTRON_DIR/build" "$ELECTRON_DIR/assets"
	cp "$BUILD_DIR/AgentOfficeAppIcon.icns" "$ELECTRON_DIR/build/icon.icns"
	cp "$BUILD_DIR/AgentOfficeAppIcon.icns" "$ELECTRON_DIR/assets/AgentOfficeAppIcon.icns"
	cp "$BUILD_DIR/agent-office-1024.png" "$ELECTRON_DIR/assets/agent-office-1024.png"
}

install_built_app() {
	local out_dir
	out_dir="$(cd "$ELECTRON_DIR" && node -p "require('./package.json').build.directories.output" 2>/dev/null || echo '../../scripts/release/agent-office-dist')"
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
	rm -rf "$APP_BUNDLE"
	cp -R "$built" "$APP_BUNDLE"

	mkdir -p "$APP_BUNDLE/Contents/Resources"
	printf '%s\n' "$REPO_ROOT" >"$APP_BUNDLE/Contents/Resources/repo_root.txt"
	cp "$ELECTRON_DIR/repo-config.json" "$APP_BUNDLE/Contents/Resources/repo-config.json" 2>/dev/null || true

	if command -v codesign >/dev/null 2>&1; then
		xattr -cr "$APP_BUNDLE" 2>/dev/null || true
		codesign --force --deep --sign - "$APP_BUNDLE" 2>&1 || true
	fi
}

main() {
	if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
		echo "Node.js and npm are required." >&2
		exit 1
	fi

	write_repo_config
	prepare_icon

	cd "$ELECTRON_DIR"
	echo "Installing npm dependencies in $ELECTRON_DIR ..."
	npm install

	if [[ "$DEV_ONLY" -eq 1 ]]; then
		echo "Dev mode: cd tools/agent-office-electron && PD_REPO_ROOT=\"$REPO_ROOT\" npm start"
		exit 0
	fi

	echo "Building ${APP_NAME}.app with electron-builder ..."
	npm run build
	install_built_app

	rm -f "$REPO_ROOT/${APP_NAME}.app"
	if [[ "$SYMLINK_AT_ROOT" -eq 1 ]]; then
		kit_symlink_app "${APP_NAME}.app"
	fi

	printf '\nBuilt Virtual Agent Office app:\n  %s\n' "$APP_BUNDLE"
	if [[ "$SYMLINK_AT_ROOT" -eq 1 ]]; then
		printf '  %s -> %s\n' "$REPO_ROOT/${APP_NAME}.app" "$APP_BUNDLE"
	fi
	printf '\nQuick dev: ./scripts/launch-agent-office-app.sh\n'
}

main "$@"
