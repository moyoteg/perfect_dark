#!/usr/bin/env bash
# Build the Electron-based Perfect Dark Asset Catalog macOS .app bundle.
#
# Outputs:
#   scripts/release/PD Asset Catalog.app
#
# Usage:
#   ./scripts/build-object-catalog-electron.sh              # builds + repo-root symlink
#   ./scripts/build-object-catalog-electron.sh --no-symlink # build only
#   ./scripts/build-object-catalog-electron.sh --dev        # npm start only (no .app)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pd-kit-common.sh
source "$SCRIPT_DIR/pd-kit-common.sh"
REPO_ROOT="$PD_KIT_REPO_ROOT"
ELECTRON_DIR="$REPO_ROOT/journal/object_catalog/electron"
APP_DIR="$REPO_ROOT/journal/object_catalog"
BUNDLE_STAGING="$ELECTRON_DIR/object-catalog-bundle"
RELEASE_DIR="$PD_KIT_RELEASE_DIR"
APP_BUNDLE_NAME="${PD_KIT_APP_OBJECT_CATALOG:-PD Asset Catalog.app}"
APP_NAME="${APP_BUNDLE_NAME%.app}"
APP_BUNDLE="$RELEASE_DIR/${APP_NAME}.app"
BUILD_DIR="$REPO_ROOT/.tmp-map-editor-app-build"
SYMLINK_AT_ROOT=1
DEV_ONLY=0

APP_BUNDLE_FILES=(
	serve_object_catalog.py
	object_catalog.html
	mesh_viewer.js
	mesh_shaders.inc.js
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

prepare_app_bundle() {
	echo "Staging object-catalog bundle for Contents/Resources/object-catalog/ ..."
	rm -rf "$BUNDLE_STAGING"
	mkdir -p "$BUNDLE_STAGING"
	local f
	for f in "${APP_BUNDLE_FILES[@]}"; do
		if [[ ! -f "$APP_DIR/$f" ]]; then
			echo "Missing catalog asset: $APP_DIR/$f" >&2
			exit 1
		fi
		cp "$APP_DIR/$f" "$BUNDLE_STAGING/$f"
	done
	printf '{"builtAt":"%s","repoRoot":"%s","files":%s}\n' \
		"$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
		"$REPO_ROOT" \
		"$(printf '%s\n' "${APP_BUNDLE_FILES[@]}" | python3 -c 'import json,sys; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')" \
		>"$BUNDLE_STAGING/manifest.json"
}

prepare_icon() {
	"$SCRIPT_DIR/pd-kit-icons.sh" object-catalog
	mkdir -p "$ELECTRON_DIR/build"
	cp "$BUILD_DIR/ObjectCatalogAppIcon.icns" "$ELECTRON_DIR/build/icon.icns"
}

install_built_app() {
	local out_dir
	out_dir="$(cd "$ELECTRON_DIR" && node -p "require('./package.json').build.directories.output" 2>/dev/null || echo '../../../scripts/release/object-catalog-dist')"
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

	local bundled="$APP_BUNDLE/Contents/Resources/object-catalog"
	if [[ ! -f "$bundled/serve_object_catalog.py" ]]; then
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
		prepare_app_bundle
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

	# Retire previous product name if present.
	rm -rf "$RELEASE_DIR/PD Object Catalog.app"
	rm -f "$REPO_ROOT/PD Object Catalog.app" "$REPO_ROOT/${APP_NAME}.app"
	if [[ "$SYMLINK_AT_ROOT" -eq 1 ]]; then
		kit_symlink_app "${APP_NAME}.app"
	fi

	printf '\nBuilt Asset Catalog app:\n  %s\n' "$APP_BUNDLE"
	if [[ "$SYMLINK_AT_ROOT" -eq 1 ]]; then
		printf '  %s -> %s\n' "$REPO_ROOT/${APP_NAME}.app" "$APP_BUNDLE"
	fi
	printf '\nDev fallback: cd journal/object_catalog/electron && PD_REPO_ROOT="%s" npm start\n' "$REPO_ROOT"
	printf 'Browser fallback: python3 journal/object_catalog/serve_object_catalog.py\n'
}

main "$@"
