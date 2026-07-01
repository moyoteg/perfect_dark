#!/usr/bin/env bash
# Perfect Dark Kit CLI — version, build, open apps, validate maps, play test maps.
#
# Usage:
#   ./scripts/pd-kit.sh version
#   ./scripts/pd-kit.sh build [--game-only|--apps-only]
#   ./scripts/pd-kit.sh open [kit|map-editor|anim-lab|asset-upgrader]
#   ./scripts/pd-kit.sh validate [level ...]
#   ./scripts/pd-kit.sh play [--test-map] [--mod mod_allinone]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pd-kit-common.sh
source "$SCRIPT_DIR/pd-kit-common.sh"

cmd="${1:-}"
shift || true

usage() {
	cat <<EOF
${PD_KIT_NAME} v${PD_KIT_VERSION} (port v${PD_PORT_VERSION})

Usage:
  pd-kit.sh version
  pd-kit.sh build [--game-only|--apps-only|--no-symlink|--skip-game]
  pd-kit.sh open [kit|map-editor|anim-lab|asset-upgrader]
  pd-kit.sh validate [level ...]
  pd-kit.sh play [--test-map] [--mod MOD]

Examples:
  ./scripts/pd-kit.sh build
  ./scripts/pd-kit.sh open
  ./scripts/pd-kit.sh open map-editor
  ./scripts/pd-kit.sh validate my_arena testarena
  ./scripts/pd-kit.sh play --test-map --mod mod_allinone
EOF
}

case "$cmd" in
version | -V | --version)
	echo "${PD_KIT_NAME} ${PD_KIT_VERSION} (port ${PD_PORT_VERSION})"
	echo "Repo: $PD_KIT_REPO_ROOT"
	echo "Support: $PD_KIT_SUPPORT_ROOT"
	echo "Logs: $PD_KIT_LOGS_ROOT"
	;;
build)
	exec "$SCRIPT_DIR/build-pd-kit.sh" "$@"
	;;
open)
	app="${1:-kit}"
	case "$app" in
	kit | hub | "")
		kit_open_app "$PD_KIT_APP_HUB"
		;;
	map-editor | editor)
		kit_open_app "$PD_KIT_APP_MAP_EDITOR"
		;;
	anim-lab | anim | animation)
		kit_open_app "$PD_KIT_APP_ANIM_LAB"
		;;
	asset-upgrader | upgrader | textures)
		kit_open_app "$PD_KIT_APP_ASSET_UPGRADER"
		;;
	*)
		echo "Unknown app: $app" >&2
		echo "Choose: map-editor, anim-lab, asset-upgrader" >&2
		exit 2
		;;
	esac
	;;
validate)
	cd "$PD_KIT_REPO_ROOT"
	if [[ $# -eq 0 ]]; then
		set -- my_arena testarena
	fi
	for level in "$@"; do
		echo "==> pdmap validate $level"
		python3 tools/pdmap.py validate "$level"
	done
	;;
play)
	cd "$PD_KIT_REPO_ROOT"
	mod="mod_allinone"
	extra=()
	while [[ $# -gt 0 ]]; do
		case "$1" in
		--test-map)
			extra+=(--test-map)
			shift
			;;
		--mod)
			mod="${2:-}"
			shift 2
			;;
		*)
			echo "Unknown play option: $1" >&2
			exit 2
			;;
		esac
	done
	binary="$PD_KIT_REPO_ROOT/build/pd.arm64"
	if [[ ! -x "$binary" ]]; then
		echo "Missing game binary: $binary" >&2
		echo "Run: ./scripts/pd-kit.sh build --game-only" >&2
		exit 1
	fi
	exec "$binary" --moddir "mods/$mod" "${extra[@]}"
	;;
"" | -h | --help | help)
	usage
	;;
*)
	echo "Unknown command: $cmd" >&2
	usage
	exit 2
	;;
esac
