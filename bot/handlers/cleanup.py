import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from bot.inline_keyboards import to_bn_number
from bot.text_resources import S
from bot.auth import require_auth
from core.message_store import get_all_temporary, get_all_files, clear_all_except_files

async def clean_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_auth(update, context): return
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Phase 1: delete all tracked temporary messages
    temps = await get_all_temporary(user_id)
    deleted = 0
    protected_ids = set()
    files = await get_all_files(user_id)
    for f in files:
        protected_ids.add(f['msg_id'])

    for t in temps:
        if t['msg_id'] in protected_ids:
            continue
        try:
            await context.bot.delete_message(chat_id=t['chat_id'], message_id=t['msg_id'])
            deleted += 1
        except Exception:
            pass

    await clear_all_except_files(user_id)

    # Phase 2: brute-force scan for untracked bot messages
    # Try deleting from current_msg_id - 1 down to 1
    # Skip protected file messages
    # Move up to 500 messages back (Telegram rate limit safe)
    if update.message:
        current_id = update.message.message_id
        scan_start = max(current_id - 500, 1)
        for mid in range(current_id - 1, scan_start - 1, -1):
            if mid in protected_ids:
                continue
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=mid)
                deleted += 1
            except Exception:
                pass

    # Phase 3: update file captions with metadata
    now_str = __import__('datetime').datetime.now()
    for f in files:
        month_bn = to_bn_number(str(f['month']).zfill(2))
        year_bn = to_bn_number(str(f['year']))
        ts = now_str.strftime('%d-%m-%Y at %H:%M')
        meta = (
            f"📄 Logsheet — {month_bn}/{year_bn}"
            f"\n📅 Generated: {to_bn_number(ts)}"
        )
        try:
            await context.bot.edit_message_caption(
                chat_id=f['chat_id'], message_id=f['msg_id'],
                caption=meta, parse_mode='HTML'
            )
        except Exception:
            pass

    msg = S('clean.done', count=to_bn_number(deleted))
    await update.message.reply_text(msg, parse_mode='HTML')
