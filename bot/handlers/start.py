from telegram import Update
from telegram.ext import ContextTypes
from bot.inline_keyboards import get_main_menu, BACK_TO_MENU, MONTHS_BN_FULL, to_bn_number
from bot.text_resources import S
from bot.auth import require_auth
from core.timezone import now_dhaka
from core.message_store import get_all_temporary, get_all_files, clear_all_except_files, record_message

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    if not await require_auth(update, context): return
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user = update.effective_user
    now = now_dhaka()
    month_name = MONTHS_BN_FULL[now.month]
    year = to_bn_number(now.year)
    today = to_bn_number(now.strftime('%d/%m/%y'))
    welcome_text = (
        f"{S('start.welcome_title', user_name=user.first_name)} 👋\n\n"
        f"{S('start.menu_header', month_name=month_name, year=year)}\n"
        f"{S('start.bot_info')}\n\n"
        f"{S('start.website_link')}\n\n"
        f"{S('start.menu_prompt')}"
    )
    msg = await update.message.reply_text(welcome_text, reply_markup=get_main_menu(), parse_mode='HTML', disable_web_page_preview=True)
    await record_message(user_id, msg.chat_id, msg.message_id, 'temporary')

    # Delete all previous bot messages (tracked temps + files).
    # The welcome menu and the /start command itself are kept.
    # Note: in private chats, Telegram does not allow bots to delete
    # user messages, so the /start command text stays visible.
    files = await get_all_files(user_id)
    protected_ids = {f['msg_id'] for f in files}
    protected_ids.add(msg.message_id)
    temps = await get_all_temporary(user_id)
    for t in temps:
        if t['msg_id'] in protected_ids:
            continue
        try:
            await context.bot.delete_message(chat_id=t['chat_id'], message_id=t['msg_id'])
        except Exception:
            pass
    await clear_all_except_files(user_id)

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
    user_id = update.effective_user.id
    if update.callback_query:
        await update.callback_query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        msg = await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='HTML')
        await record_message(user_id, msg.chat_id, msg.message_id, 'temporary')

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu button clicks."""
    if not await require_auth(update, context): return
    query = update.callback_query
    await query.answer()

    if query.data == "main_menu":
        now = now_dhaka()
        month_name = MONTHS_BN_FULL[now.month]
        year = to_bn_number(now.year)
        text = (
            f"{S('start.menu_header', month_name=month_name, year=year)}\n"
            f"{S('start.bot_info')}\n\n"
            f"{S('start.website_link')}\n\n"
            f"{S('start.menu_prompt')}"
        )
        await query.edit_message_text(text, reply_markup=get_main_menu(), parse_mode='HTML', disable_web_page_preview=True)
