#!/bin/bash
cd "$(dirname "$0")"
./build/pd.x86_64 --test-map --scenario=0
