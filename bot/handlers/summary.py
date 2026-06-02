from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.database import get_entries
from core.calculations import calculate_summary
from bot.keyboards import to_bn_number
from datetime import datetime

BACK_TO_MENU = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মূল মেনু", callback_data="main_menu")]])

async def list_entries_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    year, month = None, None
    if query:
        await query.answer()
        if query.data.startswith("list_entries_"):
            parts = query.data.split("_")
            year, month = int(parts[2]), int(parts[3])
    
    entries = await get_entries(month, year)
    if not entries:
        msg = "কোনো এন্ট্রি পাওয়া যায়নি।"
        if query:
            await query.edit_message_text(msg, reply_markup=BACK_TO_MENU)
        else:
            await update.message.reply_text(msg, reply_markup=BACK_TO_MENU)
        return
        
    text = ""
    # If filtered, show all. If not, show last 10
    display_entries = entries if (month and year) else entries[-10:]
    for i, e in enumerate(display_entries, 1):
        dt_str = datetime.strptime(e['date'], '%Y-%m-%d').strftime('%d/%m/%y')
        text += f"#{to_bn_number(i)} {'ফিল্ড ট্যুর' if e['entry_type'] == 'REGULAR' else 'মাসিক মিটিং'} — {to_bn_number(dt_str)}\n"
        # ... existing fields ...
        text += f"মিটার শুরু: {to_bn_number(e['odo_start'])}\n"
        text += f"মিটার শেষ: {to_bn_number(e['odo_end'])}\n"
        text += f"দূরত্ব: {to_bn_number(e['total_km'])} কিমি\n"
        
        if e.get('petrol_liters'):
            text += f"তেল: {to_bn_number(e['petrol_liters'])} লি = {to_bn_number(e['petrol_cost'])} টাকা\n"
        
        if e.get('mobil_liters'):
            text += f"মবিল: {to_bn_number(e['mobil_liters'])} লি = {to_bn_number(e['mobil_cost'])} টাকা\n"
            
        text += f"DA বিল: {to_bn_number(e['da_amount'])} টাকা\n"
        
        if e['entry_type'] == 'MONTHLY_MEETING':
            text += f"যাতায়াত ভাড়া: {to_bn_number(e.get('transport_fee', 0))} টাকা\n"
            text += f"বিবরণ: {e.get('venue', '')}\n"
            
        text += f"মোট খরচ: {to_bn_number(e['total_cost'])} টাকা\n"
        
        if e['entry_type'] == 'REGULAR' and e.get('distributors_raw'):
            for dist in e['distributors_raw']:
                text += f"পরিবেশক: {dist}\n"
        text += "\n"
    
    if query:
        await query.edit_message_text(text, reply_markup=BACK_TO_MENU)
    else:
        await update.message.reply_text(text, reply_markup=BACK_TO_MENU)

async def summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    year, month = None, None
    if query:
        await query.answer()
        if query.data.startswith("summary_"):
            parts = query.data.split("_")
            year, month = int(parts[1]), int(parts[2])
    
    entries = await get_entries(month, year)
    if not entries:
        msg = "কোনো এন্ট্রি পাওয়া যায়নি।"
        if query:
            await query.edit_message_text(msg, reply_markup=BACK_TO_MENU)
        else:
            await update.message.reply_text(msg, reply_markup=BACK_TO_MENU)
        return
        
    summary = calculate_summary(entries)
    text = (
        f"📊 **সার সংক্ষেপ**\n\n"
        f"    মোট ট্যুর: {to_bn_number(summary['total_tour'])}টি\n"
        f"    মোট কিমি: {to_bn_number(summary['total_km'])} কিমি\n"
        f"    মোট পেট্রোল: {to_bn_number(summary['total_liters_petrol'])} লি = {to_bn_number(summary['total_petrol_cost'])}/-\n"
        f"    মোট মবিল: {to_bn_number(summary['total_liters_mobil'])} লি = {to_bn_number(summary['total_mobil_cost'])}/-\n"
        f"    মোট DA: {to_bn_number(summary['total_da'])}/-\n"
        f"    যাতায়াত ভাড়া: {to_bn_number(summary['total_others'])}/-\n"
        f"    **সর্বমোট: {to_bn_number(summary['grand_total'])}/-**"
    )
    if query:
        await query.edit_message_text(text, reply_markup=BACK_TO_MENU, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=BACK_TO_MENU, parse_mode='Markdown')
