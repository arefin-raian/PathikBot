"""Admin flow tests — /adduser, /removeuser, /users using mock PTB objects."""
import sys, os, json, glob
from unittest.mock import AsyncMock, MagicMock
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from core.file_data_store import (
    init_db, add_user, is_registered, remove_user, get_all_users, OWNER_ID
)

TEST_CHAT = -100776655
ADMIN_ID = OWNER_ID  # must match owner_only guard

@pytest.fixture(autouse=True)
def clean_data():
    os.makedirs('data', exist_ok=True)
    for f in glob.glob('data/users.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/entries_776655*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/user_prefs/776655*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/message_log/776655*.json'):
        try: os.remove(f)
        except: pass
    yield
    for f in glob.glob('data/users.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/entries_776655*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/user_prefs/776655*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/message_log/776655*.json'):
        try: os.remove(f)
        except: pass


def make_text_update(user_id, chat_id, text):
    upd = MagicMock(spec=Update)
    upd.effective_user.id = user_id
    upd.effective_chat.id = chat_id
    msg = MagicMock()
    msg.text = text
    msg.message_id = 101
    msg.chat_id = chat_id
    msg.reply_text = AsyncMock(return_value=msg)
    msg.reply_html = AsyncMock(return_value=msg)
    msg.delete = AsyncMock()
    upd.message = msg
    upd.callback_query = None
    upd.effective_message = msg
    return upd


def make_callback_update(user_id, chat_id, callback_data):
    upd = MagicMock(spec=Update)
    upd.effective_user.id = user_id
    upd.effective_chat.id = chat_id
    cq = MagicMock()
    cq.data = callback_data
    cq.message = MagicMock()
    cq.message.chat_id = chat_id
    cq.message.message_id = 100
    cq.message.delete = AsyncMock()
    cq.message.reply_text = AsyncMock(return_value=cq.message)
    cq.message.reply_html = AsyncMock(return_value=cq.message)
    cq.edit_message_text = AsyncMock()
    cq.edit_message_reply_markup = AsyncMock()
    cq.answer = AsyncMock()
    upd.callback_query = cq
    upd.message = None
    upd.effective_message = cq.message
    return upd


def make_context():
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    ctx.user_data = {}
    ctx.bot.send_message = AsyncMock()
    ctx.bot.send_document = AsyncMock()
    ctx.bot.delete_message = AsyncMock()
    ctx.bot.edit_message_text = AsyncMock()
    ctx.bot.edit_message_reply_markup = AsyncMock()
    ctx.bot.send_chat_action = AsyncMock()
    ctx.application.create_task = MagicMock()
    return ctx


from bot.handlers.admin import (
    start_adduser, handle_adduser_id, confirm_adduser,
    start_removeuser, select_removeuser, confirm_removeuser,
    listusers_handler, cancel,
    ADDUSER_AWAIT_ID, ADDUSER_CONFIRM,
    REMOVEUSER_SELECT, REMOVEUSER_CONFIRM
)


@pytest.mark.asyncio
class TestAdminFlow:

    async def test_adduser_starts(self, clean_data):
        """Owner starts /adduser, enters user ID, confirms."""
        ctx = make_context()
        upd = make_text_update(ADMIN_ID, TEST_CHAT, "/adduser")
        result = await start_adduser(upd, ctx)
        assert result == ADDUSER_AWAIT_ID

    async def test_adduser_rejects_non_owner(self, clean_data):
        """Non-owner calling /adduser should be rejected."""
        ctx = make_context()
        upd = make_text_update(12345, TEST_CHAT, "/adduser")
        result = await start_adduser(upd, ctx)
        assert result == ConversationHandler.END

    async def test_adduser_enter_id(self, clean_data):
        ctx = make_context()
        upd = make_text_update(ADMIN_ID, TEST_CHAT, "100200300")
        result = await handle_adduser_id(upd, ctx)
        assert result == ADDUSER_CONFIRM

    async def test_adduser_confirm(self, clean_data):
        ctx = make_context()
        ctx.user_data['add_target_id'] = 100200300
        upd = make_callback_update(ADMIN_ID, TEST_CHAT, "admin_confirm_add")
        result = await confirm_adduser(upd, ctx)
        assert result == ConversationHandler.END
        assert await is_registered(100200300)

    async def test_adduser_cancel(self, clean_data):
        ctx = make_context()
        ctx.user_data['add_target_id'] = 100200300
        upd = make_callback_update(ADMIN_ID, TEST_CHAT, "admin_cancel")
        result = await confirm_adduser(upd, ctx)
        assert result == ConversationHandler.END
        assert not await is_registered(100200300)

    async def test_removeuser_starts(self, clean_data):
        await add_user(ADMIN_ID)
        await add_user(200300400)
        ctx = make_context()
        upd = make_text_update(ADMIN_ID, TEST_CHAT, "/removeuser")
        result = await start_removeuser(upd, ctx)
        assert result == REMOVEUSER_SELECT

    async def test_removeuser_rejects_non_owner(self, clean_data):
        ctx = make_context()
        upd = make_text_update(12345, TEST_CHAT, "/removeuser")
        result = await start_removeuser(upd, ctx)
        assert result == ConversationHandler.END

    async def test_removeuser_select(self, clean_data):
        await add_user(ADMIN_ID)
        await add_user(200300400)
        ctx = make_context()
        upd = make_callback_update(ADMIN_ID, TEST_CHAT, "admin_remove_200300400")
        result = await select_removeuser(upd, ctx)
        assert result == REMOVEUSER_CONFIRM

    async def test_removeuser_confirm(self, clean_data):
        await add_user(ADMIN_ID)
        await add_user(200300400)
        ctx = make_context()
        ctx.user_data['remove_target_id'] = 200300400
        upd = make_callback_update(ADMIN_ID, TEST_CHAT, "admin_confirm_remove")
        result = await confirm_removeuser(upd, ctx)
        assert result == ConversationHandler.END
        assert not await is_registered(200300400)

    async def test_removeuser_confirm_back_to_list(self, clean_data):
        await add_user(ADMIN_ID)
        await add_user(200300400)
        ctx = make_context()
        ctx.user_data['remove_target_id'] = 200300400
        upd = make_callback_update(ADMIN_ID, TEST_CHAT, "admin_back_to_list")
        result = await confirm_removeuser(upd, ctx)
        assert result == REMOVEUSER_SELECT
        assert await is_registered(200300400)

    async def test_removeuser_select_cancel(self, clean_data):
        await add_user(ADMIN_ID)
        ctx = make_context()
        upd = make_callback_update(ADMIN_ID, TEST_CHAT, "admin_cancel")
        result = await select_removeuser(upd, ctx)
        assert result == ConversationHandler.END

    async def test_listusers_requires_owner(self, clean_data):
        await add_user(ADMIN_ID)
        await add_user(300400500)
        ctx = make_context()
        upd = make_text_update(ADMIN_ID, TEST_CHAT, "/users")
        result = await listusers_handler(upd, ctx)
        # listusers is not part of a ConversationHandler, returns None
        assert result is None

    async def test_listusers_rejects_non_owner(self, clean_data):
        ctx = make_context()
        upd = make_text_update(12345, TEST_CHAT, "/users")
        result = await listusers_handler(upd, ctx)
        assert result is None

    async def test_cancel_admin(self, clean_data):
        ctx = make_context()
        upd = make_callback_update(ADMIN_ID, TEST_CHAT, "cancel")
        result = await cancel(upd, ctx)
        assert result == ConversationHandler.END
