"""Edit/delete entry flow tests using mock PTB objects."""
import sys, os, json, glob
from unittest.mock import AsyncMock, MagicMock
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from core.file_data_store import (
    add_user, add_entry, get_entries, get_entry_by_id,
    get_distributors, add_distributor
)

TEST_USER = 776655002
TEST_CHAT = -100776655


@pytest.fixture(autouse=True)
def clean_data():
    os.makedirs('data', exist_ok=True)
    os.makedirs('data/user_prefs', exist_ok=True)
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
    with open('data/distributors.json', 'w', encoding='utf-8') as f:
        json.dump(["টেস্ট ডিস্ট্রিবিউটর"], f, ensure_ascii=False, indent=2)
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


from bot.handlers.settings import (
    edit_delete_menu_handler, start_edit_entry, handle_edit_selection,
    start_field_edit, handle_new_value, handle_edit_distributors,
    handle_recalc_confirm, start_delete_entry, handle_delete_selection,
    confirm_delete_callback, cancel_conversation,
    CHOOSING_ENTRY_TO_EDIT, CHOOSING_FIELD_TO_EDIT, ENTERING_NEW_VALUE,
    EDITING_DISTRIBUTORS, CHOOSING_ENTRY_TO_DELETE, CONFIRM_DELETE,
    CONFIRM_RECALC
)


