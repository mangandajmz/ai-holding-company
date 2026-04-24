#!/bin/bash
set -a
source .env
set +a
nohup python3 scripts/aiogram_bridge.py > logs/aiogram_bridge.log 2>&1 &
echo $!
