#!/usr/bin/env bash
# Shared Perfect Dark Kit constants for build and launcher scripts.
# Source from other scripts: source "$(dirname "$0")/pd-kit-common.sh"

if [[ -n "${PD_KIT_COMMON_LOADED:-}" ]]; then
	return 0 2>/dev/null || exit 0
fi
PD_KIT_COMMON_LOADED=1

_PD_KIT_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PD_KIT_SCRIPT_DIR="$_PD_KIT_COMMON_DIR"
PD_KIT_REPO_ROOT="$(cd "$_PD_KIT_COMMON_DIR/.." && pwd)"
PD_KIT_MANIFEST="$PD_KIT_REPO_ROOT/tools/pd_kit/kit.json"
PD_KIT_RELEASE_DIR="$PD_KIT_SCRIPT_DIR/release"

read_kit_version() {
	if [[ -f "$PD_KIT_REPO_ROOT/KIT_VERSION" ]]; then
		tr -d '[:space:]' <"$PD_KIT_REPO_ROOT/KIT_VERSION"
	else
		echo "0.0.0"
	fi
}

read_port_version() {
	if [[ -f "$PD_KIT_REPO_ROOT/PORT_VERSION" ]]; then
		tr -d '[:space:]' <"$PD_KIT_REPO_ROOT/PORT_VERSION"
	else
		echo "0.0.0"
	fi
}

kit_json_field() {
	local expr="$1"
	python3 - "$PD_KIT_MANIFEST" "$expr" <<'PY'
import json, sys
manifest = json.load(open(sys.argv[1], encoding="utf-8"))
expr = sys.argv[2]
# expr like apps.mapEditor.bundleFileName
cur = manifest
for part in expr.split("."):
    cur = cur[part]
print(cur)
PY
}

PD_KIT_NAME="$(python3 - "$PD_KIT_MANIFEST" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("name", "Perfect Dark Kit"))
PY
)"
PD_KIT_VERSION="$(read_kit_version)"
PD_PORT_VERSION="$(read_port_version)"

PD_KIT_APP_MAP_EDITOR="$(kit_json_field apps.mapEditor.bundleFileName)"
PD_KIT_APP_ANIM_LAB="$(kit_json_field apps.animLab.bundleFileName)"
PD_KIT_APP_ASSET_UPGRADER="$(kit_json_field apps.assetUpgrader.bundleFileName)"
PD_KIT_APP_HUB="$(kit_json_field apps.kitHub.bundleFileName)"

PD_KIT_SUPPORT_ROOT="${HOME}/Library/Application Support/PerfectDarkKit"
PD_KIT_LOGS_ROOT="${HOME}/Library/Logs/PerfectDarkKit"

write_kit_release_manifest() {
	local pd_binary="${1:-$PD_KIT_REPO_ROOT/build/pd.arm64}"
	python3 - "$PD_KIT_REPO_ROOT" "$PD_KIT_RELEASE_DIR" "$pd_binary" <<'PY'
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path

repo = Path(sys.argv[1])
release = Path(sys.argv[2])
pd_binary = Path(sys.argv[3])
manifest = json.loads((repo / "tools/pd_kit/kit.json").read_text(encoding="utf-8"))
kit_version = (repo / "KIT_VERSION").read_text(encoding="utf-8").strip()
port_version = (repo / "PORT_VERSION").read_text(encoding="utf-8").strip()

apps = {}
for key, cfg in manifest.get("apps", {}).items():
    bundle = cfg.get("bundleFileName", "")
    app_path = release / bundle
    entry = {
        "productName": cfg.get("productName"),
        "bundleFileName": bundle,
        "built": app_path.is_dir(),
        "path": str(app_path),
    }
    if key == "kitHub" and app_path.is_dir():
        wrapped_root = app_path / "Contents" / "Resources" / "Apps"
        wrapped = {}
        for child_key, child_cfg in manifest.get("apps", {}).items():
            if child_key == "kitHub":
                continue
            child_bundle = child_cfg.get("bundleFileName", "")
            wrapped[child_key] = (wrapped_root / child_bundle).is_dir()
        entry["wrappedApps"] = wrapped
    apps[key] = entry

payload = {
    "name": manifest.get("name", "Perfect Dark Kit"),
    "kitVersion": kit_version,
    "portVersion": port_version,
    "builtAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "repoRoot": str(repo),
    "releaseDir": str(release),
    "gameBinary": {
        "path": str(pd_binary),
        "built": pd_binary.is_file(),
    },
    "apps": apps,
}
out = release / manifest.get("release", {}).get("manifestFile", "kit-manifest.json")
out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(out)
PY
}

kit_symlink_app() {
	local bundle_name="$1"
	local bundle_path="$PD_KIT_RELEASE_DIR/$bundle_name"
	if [[ -d "$bundle_path" ]]; then
		ln -sfn "$bundle_path" "$PD_KIT_REPO_ROOT/$bundle_name"
	fi
}

# Remove superseded .app bundles and repo-root symlinks from older naming schemes.
kit_prune_legacy_app_bundles() {
	local legacy=(
		"Perfect Dark Kit — Map Editor.app"
		"Perfect Dark Kit — Animation Lab.app"
		"Perfect Dark Kit — Asset Upgrader.app"
		"Perfect Dark Map Editor.app"
		"Perfect Dark Map Editor (Electron).app"
		"Perfect Dark Map Editor 2.app"
		"Perfect Dark Map Editor 3.app"
		"Perfect Dark Animation Lab.app"
	)
	local name
	for name in "${legacy[@]}"; do
		rm -rf "$PD_KIT_RELEASE_DIR/$name" 2>/dev/null || true
		rm -f "$PD_KIT_REPO_ROOT/$name" 2>/dev/null || true
	done
}

kit_open_app() {
	local bundle_name="$1"
	local bundle_path="$PD_KIT_RELEASE_DIR/$bundle_name"
	if [[ ! -d "$bundle_path" ]]; then
		echo "App not built: $bundle_path" >&2
		echo "Run: ./scripts/build-pd-kit.sh --apps" >&2
		return 1
	fi
	open "$bundle_path"
}