@pytest.mark.asyncio
class TestEditDeleteFlow:

    async def test_edit_delete_menu(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "edit_delete_menu")
        result = await edit_delete_menu_handler(upd, ctx)
        assert result is None  # no state transition

    async def test_start_edit_entry_no_entries(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_text_update(TEST_USER, TEST_CHAT, "/editentry")
        result = await start_edit_entry(upd, ctx)
        assert result == ConversationHandler.END

    async def test_start_edit_entry_with_entries(self, clean_data):
        await add_user(TEST_USER)
        await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR', 'total_cost': 200})
        ctx = make_context()
        upd = make_text_update(TEST_USER, TEST_CHAT, "/editentry")
        result = await start_edit_entry(upd, ctx)
        assert result == CHOOSING_ENTRY_TO_EDIT

    async def test_edit_select_entry(self, clean_data):
        await add_user(TEST_USER)
        eid = await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR', 'total_cost': 200})
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, f"edit_{eid}")
        result = await handle_edit_selection(upd, ctx)
        assert result == CHOOSING_FIELD_TO_EDIT
        assert ctx.user_data.get('editing_id') == eid

    async def test_edit_select_field_km(self, clean_data):
        await add_user(TEST_USER)
        eid = await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR', 'total_cost': 200})
        ctx = make_context()
        ctx.user_data['editing_id'] = eid
        upd = make_callback_update(TEST_USER, TEST_CHAT, f"edit_field_km_{eid}")
        result = await start_field_edit(upd, ctx)
        assert result == ENTERING_NEW_VALUE
        assert ctx.user_data.get('editing_field') == 'km'

    async def test_edit_field_dist(self, clean_data):
        await add_user(TEST_USER)
        eid = await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR', 'total_cost': 200})
        ctx = make_context()
        ctx.user_data['editing_id'] = eid
        upd = make_callback_update(TEST_USER, TEST_CHAT, f"edit_field_dist_{eid}")
        result = await start_field_edit(upd, ctx)
        assert result == EDITING_DISTRIBUTORS

    async def test_edit_km_value(self, clean_data):
        await add_user(TEST_USER)
        eid = await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR', 'total_cost': 200})
        ctx = make_context()
        ctx.user_data['editing_id'] = eid
        ctx.user_data['editing_field'] = 'km'
        upd = make_text_update(TEST_USER, TEST_CHAT, "80")
        result = await handle_new_value(upd, ctx)
        entry = await get_entry_by_id(TEST_USER, eid)
        assert entry['total_km'] == 80
        # Distance-affecting fields trigger recalc prompt
        assert result == CONFIRM_RECALC

    async def test_edit_petrol_value(self, clean_data):
        await add_user(TEST_USER)
        eid = await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR',
            'petrol_liters': 0, 'petrol_cost': 0, 'total_cost': 200})
        ctx = make_context()
        ctx.user_data['editing_id'] = eid
        ctx.user_data['editing_field'] = 'petrol'
        upd = make_text_update(TEST_USER, TEST_CHAT, "5")
        result = await handle_new_value(upd, ctx)
        entry = await get_entry_by_id(TEST_USER, eid)
        assert entry['petrol_liters'] == 5.0
        # Non-distance fields go back to entry selection
        assert result == CHOOSING_ENTRY_TO_EDIT

    async def test_edit_mobil_value(self, clean_data):
        await add_user(TEST_USER)
        eid = await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR',
            'mobil_liters': 0, 'mobil_cost': 0, 'total_cost': 200})
        ctx = make_context()
        ctx.user_data['editing_id'] = eid
        ctx.user_data['editing_field'] = 'mobil'
        upd = make_text_update(TEST_USER, TEST_CHAT, "2")
        result = await handle_new_value(upd, ctx)
        entry = await get_entry_by_id(TEST_USER, eid)
        assert entry['mobil_liters'] == 2.0
        assert result == CHOOSING_ENTRY_TO_EDIT

    async def test_edit_invalid_value(self, clean_data):
        await add_user(TEST_USER)
        eid = await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR', 'total_cost': 200})
        ctx = make_context()
        ctx.user_data['editing_id'] = eid
        ctx.user_data['editing_field'] = 'km'
        upd = make_text_update(TEST_USER, TEST_CHAT, "abc")
        result = await handle_new_value(upd, ctx)
        assert result == ENTERING_NEW_VALUE  # stays on input

    async def test_edit_distributor_toggle(self, clean_data):
        await add_user(TEST_USER)
        eid = await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR', 'total_cost': 200})
        ctx = make_context()
        ctx.user_data['editing_id'] = eid
        ctx.user_data['selected_dist_indices'] = []
        dists = await get_distributors()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "toggle_dist_0")
        result = await handle_edit_distributors(upd, ctx)
        assert result == EDITING_DISTRIBUTORS
        assert ctx.user_data['selected_dist_indices'] == [0]

    async def test_edit_distributor_done(self, clean_data):
        await add_user(TEST_USER)
        eid = await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR', 'total_cost': 200})
        ctx = make_context()
        ctx.user_data['editing_id'] = eid
        ctx.user_data['selected_dist_indices'] = [0]
        upd = make_callback_update(TEST_USER, TEST_CHAT, "dist_done")
        result = await handle_edit_distributors(upd, ctx)
        assert result == CHOOSING_ENTRY_TO_EDIT

    async def test_edit_distributor_back(self, clean_data):
        await add_user(TEST_USER)
        eid = await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR', 'total_cost': 200})
        ctx = make_context()
        ctx.user_data['editing_id'] = eid
        upd = make_callback_update(TEST_USER, TEST_CHAT, "back")
        result = await handle_edit_distributors(upd, ctx)
        assert result == CHOOSING_FIELD_TO_EDIT

    async def test_edit_distributor_cancel(self, clean_data):
        await add_user(TEST_USER)
        eid = await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR', 'total_cost': 200})
        ctx = make_context()
        ctx.user_data['editing_id'] = eid
        upd = make_callback_update(TEST_USER, TEST_CHAT, "cancel")
        result = await handle_edit_distributors(upd, ctx)
        assert result == ConversationHandler.END

    async def test_recalc_confirm_yes(self, clean_data):
        await add_user(TEST_USER)
        await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR', 'total_cost': 200})
        ctx = make_context()
        ctx.user_data['_recalc_entry_id'] = 1
        upd = make_callback_update(TEST_USER, TEST_CHAT, "recalc_yes")
        result = await handle_recalc_confirm(upd, ctx)
        assert result == CHOOSING_ENTRY_TO_EDIT

    async def test_recalc_confirm_no(self, clean_data):
        await add_user(TEST_USER)
        await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR', 'total_cost': 200})
        ctx = make_context()
        ctx.user_data['_recalc_entry_id'] = 1
        upd = make_callback_update(TEST_USER, TEST_CHAT, "recalc_no")
        result = await handle_recalc_confirm(upd, ctx)
        assert result == CHOOSING_ENTRY_TO_EDIT

    async def test_start_delete_entry_no_entries(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_text_update(TEST_USER, TEST_CHAT, "/delentry")
        result = await start_delete_entry(upd, ctx)
        assert result == ConversationHandler.END

    async def test_start_delete_entry_with_entries(self, clean_data):
        await add_user(TEST_USER)
        await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR', 'total_cost': 200})
        ctx = make_context()
        upd = make_text_update(TEST_USER, TEST_CHAT, "/delentry")
        result = await start_delete_entry(upd, ctx)
        assert result == CHOOSING_ENTRY_TO_DELETE

    async def test_delete_select_entry(self, clean_data):
        await add_user(TEST_USER)
        eid = await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR', 'total_cost': 200})
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, f"delete_{eid}")
        result = await handle_delete_selection(upd, ctx)
        assert result == CONFIRM_DELETE

    async def test_delete_confirm(self, clean_data):
        await add_user(TEST_USER)
        eid = await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR', 'total_cost': 200})
        await add_entry(TEST_USER, {'date': '2026-06-02', 'total_km': 30,
            'odo_start': 64, 'odo_end': 94, 'entry_type': 'REGULAR', 'total_cost': 100})
        ctx = make_context()
        ctx.user_data['deleting_id'] = eid
        upd = make_callback_update(TEST_USER, TEST_CHAT, "confirm_save")
        result = await confirm_delete_callback(upd, ctx)
        entries = await get_entries(TEST_USER)
        assert len(entries) == 1  # one entry remains
        assert result == CHOOSING_ENTRY_TO_DELETE

    async def test_delete_back(self, clean_data):
        await add_user(TEST_USER)
        eid = await add_entry(TEST_USER, {'date': '2026-06-01', 'total_km': 64,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR', 'total_cost': 200})
        await add_entry(TEST_USER, {'date': '2026-06-02', 'total_km': 30,
            'odo_start': 64, 'odo_end': 94, 'entry_type': 'REGULAR', 'total_cost': 100})
        ctx = make_context()
        ctx.user_data['deleting_id'] = eid
        upd = make_callback_update(TEST_USER, TEST_CHAT, "back")
        result = await confirm_delete_callback(upd, ctx)
        entry = await get_entry_by_id(TEST_USER, eid)
        assert entry is not None  # not deleted
        assert result == CHOOSING_ENTRY_TO_DELETE

    async def test_cancel_edit_delete(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "cancel")
        result = await cancel_conversation(upd, ctx)
        assert result == ConversationHandler.END
