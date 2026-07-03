#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RESOURCES_DIR="$REPO_ROOT/PerfectDarkAIO.app/Contents/Resources"
BUILD_DIR="$REPO_ROOT/.tmp-icon-build"
ART_SOURCE_URL="https://upload.wikimedia.org/wikipedia/en/3/32/Perfect_dark_box.jpg"
SOURCE_ART="$BUILD_DIR/perfectdark-box.jpg"
SOURCE_PNG="$BUILD_DIR/perfectdark-1024.png"
ICONSET_DIR="$BUILD_DIR/AppIcon.iconset"
ICON_PATH="$RESOURCES_DIR/AppIcon.icns"

mkdir -p "$RESOURCES_DIR" "$BUILD_DIR"
curl -fsSL "$ART_SOURCE_URL" -o "$SOURCE_ART"
swift "$SCRIPT_DIR/generate-perfectdark-icon.swift" "$SOURCE_ART" "$SOURCE_PNG"

rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"

for size in 16 32 128 256 512; do
	sips -z "$size" "$size" "$SOURCE_PNG" --out "$ICONSET_DIR/icon_${size}x${size}.png" >/dev/null
	sips -z "$((size * 2))" "$((size * 2))" "$SOURCE_PNG" --out "$ICONSET_DIR/icon_${size}x${size}@2x.png" >/dev/null
done

iconutil -c icns "$ICONSET_DIR" -o "$ICON_PATH"
printf 'Wrote %s\n' "$ICON_PATH"
