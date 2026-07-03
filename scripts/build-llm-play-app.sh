#!/usr/bin/env bash
# Delegate LLM Play.app build to the standalone llm-play project.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/llm-play/scripts/build-llm-play-electron.sh" "$@"
