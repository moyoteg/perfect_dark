#!/bin/bash
cd "$(dirname "$0")"
./build/pd.x86_64 --test-map --scenario=0 &
sleep 5
osascript -e 'tell application "System Events" to keystroke return'
wait
