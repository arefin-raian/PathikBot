"""Summary and list-entries flow tests using mock PTB objects."""
import sys, os, json, glob
from unittest.mock import AsyncMock, MagicMock
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from core.file_data_store import (
    add_user, add_entry, get_entries, set_user_prefs, get_user_prefs
)

TEST_USER = 665544003
TEST_CHAT = -100665544


@pytest.fixture(autouse=True)
def clean_data():
    os.makedirs('data', exist_ok=True)
    os.makedirs('data/user_prefs', exist_ok=True)
    for f in glob.glob('data/users.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/entries_665544*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/user_prefs/665544*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/message_log/665544*.json'):
        try: os.remove(f)
        except: pass
    yield
    for f in glob.glob('data/users.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/entries_665544*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/user_prefs/665544*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/message_log/665544*.json'):
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


from bot.handlers.summary import list_entries_handler, summary_handler


@pytest.mark.asyncio
class TestListEntries:

    ENTRY = {'date': '2026-06-01', 'total_km': 64,
             'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR',
             'total_cost': 903, 'petrol_liters': 5.0, 'petrol_cost': 703,
             'mobil_liters': 0, 'mobil_cost': 0, 'da_amount': 200}

    async def test_list_entries_command_no_entries(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_text_update(TEST_USER, TEST_CHAT, "/listentries")
        result = await list_entries_handler(upd, ctx)
        assert result is None

    async def test_list_entries_command_with_entries(self, clean_data):
        await add_user(TEST_USER)
        await add_entry(TEST_USER, self.ENTRY)
        ctx = make_context()
        upd = make_text_update(TEST_USER, TEST_CHAT, "/listentries")
        result = await list_entries_handler(upd, ctx)
        assert result is None
        # Should have called reply_text to show filter choice
        upd.message.reply_text.assert_awaited()

    async def test_list_entries_archive(self, clean_data):
        await add_user(TEST_USER)
        await add_entry(TEST_USER, self.ENTRY)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "list_entries_2026_6")
        result = await list_entries_handler(upd, ctx)
        assert result is None
        ctx.bot.send_message.assert_awaited()

    async def test_list_entries_archive_empty(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "list_entries_2026_6")
        result = await list_entries_handler(upd, ctx)
        assert result is None
        upd.callback_query.edit_message_text.assert_awaited()

    async def test_list_entries_main_menu(self, clean_data):
        await add_user(TEST_USER)
        await add_entry(TEST_USER, self.ENTRY)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "list_entries")
        result = await list_entries_handler(upd, ctx)
        assert result is None

    async def test_list_entries_all(self, clean_data):
        await add_user(TEST_USER)
        await add_entry(TEST_USER, self.ENTRY)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "list_entries_all")
        result = await list_entries_handler(upd, ctx)
        assert result is None
        ctx.bot.send_message.assert_awaited()

    async def test_list_entries_filter_checkboxes(self, clean_data):
        await add_user(TEST_USER)
        await add_entry(TEST_USER, self.ENTRY)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "list_entries_filter")
        result = await list_entries_handler(upd, ctx)
        assert result is None
        upd.callback_query.edit_message_text.assert_awaited()

    async def test_list_entries_toggle_filter(self, clean_data):
        await add_user(TEST_USER)
        await add_entry(TEST_USER, self.ENTRY)
        ctx = make_context()
        ctx.user_data['list_filter_state'] = {}
        upd = make_callback_update(TEST_USER, TEST_CHAT, "list_entries_filter_toggle_0")
        result = await list_entries_handler(upd, ctx)
        assert result is None
        assert ctx.user_data['list_filter_state'].get('petrol') is True

    async def test_list_entries_apply_filter(self, clean_data):
        await add_user(TEST_USER)
        await add_entry(TEST_USER, self.ENTRY)
        ctx = make_context()
        ctx.user_data['list_filter_state'] = {'petrol': True}
        upd = make_callback_update(TEST_USER, TEST_CHAT, "list_entries_filter_apply")
        result = await list_entries_handler(upd, ctx)
        assert result is None
        ctx.bot.send_message.assert_awaited()

    async def test_list_entries_filter_back(self, clean_data):
        await add_user(TEST_USER)
        await add_entry(TEST_USER, self.ENTRY)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "list_entries_filter_back")
        result = await list_entries_handler(upd, ctx)
        assert result is None

    async def test_list_entries_no_matches(self, clean_data):
        await add_user(TEST_USER)
        await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR',
            'total_cost': 200, 'petrol_liters': 0, 'petrol_cost': 0,
            'mobil_liters': 0, 'mobil_cost': 0, 'da_amount': 200,
            'others_designation': ''})
        ctx = make_context()
        ctx.user_data['list_filter_state'] = {'meeting': True}
        upd = make_callback_update(TEST_USER, TEST_CHAT, "list_entries_filter_apply")
        result = await list_entries_handler(upd, ctx)
        assert result is None
        upd.callback_query.edit_message_text.assert_awaited()


@pytest.mark.asyncio
class TestSummary:

    ENTRY = {'date': '2026-06-01', 'total_km': 64,
             'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR',
             'total_cost': 903, 'petrol_liters': 5.0, 'petrol_cost': 703,
             'mobil_liters': 0, 'mobil_cost': 0, 'da_amount': 200}

    async def test_summary_command_no_entries(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_text_update(TEST_USER, TEST_CHAT, "/summary")
        result = await summary_handler(upd, ctx)
        assert result is None

    async def test_summary_command_with_entries(self, clean_data):
        await add_user(TEST_USER)
        await add_entry(TEST_USER, self.ENTRY)
        ctx = make_context()
        upd = make_text_update(TEST_USER, TEST_CHAT, "/summary")
        result = await summary_handler(upd, ctx)
        assert result is None
        upd.message.reply_text.assert_awaited()

    async def test_summary_callback(self, clean_data):
        await add_user(TEST_USER)
        await add_entry(TEST_USER, self.ENTRY)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "summary")
        result = await summary_handler(upd, ctx)
        assert result is None
        upd.callback_query.edit_message_text.assert_awaited()

    async def test_summary_specific_month(self, clean_data):
        await add_user(TEST_USER)
        await add_entry(TEST_USER, self.ENTRY)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "summary_2026_6")
        result = await summary_handler(upd, ctx)
        assert result is None
        upd.callback_query.edit_message_text.assert_awaited()

    async def test_summary_specific_month_empty(self, clean_data):
        await add_user(TEST_USER)
        await add_entry(TEST_USER, self.ENTRY)
        ctx = make_context()
        # July (7) should have no entries
        upd = make_callback_update(TEST_USER, TEST_CHAT, "summary_2026_7")
        result = await summary_handler(upd, ctx)
        assert result is None
        upd.callback_query.edit_message_text.assert_awaited()
