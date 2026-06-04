import os
from datetime import datetime

STORAGE_CHANNEL = os.getenv("STORAGE_CHANNEL_ID")

EVENT_EMOJI = {
    'user_added': '\U0001f464',
    'user_removed': '\U0001f465',
    'entry_created': '\U0001f4dd',
    'entry_edited': '\u270f\ufe0f',
    'entry_deleted': '\U0001f5d1\ufe0f',
    'auto_recalc': '\U0001f504',
    'docx_generated': '\U0001f4c4',
    'pdf_generated': '\U0001f4d5',
    'file_uploaded': '\U0001f4ce',
    'file_replaced': '\U0001f504',
    'settings_changed': '\u2699\ufe0f',
    'bot_started': '\U0001f680',
    'critical_error': '\u274c',
    'warning': '\u26a0\ufe0f',
    'recovery': '\U0001f527',
}

def _fmt_user(user_id, username=None):
    name = username or f"User#{user_id}"
    return f'<a href="tg://user?id={user_id}">{name}</a>'

def _fmt_val(old, new):
    if old is not None and new is not None and old != new:
        return f"<b>{old}</b> \u2192 <b>{new}</b>"
    if new is not None:
        return f"<b>{new}</b>"
    return ""

def _indent(text, prefix="  \u2022 "):
    return "\n".join(f"{prefix}{line}" for line in text.split("\n"))

async def log_event(context_or_bot, event_type, **kw):
    if not STORAGE_CHANNEL:
        return
    bot = context_or_bot.bot if hasattr(context_or_bot, 'bot') else context_or_bot
    try:
        emoji = EVENT_EMOJI.get(event_type, '\U0001f4cb')
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        title = event_type.replace('_', ' ').title()

        parts = [f"{emoji} <b>{title}</b>", f"\U0001f550 <code>{ts}</code>"]

        uid = kw.get('user_id')
        if uid:
            uname = kw.get('username')
            parts.append(f"\U0001f464 {_fmt_user(uid, uname)}")

        if kw.get('details'):
            parts.append(f"\U0001f4cb {kw['details']}")

        changes = kw.get('changes')
        if changes:
            parts.append("")
            parts.append("<b>Changes:</b>")
            for c in changes:
                parts.append(_indent(c, "  \u2022 "))

        effects = kw.get('effects')
        if effects:
            parts.append("")
            parts.append("<b>Cascading Effects:</b>")
            for e in effects:
                parts.append(_indent(e, "  \u2192 "))

        await bot.send_message(
            chat_id=STORAGE_CHANNEL,
            text="\n".join(parts),
            parse_mode='HTML'
        )
    except Exception:
        pass
