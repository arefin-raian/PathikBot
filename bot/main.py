import os
import logging
import warnings
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

# Load environment variables BEFORE any module imports that depend on them
load_dotenv()

from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from telegram.warnings import PTBUserWarning

# Suppress harmless PTB warnings about per_message settings with mixed handler types
warnings.filterwarnings("ignore", category=PTBUserWarning, message="If 'per_message=False'")
warnings.filterwarnings("ignore", category=PTBUserWarning, message="If 'per_message=True'")

from core.audit_logger import log_event

from bot.handlers.start import start_command, help_command, main_menu_callback
from bot.handlers.credentials import credentials_command
from bot.handlers.new_entry import get_new_entry_handler
from bot.handlers.report import generate_report_handler
from bot.handlers.summary import list_entries_handler, summary_handler
from bot.handlers.settings import settings_handler, get_settings_conv_handler, get_edit_delete_conv_handler
from bot.handlers.archive import get_archive_handler
from bot.handlers.admin import get_admin_conv_handler, listusers_handler
from bot.text_resources import bot_commands
from bot.restart_scheduler import handle_post_restart, scheduled_restart_loop
from core.file_data_store import init_db

TOKEN = os.getenv("BOT_TOKEN")


class HealthHandler(BaseHTTPRequestHandler):
    """Minimal health-check endpoint for Render port binding."""
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):
        return  # silence HTTP log spam


def _start_health_server():
    """Bind to $PORT so Render doesn't kill the process."""
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logging.info("Health server listening on port %d", port)
    server.serve_forever()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def post_init(application):
    """Run after the bot has been initialized."""
    try:
        await init_db()
    except Exception as e:
        logging.error("init_db failed (continuing with file backend): %s", e)
    await application.bot.set_my_commands(bot_commands())
    try:
        await handle_post_restart(application.bot)
    except Exception as e:
        logging.warning("handle_post_restart error: %s", e)
    import asyncio as _asyncio
    _asyncio.create_task(scheduled_restart_loop(application.bot))
    try:
        await log_event(application.bot, 'bot_started',
            details="PathikBot started successfully",
            changes=[f"Version: <b>2.1</b>", f"Python: <b>3.12</b>"]
        )
    except Exception:
        pass

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
    application.add_handler(CommandHandler('credentials', credentials_command))

    # Start health HTTP server for Render port binding
    # Skipped when running under web_api/launcher.py (uvicorn binds $PORT instead)
    if os.getenv("SKIP_HEALTH_SERVER") != "1":
        hs = threading.Thread(target=_start_health_server, daemon=True)
        hs.start()

    logging.info("Bot is starting...")
    # Background thread under web_api/launcher.py can't install signal handlers.
    if os.getenv("SKIP_HEALTH_SERVER") == "1":
        application.run_polling(stop_signals=None)
    else:
        application.run_polling()

if __name__ == '__main__':
    main()
