#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <package-tar-gz-path>" >&2
  exit 2
fi

bundle="$1"

if [[ ! -f "$bundle" ]]; then
  echo "Package not found: $bundle" >&2
  exit 2
fi

tmp_list="$(mktemp)"
trap 'rm -f "$tmp_list"' EXIT

tar -tzf "$bundle" | sort > "$tmp_list"

if grep -E '(^|/)(src/assets/|.*\.z64$|.*\.n64$|.*\.v64$)' "$tmp_list" >/dev/null 2>&1; then
  echo "Forbidden payload detected in package: proprietary ROM/assets content pattern matched." >&2
  grep -E '(^|/)(src/assets/|.*\.z64$|.*\.n64$|.*\.v64$)' "$tmp_list" >&2 || true
  exit 1
fi

echo "verify_package_contents: PASS"
exit 0
