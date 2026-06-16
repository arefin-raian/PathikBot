"""/credentials command — issue or rotate web-login credentials."""
from telegram import Update
from telegram.ext import ContextTypes

from bot.auth import require_auth
from bot.text_resources import S
from core.credentials import issue_credentials


async def credentials_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_auth(update, context):
        return
    user = update.effective_user
    try:
        email, password = await issue_credentials(
            user.id,
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            username=user.username or "",
        )
    except Exception as e:
        await update.effective_message.reply_text(
            S("credentials.failed", error=str(e)), parse_mode="HTML"
        )
        return

    text = S(
        "credentials.issued",
        email=email,
        password=password,
    )
    await update.effective_message.reply_text(text, parse_mode="HTML")
