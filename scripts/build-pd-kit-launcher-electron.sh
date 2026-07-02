#!/usr/bin/env bash
# Build the Perfect Dark Kit hub .app — wraps Map Editor, Animation Lab,
# and Asset Upgrader inside Contents/Resources/Apps/.
#
# Outputs:
#   scripts/release/Perfect Dark Kit.app
#
# Usage:
#   ./scripts/build-pd-kit-launcher-electron.sh              # build + wrap + symlink
#   ./scripts/build-pd-kit-launcher-electron.sh --no-symlink
#   ./scripts/build-pd-kit-launcher-electron.sh --dev        # npm start only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pd-kit-common.sh
source "$SCRIPT_DIR/pd-kit-common.sh"

ELECTRON_DIR="$PD_KIT_REPO_ROOT/tools/pd_kit/electron"
RELEASE_DIR="$PD_KIT_RELEASE_DIR"
APP_NAME="${PD_KIT_APP_HUB%.app}"
APP_BUNDLE="$RELEASE_DIR/${APP_NAME}.app"
BUILD_DIR="$PD_KIT_REPO_ROOT/.tmp-map-editor-app-build"
WRAPPED_DIR_NAME="Apps"
SYMLINK_AT_ROOT=1
DEV_ONLY=0

CHILD_APPS=()
while IFS= read -r bundle; do
	[[ -n "$bundle" ]] && CHILD_APPS+=("$bundle")
done < <(kit_json_wrap_bundles)

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
	printf '{"repoRoot": "%s"}\n' "$PD_KIT_REPO_ROOT" >"$ELECTRON_DIR/repo-config.json"
}

prepare_icon() {
	"$SCRIPT_DIR/pd-kit-icons.sh" kit-hub
	mkdir -p "$ELECTRON_DIR/build"
	cp "$BUILD_DIR/KitHubAppIcon.icns" "$ELECTRON_DIR/build/icon.icns"
}

install_built_app() {
	local out_dir
	out_dir="$(cd "$ELECTRON_DIR" && node -p "require('./package.json').build.directories.output" 2>/dev/null || echo '../../../scripts/release/kit-hub-dist')"
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

	local resources="$APP_BUNDLE/Contents/Resources"
	mkdir -p "$resources"
	printf '%s\n' "$PD_KIT_REPO_ROOT" >"$resources/repo_root.txt"
	cp "$ELECTRON_DIR/repo-config.json" "$resources/repo-config.json" 2>/dev/null || true
}

wrap_child_apps() {
	local apps_dir="$APP_BUNDLE/Contents/Resources/$WRAPPED_DIR_NAME"
	mkdir -p "$apps_dir"
	local child missing=0
	for child in "${CHILD_APPS[@]}"; do
		local src="$RELEASE_DIR/$child"
		if [[ ! -d "$src" ]]; then
			echo "WARNING: missing child app (not wrapped): $src" >&2
			missing=1
			continue
		fi
		echo "  wrapping $child"
		rm -rf "$apps_dir/$child"
		cp -R "$src" "$apps_dir/$child"
	done
	if [[ "$missing" -eq 1 ]]; then
		echo "Build child apps first: ./scripts/build-pd-kit.sh --apps-only" >&2
	fi
}

copy_manifest() {
	if [[ -f "$RELEASE_DIR/kit-manifest.json" ]]; then
		cp "$RELEASE_DIR/kit-manifest.json" "$APP_BUNDLE/Contents/Resources/kit-manifest.json"
	fi
}

sign_app() {
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
		echo ""
		echo "Dev mode — launch with:"
		echo "  cd \"$ELECTRON_DIR\" && PD_REPO_ROOT=\"$PD_KIT_REPO_ROOT\" npm start"
		exit 0
	fi

	echo "Building ${APP_NAME}.app with electron-builder ..."
	npm run build
	install_built_app
	echo "Wrapping child apps into Contents/Resources/${WRAPPED_DIR_NAME}/ ..."
	wrap_child_apps
	copy_manifest
	sign_app

	if [[ "$SYMLINK_AT_ROOT" -eq 1 ]]; then
		kit_symlink_app "${APP_NAME}.app"
	fi

	printf '\nBuilt kit hub app:\n  %s\n' "$APP_BUNDLE"
	printf 'Wrapped tools live under:\n  %s/Contents/Resources/%s/\n' "$APP_BUNDLE" "$WRAPPED_DIR_NAME"
	if [[ "$SYMLINK_AT_ROOT" -eq 1 ]]; then
		printf '  %s -> %s\n' "$PD_KIT_REPO_ROOT/${APP_NAME}.app" "$APP_BUNDLE"
	fi
}

main "$@"
