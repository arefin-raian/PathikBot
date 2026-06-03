import os
from telegram import Update
from telegram.ext import ContextTypes
from core.database import get_entries
from docx_generator.generator import LogsheetGenerator
from datetime import datetime
from bot.keyboards import to_bn_number
from bot.strings import S

async def generate_report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    entries = await get_entries(month, year)
    if not entries:
        msg = S('report.no_entries', month=to_bn_number(month), year=to_bn_number(year))
        if query:
            await query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return

    os.makedirs("output", exist_ok=True)
    filename = f"Logsheet_{year}_{month:02d}.docx"
    output_path = os.path.join("output", filename)
    
    generator = LogsheetGenerator()
    try:
        generator.generate_report(entries, month, year, output_path)
        
        with open(output_path, 'rb') as f:
            msg = S('report.success', month=to_bn_number(month), year=to_bn_number(year))
            if query:
                await query.message.reply_document(document=f, filename=filename, caption=msg)
            else:
                await update.message.reply_document(document=f, filename=filename, caption=msg)
    except Exception as e:
        error_msg = S('report.error', error=str(e))
        if query:
            await query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)
