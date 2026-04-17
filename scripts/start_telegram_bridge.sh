#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

LOG_FILE="$REPO_ROOT/logs/telegram_bridge.log"
mkdir -p "$REPO_ROOT/logs"

# Load .env without BOM issues
if [ -f "$REPO_ROOT/.env" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        # Strip BOM, carriage returns, and skip comments/blanks
        line="${line#$'\xef\xbb\xbf'}"
        line="${line//$'\r'/}"
        [[ -z "$line" || "$line" == \#* ]] && continue
        export "$line"
    done < "$REPO_ROOT/.env"
fi

echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Starting telegram_bridge.py ..." >> "$LOG_FILE"

PYTHON="/c/Users/james/AppData/Local/Programs/Python/Python311/python"

nohup "$PYTHON" "$REPO_ROOT/scripts/telegram_bridge.py" \
    >> "$LOG_FILE" 2>&1 &

PID=$!
echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Launched with PID $PID" >> "$LOG_FILE"
echo "Started telegram_bridge.py — PID $PID"
echo "Log: $LOG_FILE"
