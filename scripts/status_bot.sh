#!/usr/bin/env bash
# Status check + last log lines. Exit 0 if running, 1 if not — usable in shell pipelines.
set -euo pipefail
cd "$(dirname "$0")/.."

if pgrep -f "src/bot/telegram_app.py" > /dev/null; then
  echo "✓ Bot is running:"
  ps -o pid,etime,rss,command -p "$(pgrep -f 'src/bot/telegram_app.py')" | head -5
  echo ""
  echo "Last 8 log lines:"
  tail -8 data/bot.log 2>/dev/null || echo "  (log empty)"
else
  echo "✗ Bot is NOT running."
  echo "Last 15 log lines:"
  tail -15 data/bot.log 2>/dev/null || echo "  (no log yet)"
  exit 1
fi
