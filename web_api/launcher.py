"""Run the Telegram bot and the FastAPI server in one Render process.

The bot's polling loop runs in a background thread; uvicorn runs in the
foreground binding to $PORT so Render's health check passes.
"""
import os
import threading
import logging
import asyncio

import uvicorn

os.environ["SKIP_HEALTH_SERVER"] = "1"  # bot/main.py honors this

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("launcher")


def _run_bot():
    # New event loop for this thread (PTB uses asyncio internally).
    asyncio.set_event_loop(asyncio.new_event_loop())
    try:
        from bot.main import main as bot_main
        log.info("Starting Telegram bot in background thread...")
        bot_main()
    except Exception as e:
        log.exception("Bot crashed: %s", e)


def main():
    if os.getenv("DISABLE_BOT") != "1":
        t = threading.Thread(target=_run_bot, daemon=True, name="telegram-bot")
        t.start()
    port = int(os.getenv("PORT", "8080"))
    log.info("Starting FastAPI on port %d", port)
    uvicorn.run("web_api.main:app", host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
