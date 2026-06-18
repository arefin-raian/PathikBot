"""Scheduled Render service restart with Telegram status messages.

Every RESTART_INTERVAL_HOURS, sends "🔄 Restarting…" to ADMIN_CHAT_ID,
calls Render's restart API, and on next boot deletes that message,
sends "✅ Restarted", waits 5s, then deletes it too.

Required env vars:
    RENDER_API_KEY          - Render account API key
    RENDER_SERVICE_ID       - srv-xxxxx of the bot service
    ADMIN_CHAT_ID           - Telegram chat id that receives the messages
Optional:
    RESTART_INTERVAL_HOURS  - default "12"
"""
import asyncio
import logging
import os
from datetime import datetime

import httpx

from core.mongo_db import get_db

log = logging.getLogger(__name__)

_COLLECTION = "bot_restart_state"
_DOC_ID = "singleton"


def _config():
    api_key = os.getenv("RENDER_API_KEY")
    service_id = os.getenv("RENDER_SERVICE_ID")
    chat_raw = os.getenv("ADMIN_CHAT_ID")
    interval = float(os.getenv("RESTART_INTERVAL_HOURS", "12"))
    if not (api_key and service_id and chat_raw):
        return None
    try:
        chat_id = int(chat_raw)
    except ValueError:
        log.warning("ADMIN_CHAT_ID is not a valid integer; restart scheduler disabled")
        return None
    return {
        "api_key": api_key,
        "service_id": service_id,
        "chat_id": chat_id,
        "interval_seconds": interval * 3600,
    }


async def _save_pending(chat_id: int, message_id: int):
    db = await get_db()
    if db is None:
        return
    await db[_COLLECTION].update_one(
        {"_id": _DOC_ID},
        {"$set": {
            "pending_chat_id": chat_id,
            "pending_message_id": message_id,
            "updated_at": datetime.utcnow().isoformat(),
        }},
        upsert=True,
    )


async def _get_pending():
    db = await get_db()
    if db is None:
        return None
    return await db[_COLLECTION].find_one({"_id": _DOC_ID})


async def _clear_pending():
    db = await get_db()
    if db is None:
        return
    await db[_COLLECTION].update_one(
        {"_id": _DOC_ID},
        {"$set": {"pending_chat_id": None, "pending_message_id": None}},
        upsert=True,
    )


async def _trigger_render_restart(cfg):
    url = f"https://api.render.com/v1/services/{cfg['service_id']}/restart"
    async with httpx.AsyncClient(timeout=20) as c:
        resp = await c.post(
            url, headers={"Authorization": f"Bearer {cfg['api_key']}"}
        )
        resp.raise_for_status()


async def scheduled_restart_loop(bot):
    """Forever loop: sleep N hours, announce, trigger Render restart."""
    cfg = _config()
    if not cfg:
        log.info("Restart scheduler disabled (missing env vars)")
        return

    log.info(
        "Restart scheduler armed: every %.1f h, chat=%s, service=%s",
        cfg["interval_seconds"] / 3600, cfg["chat_id"], cfg["service_id"],
    )

    while True:
        try:
            await asyncio.sleep(cfg["interval_seconds"])
            msg = await bot.send_message(cfg["chat_id"], "🔄 Restarting…")
            await _save_pending(cfg["chat_id"], msg.message_id)
            try:
                await _trigger_render_restart(cfg)
                log.info("Render restart requested; awaiting process termination")
            except Exception as e:
                log.exception("Render restart API call failed: %s", e)
                # tidy up the message so the user isn't left with a stale "restarting"
                try:
                    await bot.delete_message(cfg["chat_id"], msg.message_id)
                except Exception:
                    pass
                await _clear_pending()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("scheduled_restart_loop iteration failed: %s", e)
            # avoid hot-spin
            await asyncio.sleep(60)


async def handle_post_restart(bot):
    """Run once on startup: clean up the pending 'Restarting…' message."""
    try:
        state = await _get_pending()
        if not state or not state.get("pending_message_id"):
            return
        chat_id = state.get("pending_chat_id")
        old_msg_id = state.get("pending_message_id")
        if chat_id and old_msg_id:
            try:
                await bot.delete_message(chat_id, old_msg_id)
            except Exception:
                pass
            try:
                done = await bot.send_message(chat_id, "✅ Restarted")
                await asyncio.sleep(5)
                try:
                    await bot.delete_message(chat_id, done.message_id)
                except Exception:
                    pass
            except Exception as e:
                log.warning("post-restart confirmation failed: %s", e)
        await _clear_pending()
    except Exception as e:
        log.warning("handle_post_restart failed: %s", e)
