#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_PATH="$REPO_ROOT/PerfectDarkAIO.app/Contents/MacOS/perfectdark-launcher"

clang \
	-Os \
	"$SCRIPT_DIR/perfectdark-app-stub.c" \
	-o "$OUTPUT_PATH"

printf 'Wrote %s\n' "$OUTPUT_PATH"
