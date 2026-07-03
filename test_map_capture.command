#!/bin/bash
cd "$(dirname "$0")"
./build/pd.arm64 --test-map --scenario-0 --moddir mods/mod_allinone > debug_pos.log 2>&1 &
PID=$!
sleep 6
/Users/moigutierrez/.gemini/antigravity/brain/b54d3ef0-4ba8-4a8a-8ee8-bacc333e16b6/scratch/bring_to_front $PID
sleep 2
screencapture -x /Users/moigutierrez/.gemini/antigravity/brain/b54d3ef0-4ba8-4a8a-8ee8-bacc333e16b6/game_screenshot_FINAL.png
sleep 3
kill $PID
