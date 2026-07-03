#!/usr/bin/env bash

# Perfect Dark All-in-One Mod Launcher for macOS
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${PD_REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
APP_TITLE="Perfect Dark All-in-One Mod"

show_dialog() {
	local message="$1"
	local title="${2:-$APP_TITLE}"

	if command -v osascript >/dev/null 2>&1; then
		osascript - "$message" "$title" >/dev/null 2>&1 <<'APPLESCRIPT' || true
on run argv
	display dialog (item 1 of argv) with title (item 2 of argv) buttons {"OK"} default button "OK"
end run
APPLESCRIPT
	else
		printf '%s: %s\n' "$title" "$message" >&2
	fi
}

main() {
	cd "$REPO_ROOT"

	# 1. Verify base ROM
	local rom_path="data/pd.ntsc-final.z64"
	if [[ ! -f "$rom_path" ]]; then
		local fallback_paths=(
			"/Users/moigutierrez/Library/CloudStorage/GoogleDrive-moyoteg@gmail.com/My Drive/Games/N64 Decomp/PerfectDarkShared/pd.ntsc-final.z64"
			"/Users/moigutierrez/Library/Mobile Documents/com~apple~CloudDocs/Work/Personal/Games/perfect_dark/pd.ntsc-final.z64"
		)
		for fb_path in "${fallback_paths[@]}"; do
			if [[ -f "$fb_path" ]]; then
				mkdir -p data
				if cp "$fb_path" "$rom_path" 2>/dev/null; then
					break
				fi
			fi
		done
	fi

	if [[ ! -f "$rom_path" ]]; then
		show_dialog "Missing base ROM file!\n\nChecked path: $(pwd)/$rom_path\nREPO_ROOT: $REPO_ROOT\n\nPlease place your Perfect Dark US v1.1 ROM at:\nperfect_dark_jonaeru_aio/data/pd.ntsc-final.z64\n\nRefer to README_MOD_INFO.md for details."
		return 1
	fi

	# 2. Verify mod assets
	if [[ ! -d "mods" ]] || [[ ! -d "mods/mod_allinone" ]]; then
		show_dialog "Missing Mod Assets!\n\nPlease download all_in_one_mods from the Google Drive link in README_MOD_INFO.md and extract the 'mods' folder into the root of perfect_dark_jonaeru_aio."
		return 1
	fi

	# 4. Launch the game with All-in-One Mod arguments
	local binary="./build/pd.arm64"
	if [[ ! -f "$binary" ]]; then
		binary="./pd.arm64"
	fi
	if [[ ! -f "$binary" ]]; then
		show_dialog "Executable pd.arm64 not found!\n\nPlease compile the PC port first. Refer to README_MOD_INFO.md for build steps."
		return 1
	fi

	if [[ ! -x "$binary" ]]; then
		chmod +x "$binary"
	fi

	exec "$binary" \
		--moddir mods/mod_allinone \
		--gexmoddir mods/mod_gex \
		--kakarikomoddir mods/mod_kakariko \
		--darknoonmoddir mods/mod_dark_noon
}

main "$@"
