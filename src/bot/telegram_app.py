"""Build + run the Telegram bot via long-polling (§0 scope — the demo runtime).

python-telegram-bot is imported here only, so the rest of the bot package stays
import-safe for tests. Run (from repo root):
    PYTHONPATH=.:src python src/bot/telegram_app.py
"""
from __future__ import annotations

import config
from bot import handlers


def build_app():
    """Construct the PTB Application with all handlers registered."""
    from telegram.ext import Application, CommandHandler, MessageHandler, filters

    # concurrent_updates: PTB awaits each handler to completion before taking the
    # next update otherwise — 20 users would form a serial queue behind one
    # ~7s answer. With it, updates dispatch concurrently; the blocking answer
    # core itself runs on handlers._EXECUTOR (see on_text).
    app = (Application.builder()
           .token(config.TELEGRAM_BOT_TOKEN)
           .concurrent_updates(True)
           .build())
    app.add_handler(CommandHandler("start", handlers.on_start))
    app.add_handler(CommandHandler("help", handlers.on_help))
    app.add_handler(CommandHandler("reset", handlers.on_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.on_text))
    app.add_handler(MessageHandler(~filters.TEXT, handlers.on_nontext))
    return app


def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env (from @BotFather).")
    # drop_pending_updates clears Telegram's server-side queue from any previous
    # instance so a fresh start doesn't immediately race with a stale long-poll
    # claim (the "Conflict: terminated by other getUpdates request" failure).
    build_app().run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
