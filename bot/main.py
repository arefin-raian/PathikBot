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
from core.database import init_db

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
    
    # Set bot commands for the Telegram Menu
    commands = [
        BotCommand("start", "বটের স্বাগত বার্তা ও ব্যবহার নির্দেশিকা"),
        BotCommand("newentry", "নতুন ফিল্ড ট্যুর বা মাসিক মিটিং এন্ট্রি শুরু করুন"),
        BotCommand("editentry", "পুরানো এন্ট্রি এডিট করুন"),
        BotCommand("delentry", "পুরানো এন্ট্রি ডিলিট করুন"),
        BotCommand("cancel", "বর্তমান অপারেশন বাতিল করুন"),
        BotCommand("help", "সব কমান্ডের বিস্তারিত ব্যাখ্যা"),
        BotCommand("listentries", "চলতি মাসের সব এন্ট্রি দেখুন"),
        BotCommand("summary", "চলতি মাসের সারসংক্ষেপ দেখুন"),
        BotCommand("months", "পুরানো মাসের রেকর্ড দেখুন (আর্কাইভ)"),
        BotCommand("settings", "বর্তমান কনফিগারেশন ও পরিবেশক দেখুন"),
        BotCommand("generate", "চলতি মাসের DOCX রিপোর্ট তৈরি করুন")
    ]
    await application.bot.set_my_commands(commands)

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
    application.add_handler(cancel_handler)
    application.add_handler(menu_handler)

    print("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
