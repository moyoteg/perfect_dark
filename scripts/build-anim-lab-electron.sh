#!/usr/bin/env bash
# Build the Electron-based Perfect Dark Animation Lab macOS .app bundle.
#
# Outputs:
#   scripts/release/PD Anim Lab.app
#
# Usage:
#   ./scripts/build-anim-lab-electron.sh              # builds + repo-root symlink
#   ./scripts/build-anim-lab-electron.sh --no-symlink # build only
#   ./scripts/build-anim-lab-electron.sh --dev        # npm start only (no .app)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pd-kit-common.sh
source "$SCRIPT_DIR/pd-kit-common.sh"
REPO_ROOT="$PD_KIT_REPO_ROOT"
ELECTRON_DIR="$REPO_ROOT/journal/anim_lab/electron"
LAB_DIR="$REPO_ROOT/journal/anim_lab"
BUNDLE_STAGING="$ELECTRON_DIR/anim-lab-bundle"
RELEASE_DIR="$PD_KIT_RELEASE_DIR"
APP_NAME="${PD_KIT_APP_ANIM_LAB%.app}"
APP_BUNDLE="$RELEASE_DIR/${APP_NAME}.app"
LEGACY_APP_BUNDLE="$RELEASE_DIR/Perfect Dark Animation Lab.app"
BUILD_DIR="$REPO_ROOT/.tmp-map-editor-app-build"
SYMLINK_AT_ROOT=1
DEV_ONLY=0

LAB_BUNDLE_FILES=(
	serve_animlab.py
	anim_lab.html
)

while [[ $# -gt 0 ]]; do
	case "$1" in
	--no-symlink)
		SYMLINK_AT_ROOT=0
		shift
		;;
	--dev)
		DEV_ONLY=1
		shift
		;;
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

prepare_lab_bundle() {
	echo "Staging anim-lab bundle for Contents/Resources/anim-lab/ ..."
	rm -rf "$BUNDLE_STAGING"
	mkdir -p "$BUNDLE_STAGING"
	local f
	for f in "${LAB_BUNDLE_FILES[@]}"; do
		if [[ ! -f "$LAB_DIR/$f" ]]; then
			echo "Missing lab asset: $LAB_DIR/$f" >&2
			exit 1
		fi
		cp "$LAB_DIR/$f" "$BUNDLE_STAGING/$f"
	done
	printf '{"builtAt":"%s","repoRoot":"%s","files":%s}\n' \
		"$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
		"$REPO_ROOT" \
		"$(printf '%s\n' "${LAB_BUNDLE_FILES[@]}" | python3 -c 'import json,sys; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')" \
		>"$BUNDLE_STAGING/manifest.json"
}

prepare_icon() {
	"$SCRIPT_DIR/pd-kit-icons.sh" anim-lab
	mkdir -p "$ELECTRON_DIR/build"
	cp "$BUILD_DIR/AnimLabAppIcon.icns" "$ELECTRON_DIR/build/icon.icns"
}

install_built_app() {
	local out_dir
	out_dir="$(cd "$ELECTRON_DIR" && node -p "require('./package.json').build.directories.output" 2>/dev/null || echo '../../../scripts/release/anim-lab-dist')"
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

	local bundled="$APP_BUNDLE/Contents/Resources/anim-lab"
	if [[ ! -f "$bundled/serve_animlab.py" ]]; then
		mkdir -p "$bundled"
		cp -R "$BUNDLE_STAGING/." "$bundled/"
	fi

	if command -v codesign >/dev/null 2>&1; then
		xattr -cr "$APP_BUNDLE" 2>/dev/null || true
		codesign --force --deep --sign - "$APP_BUNDLE" 2>&1 || true
	fi
}

main() {
	if ! command -v node >/dev/null 2>&1; then
		echo "Node.js is required." >&2
		exit 1
	fi
	if ! command -v npm >/dev/null 2>&1; then
		echo "npm is required." >&2
		exit 1
	fi

	write_repo_config
	prepare_icon

	if [[ "$DEV_ONLY" -eq 0 ]]; then
		prepare_lab_bundle
	fi

	cd "$ELECTRON_DIR"
	echo "Installing npm dependencies in $ELECTRON_DIR ..."
	npm install

	if [[ "$DEV_ONLY" -eq 1 ]]; then
		echo ""
		echo "Dev mode — launch with:"
		echo "  cd \"$ELECTRON_DIR\" && PD_REPO_ROOT=\"$REPO_ROOT\" npm start"
		exit 0
	fi

	echo "Building macOS .app with electron-builder ..."
	npm run build
	install_built_app

	rm -rf "$LEGACY_APP_BUNDLE" "$RELEASE_DIR/Perfect Dark Kit — Animation Lab.app"
	rm -f "$REPO_ROOT/Perfect Dark Animation Lab.app" "$REPO_ROOT/Perfect Dark Kit — Animation Lab.app"
	rm -f "$REPO_ROOT/${APP_NAME}.app"
	if [[ "$SYMLINK_AT_ROOT" -eq 1 ]]; then
		kit_symlink_app "${APP_NAME}.app"
	fi

	printf '\nBuilt Animation Lab app:\n  %s\n' "$APP_BUNDLE"
	if [[ "$SYMLINK_AT_ROOT" -eq 1 ]]; then
		printf '  %s -> %s\n' "$REPO_ROOT/${APP_NAME}.app" "$APP_BUNDLE"
	fi
	printf '\nDev fallback: cd journal/anim_lab/electron && PD_REPO_ROOT="%s" npm start\n' "$REPO_ROOT"
	printf 'Browser fallback: python3 journal/anim_lab/serve_animlab.py\n'
}

main "$@"
