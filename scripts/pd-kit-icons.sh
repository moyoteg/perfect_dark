#!/usr/bin/env bash
# Generate distinct .icns icons for each Perfect Dark Kit Electron app.
#
# Usage:
#   ./scripts/pd-kit-icons.sh              # build all kit icons
#   ./scripts/pd-kit-icons.sh all
#   ./scripts/pd-kit-icons.sh kit-hub|map-editor|map-launcher|anim-lab|asset-upgrader

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$REPO_ROOT/.tmp-map-editor-app-build"

build_icns_from_png() {
	local png="$1"
	local icns="$2"
	local iconset="${icns%.icns}.iconset"
	rm -rf "$iconset"
	mkdir -p "$iconset"
	local size
	for size in 16 32 128 256 512; do
		sips -z "$size" "$size" "$png" --out "$iconset/icon_${size}x${size}.png" >/dev/null
		sips -z "$((size * 2))" "$((size * 2))" "$png" --out "$iconset/icon_${size}x${size}@2x.png" >/dev/null
	done
	iconutil -c icns "$iconset" -o "$icns"
}

build_icon() {
	local key="$1"
	local swift="$2"
	local png="$3"
	local icns="$4"
	if [[ -f "$icns" && "${PD_KIT_ICONS_FORCE:-0}" != "1" ]]; then
		echo "  icon cached: $(basename "$icns")"
		return 0
	fi
	echo "  generating $(basename "$icns") ..."
	mkdir -p "$BUILD_DIR"
	swift "$SCRIPT_DIR/$swift" "$png"
	build_icns_from_png "$png" "$icns"
}

build_kit_hub() {
	build_icon kit-hub generate-kit-hub-icon.swift \
		"$BUILD_DIR/kit-hub-1024.png" "$BUILD_DIR/KitHubAppIcon.icns"
}

build_map_editor() {
	build_icon map-editor generate-map-editor-icon.swift \
		"$BUILD_DIR/map-editor-1024.png" "$BUILD_DIR/MapEditorAppIcon.icns"
	cp "$BUILD_DIR/MapEditorAppIcon.icns" "$BUILD_DIR/EditorAppIcon.icns"
}

build_map_launcher() {
	build_icon map-launcher generate-map-launcher-icon.swift \
		"$BUILD_DIR/map-launcher-1024.png" "$BUILD_DIR/MapLauncherAppIcon.icns"
}

build_anim_lab() {
	build_icon anim-lab generate-anim-lab-icon.swift \
		"$BUILD_DIR/anim-lab-icon-1024.png" "$BUILD_DIR/AnimLabAppIcon.icns"
}

build_asset_upgrader() {
	build_icon asset-upgrader generate-asset-upgrader-icon.swift \
		"$BUILD_DIR/asset-upgrader-1024.png" "$BUILD_DIR/AssetUpgraderAppIcon.icns"
}

TARGET="${1:-all}"
mkdir -p "$BUILD_DIR"

case "$TARGET" in
all)
	echo "==> Building all Perfect Dark Kit icons"
	build_kit_hub
	build_map_editor
	build_map_launcher
	build_anim_lab
	build_asset_upgrader
	;;
kit-hub) build_kit_hub ;;
map-editor) build_map_editor ;;
map-launcher) build_map_launcher ;;
anim-lab) build_anim_lab ;;
asset-upgrader) build_asset_upgrader ;;
-h | --help)
	echo "Usage: $0 [all|kit-hub|map-editor|map-launcher|anim-lab|asset-upgrader]"
	exit 0
	;;
*)
	echo "Unknown icon target: $TARGET" >&2
	exit 2
	;;
esac

echo "Icons ready under $BUILD_DIR"
