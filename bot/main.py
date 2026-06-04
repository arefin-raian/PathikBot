import os
import logging
import warnings
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from telegram.warnings import PTBUserWarning

# Suppress harmless PTB warnings about per_message settings with mixed handler types
warnings.filterwarnings("ignore", category=PTBUserWarning, message="If 'per_message=False'")
warnings.filterwarnings("ignore", category=PTBUserWarning, message="If 'per_message=True'")

from dotenv import load_dotenv

from bot.handlers.start import start_command, help_command, main_menu_callback
from bot.handlers.new_entry import get_new_entry_handler
from bot.handlers.report import generate_report_handler
from bot.handlers.summary import list_entries_handler, summary_handler
from bot.handlers.settings import settings_handler, get_settings_conv_handler, get_edit_delete_conv_handler
from bot.handlers.archive import get_archive_handler
from bot.handlers.admin import get_admin_conv_handler, listusers_handler
from bot.text_resources import bot_commands
from core.file_data_store import init_db

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def post_init(application):
    """Run after the bot has been initialized."""
    await init_db()
    await application.bot.set_my_commands(bot_commands())

def main():
    if not TOKEN:
        print("Error: BOT_TOKEN not found in .env file.")
        return

    application = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    # Handlers
    start_handler = CommandHandler('start', start_command)
    help_handler = CommandHandler('help', help_command)
    new_entry_handler = get_new_entry_handler()
    report_handler = CommandHandler('generate', generate_report_handler)
    report_cb_handler = CallbackQueryHandler(generate_report_handler, pattern=r"^generate_report$|^generate_\d+_\d+$")
    list_handler_cmd = CommandHandler('listentries', list_entries_handler)
    list_cb_handler = CallbackQueryHandler(list_entries_handler, pattern="^list_entries")
    summary_handler_cmd = CommandHandler('summary', summary_handler)
    summary_cb_handler = CallbackQueryHandler(summary_handler, pattern="^summary")
    settings_conv_handler = get_settings_conv_handler()
    edit_delete_conv_handler = get_edit_delete_conv_handler()
    archive_handler = get_archive_handler()
    help_cb_handler = CallbackQueryHandler(help_command, pattern="^help$")
    cancel_handler = CommandHandler('cancel', lambda u, c: ConversationHandler.END)
    menu_handler = CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
    admin_conv_handler = get_admin_conv_handler()
    listusers_handler_cmd = CommandHandler('users', listusers_handler)

    application.add_handler(start_handler)
    application.add_handler(help_handler)
    application.add_handler(help_cb_handler)
    application.add_handler(new_entry_handler)
    application.add_handler(report_handler)
    application.add_handler(report_cb_handler)
    application.add_handler(list_handler_cmd)
    application.add_handler(list_cb_handler)
    application.add_handler(summary_handler_cmd)
    application.add_handler(summary_cb_handler)
    application.add_handler(settings_conv_handler)
    application.add_handler(edit_delete_conv_handler)
    application.add_handler(archive_handler)
    application.add_handler(admin_conv_handler)
    application.add_handler(cancel_handler)
    application.add_handler(menu_handler)
    application.add_handler(listusers_handler_cmd)

    print("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
