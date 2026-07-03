#!/bin/bash
cd "$(dirname "$0")"
lldb -b -o "run" -o "bt" -o "quit" -- ./build/pd.x86_64 --test-map --scenario=0 > lldb_bt.txt 2>&1 &
PID=$!
sleep 5
osascript -e 'tell application "System Events" to set frontmost of process "pd.x86_64" to true'
sleep 1
osascript -e 'tell application "System Events" to keystroke return'
sleep 2
wait $PID
