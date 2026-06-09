#!/usr/bin/env bash
# Start the Telegram bot in the background (detached). Idempotent: kills any
# existing bot first. Survives terminal close (nohup) but NOT macOS sleep — keep
# the laptop awake with `caffeinate -d -i` in another terminal during a demo.
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p data
# Kill cleanly, then SIGKILL stragglers, then wait for Telegram's side to release
# the long-poll claim (else the new instance hits a Conflict: terminated by other
# getUpdates request and silently fails to serve).
if pkill -f "src/bot/telegram_app.py" 2>/dev/null; then
  sleep 2
  pkill -9 -f "src/bot/telegram_app.py" 2>/dev/null || true
  sleep 3   # let Telegram release the previous getUpdates claim
fi

PYTHONPATH=.:src nohup .venv/bin/python3 -u src/bot/telegram_app.py \
  > data/bot.log 2>&1 &
pid=$!
disown "$pid" 2>/dev/null || true
echo "$pid" > data/bot.pid

sleep 2
if kill -0 "$pid" 2>/dev/null; then
  echo "✓ Bot started: pid $pid"
  echo "  log:  tail -f data/bot.log"
  echo "  stop: scripts/stop_bot.sh   ·   status: scripts/status_bot.sh"
else
  echo "✗ Bot failed to start within 2s; check data/bot.log"
  tail -20 data/bot.log
  exit 1
fi
