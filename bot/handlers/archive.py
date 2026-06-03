from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, ConversationHandler
from core.database import get_entries
from bot.keyboards import MONTHS_BN_FULL, to_bn_number, BACK_TO_MENU
from bot.strings import S
from datetime import datetime

# States
SELECTING_ARCHIVE_MONTH = 1

async def months_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /months command."""
    entries = await get_entries()
    if not entries:
        msg = S('archive.no_entries')
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, reply_markup=BACK_TO_MENU)
        else:
            await update.message.reply_text(msg, reply_markup=BACK_TO_MENU)
        return ConversationHandler.END

    months_data = set()
    for e in entries:
        dt = datetime.strptime(e['date'], '%Y-%m-%d')
        months_data.add((dt.year, dt.month))
    
    sorted_months = sorted(list(months_data), reverse=True)
    
    keyboard = []
    for year, month in sorted_months:
        label = S('archive.month_label', month_name=MONTHS_BN_FULL[month], year=to_bn_number(year))
        keyboard.append([InlineKeyboardButton(label, callback_data=f"archive_view_{year}_{month}")])
    
    keyboard.append([InlineKeyboardButton(S('common.back_to_menu'), callback_data="main_menu")])
    
    msg = S('archive.prompt')
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
        
        b = S('keyboards.archive_actions')
        keyboard = [
            [InlineKeyboardButton(b['list_entries'], callback_data=f"list_entries_{year}_{month}")],
            [InlineKeyboardButton(b['summary'], callback_data=f"summary_{year}_{month}")],
            [InlineKeyboardButton(b['report'], callback_data=f"generate_{year}_{month}")],
            [InlineKeyboardButton(b['back'], callback_data="months_back")]
        ]
        
        msg = S('archive.action_prompt', month_name=MONTHS_BN_FULL[month], year=to_bn_number(year))
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
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
    msg = S('archive.cancelled')
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=BACK_TO_MENU)
    else:
        await update.message.reply_text(msg, reply_markup=BACK_TO_MENU)
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
