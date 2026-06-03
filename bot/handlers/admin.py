from telegram import Update
from telegram.ext import ContextTypes
from bot.strings import S
from core.database import OWNER_ID, add_user, remove_user, get_all_users


async def owner_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the sender is the owner. Send error if not."""
    user = update.effective_user
    if user and user.id == OWNER_ID:
        return True
    if update.effective_message:
        await update.effective_message.reply_text(S('admin.not_owner'))
    return False


async def adduser_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a new user. Usage: /adduser <user_id>"""
    if not await owner_only(update, context):
        return
    args = context.args
    if not args:
        await update.effective_message.reply_text(S('admin.adduser_usage'))
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await update.effective_message.reply_text(S('admin.adduser_usage'))
        return
    if add_user(target_id):
        await update.effective_message.reply_text(S('admin.adduser_success', user_id=target_id))
    else:
        await update.effective_message.reply_text(S('admin.adduser_exists', user_id=target_id))


async def removeuser_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a user. Usage: /removeuser <user_id>"""
    if not await owner_only(update, context):
        return
    args = context.args
    if not args:
        await update.effective_message.reply_text(S('admin.removeuser_usage'))
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await update.effective_message.reply_text(S('admin.removeuser_usage'))
        return
    if target_id == OWNER_ID:
        await update.effective_message.reply_text(S('admin.removeuser_cannot_remove_owner'))
        return
    if remove_user(target_id):
        await update.effective_message.reply_text(S('admin.removeuser_success', user_id=target_id))
    else:
        await update.effective_message.reply_text(S('admin.removeuser_not_found', user_id=target_id))


async def listusers_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all registered users."""
    if not await owner_only(update, context):
        return
    users = get_all_users()
    if not users:
        await update.effective_message.reply_text(S('admin.users_empty'))
        return
    lines = [S('admin.users_title')]
    for uid_str, info in users.items():
        role = info.get('role', 'user')
        added = info.get('added_at', '?')[:10]
        lines.append(S('admin.users_line', user_id=uid_str, role=role, added_at=added))
    await update.effective_message.reply_text(''.join(lines))
