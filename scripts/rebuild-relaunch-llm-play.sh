#!/usr/bin/env bash
# Delegate rebuild/relaunch to the standalone llm-play project.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/llm-play/scripts/rebuild-relaunch-llm-play.sh" "$@"
