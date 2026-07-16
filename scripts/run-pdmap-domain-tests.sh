#!/usr/bin/env bash
# Production gate: all pdmap domain unit tests (13 modules) + curriculum validate 31/31.
#
# Usage:
#   ./scripts/run-pdmap-domain-tests.sh
#
# Exit 0 when every module prints "ok" and curriculum is 31/31; non-zero on first failure.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

# Production scenario test skips nested gate subprocess when already inside this gate.
export PDMAP_DOMAIN_GATE=1

fail() {
	echo "FAIL: $*" >&2
	exit 1
}

pass() {
	echo "PASS: $*"
}

TEST_MODULES=(
	tests/test_pdmap_validation_domain.py
	tests/test_pdmap_build_domain.py
	tests/test_pdmap_pipeline_domain.py
	tests/test_pdmap_deploy_domain.py
	tests/test_pdmap_curriculum_domain.py
	tests/test_pdmap_failure_scenarios.py
	tests/test_pdmap_dependency_failures.py
	tests/test_pdmap_limit_reached.py
	tests/test_pdmap_build_timeout.py
	tests/test_pdmap_build_retry.py
	tests/test_pdmap_legacy_path_observability.py
	tests/test_pdmap_production_scenario.py
	tests/test_pdmap_regression_catalog.py
	tests/test_serve_animlab.py
)

for module in "${TEST_MODULES[@]}"; do
	[[ -f "$module" ]] || fail "missing test module: $module"
	echo "==> python3 $module"
	output="$(python3 "$module" 2>&1)" || fail "$module exited non-zero"
	echo "$output"
	echo "$output" | rg -q '^ok$' || fail "$module did not print ok"
	pass "$module"
done

echo "==> curriculum validate 31/31"
python3 - <<'PY' || fail "curriculum validate"
from tools.pdmap.learn.curriculum import validate_curriculum

results = validate_curriculum(verbose=True)
bad = [x for x in results if not x.ok]
if bad:
    for item in bad:
        print(f"FAIL step {item.step}: {item.message}")
    raise SystemExit(1)
print(f"{len(results)}/31 steps OK")
PY

pass "curriculum validate 31/31"
echo "PASS: pdmap domain test gate"
