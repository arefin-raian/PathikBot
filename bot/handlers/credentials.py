"""/credentials command — issue or rotate web-login credentials."""
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.auth import require_auth
from bot.text_resources import S
from core.credentials import issue_credentials

# Auto-delete the credentials message (and the user's /credentials command)
# after this many seconds, to keep secrets out of Telegram history.
AUTO_DELETE_SECONDS = 120


async def _delete_later(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_ids: list[int], delay: int):
    try:
        await asyncio.sleep(delay)
        for mid in message_ids:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=mid)
            except Exception as e:
                logging.debug("credentials auto-delete: failed to delete %s: %s", mid, e)
    except Exception as e:
        logging.warning("credentials auto-delete task crashed: %s", e)


async def credentials_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_auth(update, context):
        return
    user = update.effective_user
    try:
        email, password = await issue_credentials(
            user.id,
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            username=user.username or "",
        )
    except Exception as e:
        await update.effective_message.reply_text(
            S("credentials.failed", error=str(e)), parse_mode="HTML"
        )
        return

    text = S("credentials.issued", email=email, password=password)
    sent = await update.effective_message.reply_text(text, parse_mode="HTML")

    chat_id = update.effective_chat.id
    msg_ids = [sent.message_id]
    if update.message and update.message.message_id:
        msg_ids.append(update.message.message_id)

    asyncio.create_task(_delete_later(context, chat_id, msg_ids, AUTO_DELETE_SECONDS))
