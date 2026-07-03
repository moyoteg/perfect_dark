#!/usr/bin/env bash
# Point Ollama (GUI + CLI + LLM Play) at models on the external dev drive.
#
# Finder-launched apps do not read ~/.zshrc; they use ~/.ollama/models unless
# OLLAMA_MODELS is set via launchctl. This script symlinks both paths to the same
# external store and repairs stale "2TEx Dev" symlinks after a volume rename.

set -euo pipefail

# Override with PD_OLLAMA_MODELS or OLLAMA_MODELS if already set.
pd_ollama_external_root() {
	if [[ -n "${PD_OLLAMA_MODELS:-}" ]]; then
		printf '%s' "$PD_OLLAMA_MODELS"
		return 0
	fi
	if [[ -n "${OLLAMA_MODELS:-}" && -d "${OLLAMA_MODELS}" ]]; then
		printf '%s' "$OLLAMA_MODELS"
		return 0
	fi
	printf '%s' "/Volumes/4TEx Dev main/LLM-Data/ollama-models"
}

pd_ollama_app_support_root() {
	local models_root
	models_root="$(pd_ollama_external_root)"
	printf '%s' "$(dirname "$models_root")/ollama-app-support"
}

# Replace a symlink if it is missing, broken, or still points at the old 2TEx volume.
pd_ollama_fix_symlink() {
	local link_path="$1"
	local target_path="$2"
	local parent_dir current

	parent_dir="$(dirname "$link_path")"
	mkdir -p "$parent_dir"

	if [[ -L "$link_path" ]]; then
		current="$(readlink "$link_path" 2>/dev/null || true)"
		if [[ "$current" == "$target_path" && -e "$link_path" ]]; then
			return 0
		fi
		rm "$link_path"
	elif [[ -e "$link_path" ]]; then
		# Empty ~/.ollama/models dirs are replaced by the external symlink.
		if [[ -d "$link_path" ]] && [[ -z "$(ls -A "$link_path" 2>/dev/null || true)" ]]; then
			rmdir "$link_path"
		else
			echo "Refusing to replace non-empty path (not a symlink): $link_path" >&2
			return 1
		fi
	fi

	ln -sfn "$target_path" "$link_path"
}

# Wire Application Support + ~/.ollama/models; export OLLAMA_MODELS for this shell.
pd_ensure_ollama_external_drive() {
	local models_root app_support_root
	models_root="$(pd_ollama_external_root)"
	app_support_root="$(pd_ollama_app_support_root)"

	if [[ ! -d "/Volumes/4TEx Dev main" ]]; then
		echo "External dev drive is not mounted (expected: /Volumes/4TEx Dev main)." >&2
		return 1
	fi

	mkdir -p "$models_root/manifests" "$models_root/blobs" "$app_support_root"

	pd_ollama_fix_symlink "${HOME}/Library/Application Support/Ollama" "$app_support_root"
	pd_ollama_fix_symlink "${HOME}/.ollama/models" "$models_root"

	export OLLAMA_MODELS="$models_root"
	# GUI apps (Ollama menu bar, LLM Play.app) inherit this for the login session.
	if command -v launchctl >/dev/null 2>&1; then
		launchctl setenv OLLAMA_MODELS "$models_root" 2>/dev/null || true
	fi

	printf '%s' "$models_root"
}

# Return 0 when gemma3:4b (or OLLAMA_MODEL) is registered in the running server.
pd_ollama_model_ready() {
	local model="${OLLAMA_MODEL:-gemma3:4b}"
	local tags
	tags="$(curl -sf --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null || true)"
	[[ -n "$tags" ]] || return 1
	python3 -c 'import json,sys; m=sys.argv[1]; tags=json.loads(sys.argv[2]).get("models",[]); sys.exit(0 if any(x.get("name","").startswith(m) for x in tags) else 1)' "$model" "$tags" 2>/dev/null
}
