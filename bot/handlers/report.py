import os
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes
from core.database import get_entries
from generate_logsheet import generate_for_user
from datetime import datetime
from bot.keyboards import to_bn_number
from bot.strings import S
from bot.auth import require_auth

async def generate_report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_auth(update, context): return
    query = update.callback_query
    if query:
        await query.answer()
    
    month, year = None, None
    if query and query.data and query.data.startswith("generate_"):
        parts = query.data.split("_")
        if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
            year, month = int(parts[1]), int(parts[2])
    
    if not month or not year:
        now = datetime.now()
        month, year = now.month, now.year
    
    user_id = update.effective_user.id
    entries = await get_entries(user_id, month, year)
    if not entries:
        msg = S('report.no_entries', month=to_bn_number(month), year=to_bn_number(year))
        if query:
            await query.edit_message_text(msg, parse_mode='HTML')
        else:
            await update.message.reply_text(msg, parse_mode='HTML')
        return

    try:
        output_path = generate_for_user(
            user_id=user_id,
            entries=entries,
            month=month,
            year=year,
            tpl_dir=Path("generated_logsheets"),
            out_dir=Path("outputs"),
        )
        
        filename = os.path.basename(output_path)
        with open(output_path, 'rb') as f:
            msg = S('report.success', month=to_bn_number(month), year=to_bn_number(year))
            if query:
                await query.message.reply_document(document=f, filename=filename, caption=msg, parse_mode='HTML')
            else:
                await update.message.reply_document(document=f, filename=filename, caption=msg, parse_mode='HTML')
    except Exception as e:
        error_msg = S('report.error', error=str(e))
        if query:
            await query.edit_message_text(error_msg, parse_mode='HTML')
        else:
            await update.message.reply_text(error_msg, parse_mode='HTML')
