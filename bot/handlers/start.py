from telegram import Update
from telegram.ext import ContextTypes
from bot.inline_keyboards import get_main_menu, BACK_TO_MENU, MONTHS_BN_FULL, to_bn_number
from bot.text_resources import S
from bot.auth import require_auth
from datetime import datetime

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    if not await require_auth(update, context): return
    user = update.effective_user
    now = datetime.now()
    month_name = MONTHS_BN_FULL[now.month]
    year = to_bn_number(now.year)
    today = to_bn_number(now.strftime('%d/%m/%y'))
    welcome_text = (
        f"{S('start.welcome_title', user_name=user.first_name)} 👋\n\n"
        f"{S('start.menu_header', month_name=month_name, year=year)}\n"
        f"{S('start.bot_info')}\n\n"
        f"{S('start.menu_prompt')}"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu(), parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command with detailed Bangla explanations."""
    if not await require_auth(update, context): return
    help_sections = S('help.sections')
    help_text = (
        f"{S('help.title')}\n\n"
        f"{help_sections['start']}\n\n"
        f"{help_sections['new_entry']}\n\n"
        f"{help_sections['edit_entry']}\n\n"
        f"{help_sections['del_entry']}\n\n"
        f"{help_sections['cancel']}\n\n"
        f"{help_sections['list_entries']}\n\n"
        f"{help_sections['summary']}\n\n"
        f"{help_sections['months']}\n\n"
        f"{help_sections['settings']}\n\n"
        f"{help_sections['generate']}"
    )
    # Context-aware: direct command → no back button; menu callback → back to main menu
    reply_markup = BACK_TO_MENU if update.callback_query else None
    if update.callback_query:
        await update.callback_query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='HTML')

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu button clicks."""
    if not await require_auth(update, context): return
    query = update.callback_query
    await query.answer()

    if query.data == "main_menu":
        now = datetime.now()
        month_name = MONTHS_BN_FULL[now.month]
        year = to_bn_number(now.year)
        text = (
            f"{S('start.menu_header', month_name=month_name, year=year)}\n"
            f"{S('start.bot_info')}\n\n"
            f"{S('start.menu_prompt')}"
        )
        await query.edit_message_text(text, reply_markup=get_main_menu(), parse_mode='HTML')
