#!/bin/bash
cd "$(dirname "$0")"

set -e

echo "=== Building Matrix Test Room (seg + pads + tiles + setup) ==="
python3 tools/pdmap.py build uff --deploy --seg

echo "=== Level info ==="
python3 tools/pdmap.py info uff

echo "=== Rebuilding game binary ==="
cmake --build build --target pd -j4

echo "=== Launching Matrix Test Room ==="
./build/pd.arm64 --test-map --scenario-0 --moddir mods/mod_allinone
