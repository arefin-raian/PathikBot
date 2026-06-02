from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, ConversationHandler
from core.database import get_entries
from bot.keyboards import MONTHS_BN_FULL, to_bn_number, get_main_menu
from datetime import datetime

# States
SELECTING_ARCHIVE_MONTH = 1

async def months_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /months command."""
    entries = await get_entries()
    if not entries:
        msg = "কোনো এন্ট্রি পাওয়া যায়নি।"
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, reply_markup=get_main_menu())
        else:
            await update.message.reply_text(msg, reply_markup=get_main_menu())
        return ConversationHandler.END

    # Get unique months and years from entries
    months_data = set()
    for e in entries:
        dt = datetime.strptime(e['date'], '%Y-%m-%d')
        months_data.add((dt.year, dt.month))
    
    sorted_months = sorted(list(months_data), reverse=True)
    
    keyboard = []
    for year, month in sorted_months:
        label = f"{MONTHS_BN_FULL[month]} {to_bn_number(year)}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"archive_view_{year}_{month}")])
    
    keyboard.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data="main_menu")])
    
    msg = "পুরানো মাসের রেকর্ড দেখতে মাস নির্বাচন করুন:"
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_ARCHIVE_MONTH

async def archive_month_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "main_menu":
        from bot.handlers.start import main_menu_callback
        return await main_menu_callback(update, context)

    if query.data.startswith("archive_view_"):
        parts = query.data.split("_")
        year, month = int(parts[2]), int(parts[3])
        
        # Options for the selected month
        keyboard = [
            [InlineKeyboardButton("📋 এন্ট্রি তালিকা", callback_data=f"list_entries_{year}_{month}")],
            [InlineKeyboardButton("📊 সারসংক্ষেপ", callback_data=f"summary_{year}_{month}")],
            [InlineKeyboardButton("📄 রিপোর্ট তৈরি করুন", callback_data=f"generate_{year}_{month}")],
            [InlineKeyboardButton("🔙 ফিরে যান", callback_data="months_back")]
        ]
        
        msg = f"📂 **{MONTHS_BN_FULL[month]} {to_bn_number(year)}**-এর জন্য আপনি কী করতে চান?"
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return SELECTING_ARCHIVE_MONTH

    if query.data == "months_back":
        return await months_command(update, context)

    if query.data.startswith("list_entries_"):
        from bot.handlers.summary import list_entries_handler
        await list_entries_handler(update, context)
        return ConversationHandler.END

    if query.data.startswith("summary_"):
        from bot.handlers.summary import summary_handler
        await summary_handler(update, context)
        return ConversationHandler.END

    if query.data.startswith("generate_"):
        from bot.handlers.report import generate_report_handler
        await generate_report_handler(update, context)
        return ConversationHandler.END

    return SELECTING_ARCHIVE_MONTH

async def archive_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return ConversationHandler.END

def get_archive_handler():
    return ConversationHandler(
        entry_points=[
            CommandHandler("months", months_command),
            CallbackQueryHandler(months_command, pattern="^archive_menu$")
        ],
        states={
            SELECTING_ARCHIVE_MONTH: [CallbackQueryHandler(archive_month_selection_handler)]
        },
        fallbacks=[CommandHandler("cancel", archive_cancel)],
    )
