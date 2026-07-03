#!/bin/bash
cd "$(dirname "$0")"
./pd.arm64 --test-map --scenario=0 --moddir mods/mod_allinone > game_run_capture.log 2>&1 &
PID=$!
sleep 10
screencapture -x game_screenshot_30.png
kill $PID
