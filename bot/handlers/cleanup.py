import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from bot.text_resources import S
from bot.auth import require_auth
from core.message_store import get_all_temporary, get_all_files, get_log, save_log


async def clean_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_auth(update, context): return
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    deleted = 0
    cmd_msg_id = update.message.message_id if update.message else None

    # Phase 1: Delete the user's /clean command message
    if cmd_msg_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=cmd_msg_id)
            deleted += 1
        except Exception:
            pass

    # Phase 2: Delete all tracked temporary messages (from any chat)
    temps = await get_all_temporary(user_id)
    for t in temps:
        try:
            await context.bot.delete_message(chat_id=t['chat_id'], message_id=t['msg_id'])
            deleted += 1
        except Exception:
            pass

    # Phase 3: Delete all tracked file messages from user chat
    files = await get_all_files(user_id)
    for f in files:
        try:
            await context.bot.delete_message(chat_id=f['chat_id'], message_id=f['msg_id'])
            deleted += 1
        except Exception:
            pass

    # Wipe the entire message store for this user
    log = await get_log(user_id)
    log['temporary'] = []
    log['files'] = []
    await save_log(user_id, log)

    # Phase 4: Brute-force scan — delete every message we can find
    if cmd_msg_id:
        scan_start = max(cmd_msg_id - 500, 1)
        for mid in range(cmd_msg_id, scan_start - 1, -1):
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=mid)
                deleted += 1
            except Exception:
                pass

    # Phase 5: Self-destructing confirmation (visible for 3 seconds)
    try:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=S('clean.done', count=str(deleted)),
            parse_mode='HTML'
        )
        await asyncio.sleep(3)
        await context.bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
    except Exception:
        pass
