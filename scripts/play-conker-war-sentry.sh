#!/usr/bin/env bash
# War Colors (STAGE_EXTRA26 / bg_mp13): mod_kakariko Conker seg/tiles/pads/setup.
#
# Spawn/weapons: Conker-correct Ump_setupmp13Z (12 balanced spawns, 10 floor weapons).
# Pads: full Conker floor Y probe on usable mp13 pad graph (219 pads).
# --teams-battle only enables MP teams + bot split; sentry flags do not affect spawn positions.
#
# Usage:
#   ./scripts/play-conker-war-sentry.sh              # baseline (8 sims, teams, sentry flags)
#   ./scripts/play-conker-war-sentry.sh --solo       # human only (spawn smoke test)
#   ./scripts/play-conker-war-sentry.sh --full-battle # 31 sims max (teams chr cap 32 incl. human)
#   ./scripts/play-conker-war-sentry.sh --clean      # purge mp13 overrides only, no launch
#   ./scripts/play-conker-war-sentry.sh --deploy-custom # experimental 64-spawn overlay (not default)
#   ./scripts/play-conker-war-sentry.sh --no-play [--deploy-custom]
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PD="$REPO/build/pd.arm64"
MODDIR="$REPO/mods/mod_allinone"
KAKARIKO_MODDIR="$REPO/mods/mod_kakariko"
DATA_DIR="$REPO/data"
ROM="$DATA_DIR/pd.ntsc-final.z64"
LOG_DIR="$REPO/journal/map_learn"
LAST_LOG="$LOG_DIR/.conker_war_sentry_inf_test.log"
BOOT_STAGE="0x5b"

NUM_SIMS=8
NO_PLAY=false
DEPLOY_CUSTOM=false
CLEAN_ONLY=false
SOLO=false
FULL_BATTLE=false
SENTRY_FLAGS=true
TEAMS_BATTLE=true

while [[ $# -gt 0 ]]; do
	case "$1" in
	--no-play) NO_PLAY=true; shift ;;
	--deploy-custom) DEPLOY_CUSTOM=true; shift ;;
	--clean) CLEAN_ONLY=true; shift ;;
	--solo) SOLO=true; NUM_SIMS=0; shift ;;
	--full-battle) FULL_BATTLE=true; NUM_SIMS=50; shift ;;
	--no-sentry) SENTRY_FLAGS=false; shift ;;
	--no-teams) TEAMS_BATTLE=false; shift ;;
	--retail-setup)
		echo "  Note: --retail-setup is deprecated (retail layout is the default)." >&2
		shift
		;;
	--num-sims)
		NUM_SIMS="${2:?--num-sims requires a value}"
		shift 2
		;;
	*) echo "Unknown arg: $1" >&2; exit 1 ;;
	esac
done

# Presets win over --num-sims order (map launcher may pass both --full-battle and --num-sims).
# Teams MP caps at MAX_CHRSPERTEAM (32) including the human — 31 sims max or the game SIGBUS-crashes.
WAR_COLORS_MAX_TEAM_SIMS=31
if [[ "$SOLO" == true ]]; then
	NUM_SIMS=0
elif [[ "$FULL_BATTLE" == true ]]; then
	NUM_SIMS=$WAR_COLORS_MAX_TEAM_SIMS
elif [[ "$NUM_SIMS" -lt 1 ]]; then
	NUM_SIMS=8
fi
if [[ "$TEAMS_BATTLE" == true && "$SOLO" != true && "$NUM_SIMS" -gt $WAR_COLORS_MAX_TEAM_SIMS ]]; then
	echo "  WARN: capping sims $NUM_SIMS → $WAR_COLORS_MAX_TEAM_SIMS (teams MP chr limit is 32 incl. human)" >&2
	NUM_SIMS=$WAR_COLORS_MAX_TEAM_SIMS
fi

