#!/bin/bash
set -e
make -C build -j8

for i in 0 1 2 3 4 5; do
  echo "Testing Scenario $i..."
  ./build/pd.arm64 --test-map --scenario-$i > "game_run_scen_$i.log" 2>&1 &
  PID=$!
  sleep 4
  
  if kill -0 $PID 2>/dev/null; then
    echo "Scenario $i successfully ran without crashing!"
    kill $PID
  else
    echo "ERROR: Scenario $i CRASHED!"
    cat "game_run_scen_$i.log"
    exit 1
  fi
done

echo "ALL SCENARIOS PASSED!"
