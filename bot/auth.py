from core.file_data_store import is_registered, is_owner, OWNER_ID
from bot.text_resources import S


async def require_auth(update, context) -> bool:
    """Check if the user is authorized (registered or owner).
    Returns True if authorized, False if blocked.
    """
    user = update.effective_user
    if user is None:
        return False
    uid = user.id
    if is_owner(uid) or is_registered(uid):
        return True
    message = update.effective_message
    if message:
        await message.reply_text(S('auth.unauthorized'))
    return False