remove_mp13_overrides() {
	local removed=0
	# Purge experimental mp13 setup overrides outside mod_kakariko (canonical setup lives there).
	while IFS= read -r -d '' _mp13_override; do
		case "$_mp13_override" in
		"$KAKARIKO_MODDIR"/*) continue ;;
		esac
		rm -f "$_mp13_override"
		echo "  removed $(basename "$_mp13_override") from ${_mp13_override#"$REPO/mods/"}"
		removed=$((removed + 1))
	done < <(find "$REPO/mods" \( -name 'Ump_setupmp13Z' -o -name 'Usetupmp13Z' \) -type f -print0 2>/dev/null)

	# Purge custom pad overrides outside mod_kakariko (canonical Conker-corrected pads live there).
	while IFS= read -r -d '' _mp13_pads; do
		rm -f "$_mp13_pads"
		echo "  removed $(basename "$_mp13_pads") from ${_mp13_pads#"$REPO/mods/"}"
		removed=$((removed + 1))
	done < <(find "$REPO/mods" -path "$KAKARIKO_MODDIR/*" -prune -o -name 'bg_mp13_padsZ' -type f -print0 2>/dev/null)

	if [[ "$removed" -eq 0 ]]; then
		echo "  mp13 overrides: none outside mod_kakariko (kakariko pads + setup canonical)"
	else
		echo "  mp13 overrides: removed $removed file(s) outside mod_kakariko"
	fi
}

deploy_war_colors_conker() {
	echo "Deploying Conker-correct mp13 setup to mod_kakariko…"
	python3 tools/pdmap.py build war_colors_conker --deploy --mod mod_kakariko
	echo "Probing Conker floor Y for all usable mp13 pads…"
	python3 tools/war_colors_correct_pads.py --pd "$PD" --all
}

verify_deployed_setup() {
	# Fail fast if Conker setup was not deployed or spawn pads drift from source.
	if [[ ! -f "$KAKARIKO_MODDIR/files/Ump_setupmp13Z" ]]; then
		echo "ERROR: missing $KAKARIKO_MODDIR/files/Ump_setupmp13Z — deploy failed" >&2
		exit 1
	fi
	if ! python3 - <<'PY'
import struct, sys, zlib
from pathlib import Path
ROOT = Path(".")
setup = ROOT / "mods/mod_kakariko/files/Ump_setupmp13Z"
raw = setup.read_bytes()
out_len = int.from_bytes(raw[2:5], "big")
dec = zlib.decompressobj(wbits=-15)
data = dec.decompress(raw[5:])
if len(data) < out_len:
    data += dec.flush()
data = data[:out_len]
ptr_intro = struct.unpack(">I", data[0x0C:0x10])[0]
i = ptr_intro
spawns = []
while i + 12 <= len(data):
    code, a, b = struct.unpack(">3I", data[i:i+12])
    if code == 0:
        spawns.append(a)
        i += 12
    elif code == 1:
        i += 16
    elif code == 2:
        i += 16
    elif code in (5, 7):
        i += 8
    elif code in (9, 10, 11):
        i += 12
    elif code in (0xFFFFFFFF, 0x7FFFFFFF, 12):
        break
    else:
        break
expected = [35, 116, 113, 0, 218, 108, 88, 80, 16, 82, 20, 89]
if spawns != expected:
    print(f"ERROR: deployed spawn pads {spawns} != expected {expected}", file=sys.stderr)
    sys.exit(1)
print(f"  setup verify: 12 Conker in-base spawn pads OK ({spawns})")
PY
	then
		exit 1
	fi
	if [[ ! -f "$KAKARIKO_MODDIR/files/bgdata/bg_mp13_padsZ" ]]; then
		echo "ERROR: missing probed pads at $KAKARIKO_MODDIR/files/bgdata/bg_mp13_padsZ" >&2
		exit 1
	fi
	echo "  pads verify: mod_kakariko bg_mp13_padsZ present"
}

kill_stale_war_colors() {
	local p cmd
	for p in $(pgrep -x pd.arm64 2>/dev/null); do
		cmd="$(ps -p "$p" -o command= 2>/dev/null || true)"
		if [[ "$cmd" == *"$PD"* && "$cmd" == *"--boot-stage"* && "$cmd" == *"$BOOT_STAGE"* ]]; then
			echo "  killing stale War Colors pid $p"
			kill "$p" 2>/dev/null || true
		fi
	done
}

ensure_rom() {
	if [[ -f "$ROM" ]]; then
		return 0
	fi
	local fb=(
		"/Users/moigutierrez/Library/CloudStorage/GoogleDrive-moyoteg@gmail.com/My Drive/Games/N64 Decomp/PerfectDarkShared/pd.ntsc-final.z64"
		"/Users/moigutierrez/Library/Mobile Documents/com~apple~CloudDocs/Work/Personal/Games/perfect_dark/pd.ntsc-final.z64"
	)
	for p in "${fb[@]}"; do
		if [[ -f "$p" ]]; then
			mkdir -p "$DATA_DIR"
			cp "$p" "$ROM" && return 0
		fi
	done
	echo "ERROR: missing ROM at $ROM (see README_MOD_INFO.md)" >&2
	exit 1
}

build_play_flags() {
	play_parts=(
		--boot-stage "$BOOT_STAGE"
		--skip-intro
		--scenario-0
		--basedir "$DATA_DIR"
		--moddir "$MODDIR"
		--kakarikomoddir "$KAKARIKO_MODDIR"
		--savedir "$REPO"
		--num-sims "$NUM_SIMS"
		--sim-difficulty 5
	)

	if [[ "$SOLO" == true ]]; then
		play_parts+=(--solo)
	fi
	if [[ "$TEAMS_BATTLE" == true ]]; then
		play_parts+=(--teams-battle)
	fi
	if [[ "$SENTRY_FLAGS" == true ]]; then
		play_parts+=(--laptop-sentry-infinite-ammo --unlimited-sentries)
	fi
}

cd "$REPO"

echo "=== Conker War Sentry (War Colors / bg_mp13) ==="
echo "  Stage:  STAGE_EXTRA26 ($BOOT_STAGE) — War Colors / Conker BFD War"
if [[ "$DEPLOY_CUSTOM" == true ]]; then
	echo "  Layout: DEPLOY conker_war_sentry_inf → mp13 slot (64-spawn experiment)"
else
	echo "  Layout: mod_kakariko seg/tiles/pads + Conker Ump_setupmp13Z"
fi
	echo "  Spawn:  12 Conker-valid pads (6 SHC interior / 6 Tediz deep tunnel)"
	echo "  Weapons: 10 Conker-valid pads (5 SHC interior / 5 Tediz deep tunnel)"
echo "  Binary: ${PD#$REPO/}"
echo "  Sims:   $NUM_SIMS $( [[ "$SOLO" == true ]] && echo '(solo human)' || true )"
echo "  Teams:  $TEAMS_BATTLE | Sentry engine flags: $SENTRY_FLAGS"
if [[ "$NUM_SIMS" -ge 16 && "$DEPLOY_CUSTOM" != true ]]; then
	echo "  WARN:   retail mp13 has 12 spawn pads; >12 chrs will reuse pads (use --deploy-custom for 64)"
fi

kill_stale_war_colors

echo "Building pd.arm64 (cmake --build build --target pd -j8)…"
cmake --build build --target pd -j8

remove_mp13_overrides

if [[ "$CLEAN_ONLY" == true ]]; then
	echo "  --clean: overrides purged, not launching"
	exit 0
fi

if [[ "$DEPLOY_CUSTOM" != true ]]; then
	deploy_war_colors_conker
	verify_deployed_setup
fi

if [[ "$DEPLOY_CUSTOM" == true ]]; then
	python3 tools/pdmap.py build conker_war_sentry_inf --deploy
fi

if [[ "$NO_PLAY" == true ]]; then
	echo "  --no-play: setup only"
	exit 0
fi

ensure_rom
build_play_flags

# Hard guard: never launch War Colors with kakarikomoddir pointing at mod_allinone.
if [[ "$KAKARIKO_MODDIR" != "$REPO/mods/mod_kakariko" ]]; then
	echo "ERROR: KAKARIKO_MODDIR must be mods/mod_kakariko (got $KAKARIKO_MODDIR)" >&2
	exit 1
fi

{
	echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) War Colors retail-spawn sims=$NUM_SIMS deploy_custom=$DEPLOY_CUSTOM ==="
	echo "cmd: $PD ${play_parts[*]}"
} >>"$LAST_LOG"

if [[ "$(uname -s)" == "Darwin" ]] && command -v osascript >/dev/null 2>&1; then
	play_cmd="cd $(printf '%q' "$REPO") && $(printf '%q' "$PD")"
	for pf in "${play_parts[@]}"; do
		play_cmd+=" $(printf '%q' "$pf")"
	done
	play_cmd+=" 2>&1 | tee -a $(printf '%q' "$LAST_LOG")"
	osascript - "$play_cmd" <<'APPLESCRIPT' >/dev/null
on run argv
	tell application "Terminal"
		do script (item 1 of argv)
	end tell
end run
APPLESCRIPT

	pgrep_play() {
		local p cmd
		for p in $(pgrep -x pd.arm64 2>/dev/null); do
			cmd="$(ps -p "$p" -o command= 2>/dev/null || true)"
			if [[ "$cmd" == *"$PD"* && "$cmd" == *"--boot-stage"* && "$cmd" == *"$BOOT_STAGE"* ]]; then
				echo "$p"
				return 0
			fi
		done
	}

	play_pid=""
	for _ in $(seq 1 24); do
		play_pid="$(pgrep_play)"
		if [[ -n "$play_pid" ]]; then
			break
		fi
		sleep 0.25
	done
	if [[ -z "$play_pid" ]] && command -v open >/dev/null 2>&1; then
		open_args=(-na "$PD" --args)
		for pf in "${play_parts[@]}"; do
			open_args+=("$pf")
		done
		open "${open_args[@]}"
		for _ in $(seq 1 16); do
			play_pid="$(pgrep_play)"
			if [[ -n "$play_pid" ]]; then
				break
			fi
			sleep 0.25
		done
	fi
	if [[ -n "$play_pid" ]]; then
		echo "$play_pid" >"$LOG_DIR/.last_play.pid"
		osascript >/dev/null 2>&1 <<'APPLESCRIPT' || true
tell application "System Events"
  repeat with i from 1 to 30
    if exists (process "pd.arm64") then
      tell process "pd.arm64" to set frontmost to true
      exit repeat
    end if
    delay 0.2
  end repeat
end tell
APPLESCRIPT
		osascript -e "display notification \"War Colors (mp13) sims=$NUM_SIMS.\" with title \"Perfect Dark — War Sentry\"" >/dev/null 2>&1 || true
	fi
	echo "  game window: separate SDL window titled \"Perfect Dark\""
	if [[ -n "$play_pid" ]]; then
		echo "  pid: $play_pid"
	else
		echo "  pid: (not detected — check pgrep pd.arm64)"
	fi
else
	exec "$PD" "${play_parts[@]}" 2>&1 | tee -a "$LAST_LOG"
fi
