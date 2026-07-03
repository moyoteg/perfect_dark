#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <release-dir>" >&2
  exit 2
fi

release_dir="$1"

if [[ ! -d "$release_dir" ]]; then
  echo "Release dir not found: $release_dir" >&2
  exit 2
fi

(
  cd "$release_dir"
  sha256sum \
    artifacts/*.tar.gz \
    release_notes.md \
    test_summary.txt \
    manifest.json \
    evidence/test_suite_step0024.log \
    evidence/package_filelist.txt \
    > checksums.sha256
)

echo "generate_checksums: PASS"
exit 0
