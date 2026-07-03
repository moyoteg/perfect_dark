#!/usr/bin/env bash
# Symlink the base ROM from your Google Drive N64 Decomp folder into the repo root
# so make extract and make -j can run without copying the file.
# Override source with: PD_ROM_SOURCE=/path/to/pd.ntsc-final.z64 ./scripts/link-rom.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ROM_NAME="pd.ntsc-final.z64"

if [[ -n "$PD_ROM_SOURCE" ]]; then
  SRC="$PD_ROM_SOURCE"
else
  DRIVE="$HOME/Library/CloudStorage/GoogleDrive-moyoteg@gmail.com/My Drive/Games/N64 Decomp"
  SRC="$DRIVE/PerfectDarkShared/$ROM_NAME"
fi

if [[ ! -f "$SRC" ]]; then
  echo "ROM not found: $SRC"
  echo "Set PD_ROM_SOURCE to a different path if needed."
  exit 1
fi

cd "$REPO_ROOT"
ln -sf "$SRC" "$ROM_NAME"
echo "Linked $ROM_NAME -> $SRC"
