#!/usr/bin/env bash
# Stop the Telegram bot. Safe to run when nothing's running.
set -euo pipefail
cd "$(dirname "$0")/.."

if pkill -f "src/bot/telegram_app.py" 2>/dev/null; then
  sleep 1
  pkill -9 -f "src/bot/telegram_app.py" 2>/dev/null || true
  rm -f data/bot.pid
  echo "✓ Bot stopped"
else
  echo "(no bot running)"
fi
