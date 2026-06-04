from telegram import Update
from telegram.ext import ContextTypes
from bot.inline_keyboards import to_bn_number
from bot.text_resources import S
from bot.auth import require_auth
from core.message_store import get_all_temporary, get_all_files, clear_all_except_files

async def clean_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_auth(update, context): return
    user_id = update.effective_user.id

    temps = await get_all_temporary(user_id)
    deleted = 0
    for t in temps:
        try:
            await context.bot.delete_message(chat_id=t['chat_id'], message_id=t['msg_id'])
            deleted += 1
        except Exception:
            pass

    await clear_all_except_files(user_id)

    files = await get_all_files(user_id)
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
