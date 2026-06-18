"""Scheduled Render service restart with Telegram status messages.

Every RESTART_INTERVAL_HOURS, broadcasts "🔄 Restarting…" to ALL registered
users, calls Render's restart API, and on next boot deletes those messages,
sends "✅ Restarted" to each, waits 5s, then deletes those too.

Required env vars:
    RENDER_API_KEY          - Render account API key
    RENDER_SERVICE_ID       - srv-xxxxx of the bot service
Optional:
    ADMIN_CHAT_ID           - extra chat id that always receives the messages
                              (in case it isn't already in the users store)
    RESTART_INTERVAL_HOURS  - default "12"
"""
import asyncio
import logging
import os
from datetime import datetime

import httpx

from core.mongo_db import get_db
from core.file_data_store import get_all_users

log = logging.getLogger(__name__)

_COLLECTION = "bot_restart_state"
_DOC_ID = "singleton"


def _config():
    api_key = os.getenv("RENDER_API_KEY")
    service_id = os.getenv("RENDER_SERVICE_ID")
    interval = float(os.getenv("RESTART_INTERVAL_HOURS", "12"))
    if not (api_key and service_id):
        return None
    admin_chat_id = None
    chat_raw = os.getenv("ADMIN_CHAT_ID")
    if chat_raw:
        try:
            admin_chat_id = int(chat_raw)
        except ValueError:
            log.warning("ADMIN_CHAT_ID is not a valid integer; ignoring")
    return {
        "api_key": api_key,
        "service_id": service_id,
        "admin_chat_id": admin_chat_id,
        "interval_seconds": interval * 3600,
    }


async def _recipient_chat_ids(admin_chat_id):
    """Return a deduped list of chat ids to notify."""
    chat_ids = []
    seen = set()
    try:
        users = await get_all_users() or {}
        for uid in users.keys():
            try:
                cid = int(uid)
            except (TypeError, ValueError):
                continue
            if cid not in seen:
                seen.add(cid)
                chat_ids.append(cid)
    except Exception as e:
        log.warning("Failed to load users for restart broadcast: %s", e)
    if admin_chat_id and admin_chat_id not in seen:
        chat_ids.append(admin_chat_id)
    return chat_ids


async def _save_pending(pairs):
    """Store the list of (chat_id, message_id) pairs to clean up after restart."""
    db = await get_db()
    if db is None:
        return
    await db[_COLLECTION].update_one(
        {"_id": _DOC_ID},
        {"$set": {
            "pending": [{"chat_id": c, "message_id": m} for c, m in pairs],
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
        {"$set": {"pending": [], "pending_chat_id": None, "pending_message_id": None}},
        upsert=True,
    )


async def _trigger_render_restart(cfg):
    url = f"https://api.render.com/v1/services/{cfg['service_id']}/restart"
    async with httpx.AsyncClient(timeout=20) as c:
        resp = await c.post(
            url, headers={"Authorization": f"Bearer {cfg['api_key']}"}
        )
        resp.raise_for_status()


async def _broadcast(bot, chat_ids, text):
    """Send `text` to every chat id; return list of (chat_id, message_id) for successes."""
    pairs = []
    for cid in chat_ids:
        try:
            msg = await bot.send_message(cid, text)
            pairs.append((cid, msg.message_id))
        except Exception as e:
            log.warning("broadcast to %s failed: %s", cid, e)
    return pairs


async def _delete_many(bot, pairs):
    for cid, mid in pairs:
        try:
            await bot.delete_message(cid, mid)
        except Exception:
            pass


async def scheduled_restart_loop(bot):
    """Forever loop: sleep N hours, announce to all users, trigger Render restart."""
    cfg = _config()
    if not cfg:
        log.info("Restart scheduler disabled (missing env vars)")
        return

    log.info(
        "Restart scheduler armed: every %.1f h, service=%s, admin=%s",
        cfg["interval_seconds"] / 3600, cfg["service_id"], cfg["admin_chat_id"],
    )

    while True:
        try:
            await asyncio.sleep(cfg["interval_seconds"])
            chat_ids = await _recipient_chat_ids(cfg["admin_chat_id"])
            if not chat_ids:
                log.info("No recipients for restart broadcast; skipping cycle")
                continue
            pairs = await _broadcast(bot, chat_ids, "🔄 Restarting…")
            await _save_pending(pairs)
            try:
                await _trigger_render_restart(cfg)
                log.info("Render restart requested; awaiting process termination")
            except Exception as e:
                log.exception("Render restart API call failed: %s", e)
                await _delete_many(bot, pairs)
                await _clear_pending()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("scheduled_restart_loop iteration failed: %s", e)
            await asyncio.sleep(60)


async def handle_post_restart(bot):
    """Run once on startup: clean up the pending 'Restarting…' messages and confirm."""
    try:
        state = await _get_pending()
        if not state:
            return
        pairs = []
        for entry in state.get("pending", []) or []:
            cid = entry.get("chat_id")
            mid = entry.get("message_id")
            if cid and mid:
                pairs.append((cid, mid))
        # Backward compatibility with the old single-message format
        legacy_cid = state.get("pending_chat_id")
        legacy_mid = state.get("pending_message_id")
        if legacy_cid and legacy_mid and (legacy_cid, legacy_mid) not in pairs:
            pairs.append((legacy_cid, legacy_mid))

        if not pairs:
            return

        await _delete_many(bot, pairs)

        confirm_pairs = []
        for cid, _ in pairs:
            try:
                done = await bot.send_message(cid, "✅ Restarted")
                confirm_pairs.append((cid, done.message_id))
            except Exception as e:
                log.warning("post-restart confirmation to %s failed: %s", cid, e)

        await asyncio.sleep(5)
        await _delete_many(bot, confirm_pairs)
        await _clear_pending()
    except Exception as e:
        log.warning("handle_post_restart failed: %s", e)
