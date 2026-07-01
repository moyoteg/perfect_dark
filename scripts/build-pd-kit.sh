#!/usr/bin/env bash
# Build the full Perfect Dark Kit: game binary + all Electron authoring apps.
#
# Usage:
#   ./scripts/build-pd-kit.sh                 # game + all apps + manifest
#   ./scripts/build-pd-kit.sh --game-only     # cmake pd target only
#   ./scripts/build-pd-kit.sh --apps-only     # Electron apps only
#   ./scripts/build-pd-kit.sh --no-symlink    # skip repo-root .app symlinks
#   ./scripts/build-pd-kit.sh --skip-game     # apps + manifest (default game build skipped if binary exists)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pd-kit-common.sh
source "$SCRIPT_DIR/pd-kit-common.sh"

BUILD_GAME=1
BUILD_APPS=1
SYMLINK_AT_ROOT=1
SKIP_GAME_IF_EXISTS=0
CMAKE_JOBS="${CMAKE_JOBS:-8}"

while [[ $# -gt 0 ]]; do
	case "$1" in
	--game-only)
		BUILD_GAME=1
		BUILD_APPS=0
		shift
		;;
	--apps-only)
		BUILD_GAME=0
		BUILD_APPS=1
		shift
		;;
	--no-symlink)
		SYMLINK_AT_ROOT=0
		shift
		;;
	--skip-game)
		SKIP_GAME_IF_EXISTS=1
		shift
		;;
	-h | --help)
		cat <<EOF
Usage: $0 [--game-only] [--apps-only] [--no-symlink] [--skip-game]

Build Perfect Dark Kit v${PD_KIT_VERSION} (port v${PD_PORT_VERSION}).

  --game-only    Build ./build/pd.arm64 only
  --apps-only    Build Map Editor, Animation Lab, Asset Upgrader only
  --no-symlink   Do not create repo-root .app symlinks
  --skip-game    Skip cmake when build/pd.arm64 already exists
EOF
		exit 0
		;;
	*)
		echo "Unknown option: $1" >&2
		exit 2
		;;
	esac
done

PD_BINARY="$PD_KIT_REPO_ROOT/build/pd.arm64"

build_game() {
	if [[ "$SKIP_GAME_IF_EXISTS" -eq 1 && -f "$PD_BINARY" ]]; then
		echo "==> Game binary exists — skipping cmake ($PD_BINARY)"
		return 0
	fi
	echo "==> Building PC port (pd target)"
	cd "$PD_KIT_REPO_ROOT"
	if [[ ! -d build ]]; then
		cmake -G"Unix Makefiles" -Bbuild -DCMAKE_OSX_ARCHITECTURES=arm64 .
	fi
	cmake --build build --target pd -j"$CMAKE_JOBS"
}

build_apps() {
	local symlink_flag=()
	if [[ "$SYMLINK_AT_ROOT" -eq 0 ]]; then
		symlink_flag=(--no-symlink)
	fi

	echo "==> Building Map Editor"
	"$SCRIPT_DIR/build-map-editor-electron.sh" "${symlink_flag[@]}"

	echo "==> Building Animation Lab"
	"$SCRIPT_DIR/build-anim-lab-electron.sh" "${symlink_flag[@]}"

	echo "==> Building Asset Upgrader"
	"$SCRIPT_DIR/build-asset-upgrader-electron.sh" --build "${symlink_flag[@]}"
}

main() {
	echo "==> ${PD_KIT_NAME} v${PD_KIT_VERSION} (port v${PD_PORT_VERSION})"
	mkdir -p "$PD_KIT_RELEASE_DIR"

	if [[ "$BUILD_GAME" -eq 1 ]]; then
		build_game
	fi

	if [[ "$BUILD_APPS" -eq 1 ]]; then
		build_apps
	fi

	local manifest_path
	manifest_path="$(write_kit_release_manifest "$PD_BINARY")"
	echo ""
	echo "==> Kit build complete"
	echo "    Manifest: $manifest_path"
	echo "    Game:     $PD_BINARY"
	echo "    Release:  $PD_KIT_RELEASE_DIR/"
	echo ""
	echo "Launch tools: ./scripts/pd-kit.sh open map-editor"
}

main "$@"
