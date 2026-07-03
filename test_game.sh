#!/bin/bash
./pd.arm64 --rom ntsc-final --play-scenario 0 > scratch_output.txt 2>&1 &
PID=$!
sleep 15
kill $PID
