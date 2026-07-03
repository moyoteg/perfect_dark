#!/bin/bash
set -e
make -C build -j8 > /dev/null

echo "Starting game in background..."
./build/pd.arm64 --test-map --scenario-0 > game_freeze.log 2>&1 &
PID=$!

echo "Waiting 3 seconds..."
sleep 3

# Check if process is still alive
if kill -0 $PID 2>/dev/null; then
  echo "Process is still alive. Getting backtrace to see what it's doing..."
  lldb -p $PID --batch -o "bt" -o "quit" > lldb_freeze.log
  kill -9 $PID
  
  if grep -q "cdCollectGeoForCylFromList" lldb_freeze.log; then
    echo "ERROR: Process is still hanging in cdCollectGeoForCylFromList!"
    cat lldb_freeze.log
    exit 1
  elif grep -q "mainLoop" lldb_freeze.log; then
    echo "SUCCESS: Process is naturally running in mainLoop without hanging!"
    cat lldb_freeze.log
    exit 0
  else
    echo "UNKNOWN STATE:"
    cat lldb_freeze.log
    exit 1
  fi
else
  echo "Process exited unexpectedly!"
  cat game_freeze.log
  exit 1
fi
