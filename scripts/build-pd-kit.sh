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
  --apps-only    Build child apps + Kit hub wrapper
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
	kit_prune_legacy_app_bundles
	"$SCRIPT_DIR/pd-kit-icons.sh" all

	echo "==> Building Map Editor"
	"$SCRIPT_DIR/build-map-editor-electron.sh" --no-symlink

	echo "==> Building Animation Lab"
	"$SCRIPT_DIR/build-anim-lab-electron.sh" --no-symlink

	echo "==> Building Asset Upgrader"
	"$SCRIPT_DIR/build-asset-upgrader-electron.sh" --build --no-symlink

	echo "==> Building Play Last Test Map"
	"$SCRIPT_DIR/build-map-editor-app.sh"

	echo "==> Building LLM Play (optional sibling project)"
	if [[ -f "$SCRIPT_DIR/build-llm-play-electron.sh" ]]; then
		if "$SCRIPT_DIR/build-llm-play-electron.sh" 2>/dev/null; then
			echo "    LLM Play.app built"
			local llm_src="$PD_KIT_REPO_ROOT/../llm-play/LLM Play.app"
			if [[ -d "$llm_src" ]]; then
				ln -sfn "$llm_src" "$PD_KIT_RELEASE_DIR/LLM Play.app"
			fi
		else
			echo "    WARNING: LLM Play build skipped or failed (sibling llm-play project)" >&2
		fi
	fi
}

build_kit_hub() {
	echo "==> Building Kit Hub (wraps all tools)"
	if [[ "$SYMLINK_AT_ROOT" -eq 0 ]]; then
		"$SCRIPT_DIR/build-pd-kit-launcher-electron.sh" --no-symlink
	else
		"$SCRIPT_DIR/build-pd-kit-launcher-electron.sh"
	fi
}

main() {
	echo "==> ${PD_KIT_NAME} v${PD_KIT_VERSION} (port v${PD_PORT_VERSION})"
	mkdir -p "$PD_KIT_RELEASE_DIR"

	if [[ "$BUILD_GAME" -eq 1 ]]; then
		build_game
	fi

	if [[ "$BUILD_APPS" -eq 1 ]]; then
		build_apps
		write_kit_release_manifest "$PD_BINARY" >/dev/null
		build_kit_hub
		kit_prune_legacy_app_bundles
	fi

	manifest_path="$(write_kit_release_manifest "$PD_BINARY")"
	if [[ -d "$PD_KIT_RELEASE_DIR/$PD_KIT_APP_HUB" ]]; then
		cp "$manifest_path" "$PD_KIT_RELEASE_DIR/$PD_KIT_APP_HUB/Contents/Resources/kit-manifest.json"
	fi
	echo ""
	echo "==> Kit build complete"
	echo "    Manifest: $manifest_path"
	echo "    Game:     $PD_BINARY"
	echo "    Release:  $PD_KIT_RELEASE_DIR/"
	echo ""
	echo "Launch hub: ./scripts/pd-kit.sh open"
}

main "$@"
