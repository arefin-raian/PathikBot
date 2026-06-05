"""Settings flow tests using mock PTB objects."""
import sys, os, json, glob
from unittest.mock import AsyncMock, MagicMock
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from core.file_data_store import (
    init_db, add_user, is_registered, get_user_prefs, set_user_prefs,
    get_distributors, add_distributor, remove_distributor,
    add_entry, get_entries, OWNER_ID
)

TEST_USER = 998877001
TEST_CHAT = -100998877


@pytest.fixture(autouse=True)
def clean_data():
    os.makedirs('data', exist_ok=True)
    os.makedirs('data/user_prefs', exist_ok=True)
    for f in glob.glob('data/users.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/entries_998877*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/user_prefs/998877*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/message_log/998877*.json'):
        try: os.remove(f)
        except: pass
    with open('data/distributors.json', 'w', encoding='utf-8') as f:
        json.dump(["টেস্ট ডিস্ট্রিবিউটর"], f, ensure_ascii=False, indent=2)
    yield
    for f in glob.glob('data/users.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/entries_998877*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/user_prefs/998877*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/message_log/998877*.json'):
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
    settings_handler, handle_settings_navigation,
    start_setting_change, handle_setting_value,
    distributor_mgmt_handler, handle_distributor_mgmt_callback,
    handle_new_distributor_name, handle_update_old_confirm,
    cancel_conversation,
    SHOWING_SETTINGS, SETTING_VALUE, MANAGING_DISTRIBUTORS,
    ADDING_DISTRIBUTOR, CONFIRM_UPDATE_OLD
)


@pytest.mark.asyncio
class TestSettingsFlow:

    async def test_settings_menu_from_command(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_text_update(TEST_USER, TEST_CHAT, "/settings")
        result = await settings_handler(upd, ctx)
        assert result == SHOWING_SETTINGS

    async def test_settings_menu_from_callback(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "settings")
        result = await settings_handler(upd, ctx)
        assert result == SHOWING_SETTINGS

    async def test_start_petrol_price_change(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        await settings_handler(make_text_update(TEST_USER, TEST_CHAT, "/settings"), ctx)
        upd = make_callback_update(TEST_USER, TEST_CHAT, "set_petrol_price")
        result = await start_setting_change(upd, ctx)
        assert result == SETTING_VALUE
        assert ctx.user_data.get('changing_setting') == 'petrol_price'

    async def test_set_petrol_price(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        ctx.user_data['changing_setting'] = 'petrol_price'
        upd = make_text_update(TEST_USER, TEST_CHAT, "145.5")
        result = await handle_setting_value(upd, ctx)
        prefs = await get_user_prefs(TEST_USER)
        assert prefs.get('petrol_price') == 145.5
        assert result == CONFIRM_UPDATE_OLD

    async def test_set_mobil_price(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        ctx.user_data['changing_setting'] = 'mobil_price'
        upd = make_text_update(TEST_USER, TEST_CHAT, "580")
        result = await handle_setting_value(upd, ctx)
        prefs = await get_user_prefs(TEST_USER)
        assert prefs.get('mobil_price') == 580.0
        assert result == CONFIRM_UPDATE_OLD

    async def test_set_da_rate(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        ctx.user_data['changing_setting'] = 'da_amount'
        upd = make_text_update(TEST_USER, TEST_CHAT, "250")
        result = await handle_setting_value(upd, ctx)
        prefs = await get_user_prefs(TEST_USER)
        assert prefs.get('da_amount') == 250
        assert result == SHOWING_SETTINGS  # no update_old prompt for DA

    async def test_set_transport_fee(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        ctx.user_data['changing_setting'] = 'transport_fee'
        upd = make_text_update(TEST_USER, TEST_CHAT, "500")
        result = await handle_setting_value(upd, ctx)
        prefs = await get_user_prefs(TEST_USER)
        assert prefs.get('transport_fee') == 500
        assert result == SHOWING_SETTINGS

    async def test_set_invalid_value(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        ctx.user_data['changing_setting'] = 'da_amount'
        upd = make_text_update(TEST_USER, TEST_CHAT, "abc")
        result = await handle_setting_value(upd, ctx)
        assert result == SETTING_VALUE  # stays on input
        prefs = await get_user_prefs(TEST_USER)
        assert prefs.get('da_amount') != "abc"

    async def test_set_invalid_price(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        ctx.user_data['changing_setting'] = 'petrol_price'
        upd = make_text_update(TEST_USER, TEST_CHAT, "not a number")
        result = await handle_setting_value(upd, ctx)
        assert result == SETTING_VALUE

    async def test_update_old_yes(self, clean_data):
        await add_user(TEST_USER)
        eid = await add_entry(TEST_USER, {
            'date': '2026-06-01', 'total_km': 64, 'petrol_liters': 5.0,
            'petrol_cost': 703.5, 'total_cost': 903.5,
            'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR'
        })
        ctx = make_context()
        ctx.user_data['_price_key'] = 'petrol_price'
        ctx.user_data['_price_value'] = 200.0
        upd = make_callback_update(TEST_USER, TEST_CHAT, "update_old_yes")
        result = await handle_update_old_confirm(upd, ctx)
        assert result == SHOWING_SETTINGS
        entry = (await get_entries(TEST_USER))[0]
        assert entry['petrol_cost'] == 1000.0  # 5.0 * 200.0

    async def test_update_old_no(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        ctx.user_data['_price_key'] = 'petrol_price'
        ctx.user_data['_price_value'] = 200.0
        upd = make_callback_update(TEST_USER, TEST_CHAT, "update_old_no")
        result = await handle_update_old_confirm(upd, ctx)
        assert result == SHOWING_SETTINGS

    async def test_main_menu_from_settings(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        await settings_handler(make_text_update(TEST_USER, TEST_CHAT, "/settings"), ctx)
        upd = make_callback_update(TEST_USER, TEST_CHAT, "main_menu")
        result = await handle_settings_navigation(upd, ctx)
        assert result == ConversationHandler.END

    async def test_distributor_mgmt_open(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "manage_distributors")
        result = await distributor_mgmt_handler(upd, ctx)
        assert result == MANAGING_DISTRIBUTORS

    async def test_distributor_add_flow(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "add_distributor")
        result = await handle_distributor_mgmt_callback(upd, ctx)
        assert result == ADDING_DISTRIBUTOR

    async def test_add_new_distributor_name(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_text_update(TEST_USER, TEST_CHAT, "নতুন ডিস্ট্রিবিউটর")
        result = await handle_new_distributor_name(upd, ctx)
        assert result == MANAGING_DISTRIBUTORS
        dists = await get_distributors()
        assert "নতুন ডিস্ট্রিবিউটর" in dists

    async def test_remove_distributor(self, clean_data):
        await add_user(TEST_USER)
        await add_distributor("Dist To Remove")
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "remove_dist_0")
        result = await handle_distributor_mgmt_callback(upd, ctx)
        assert result == MANAGING_DISTRIBUTORS
        dists = await get_distributors()
        assert "Dist To Remove" not in dists

    async def test_remove_distributor_invalid_index(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "remove_dist_99")
        result = await handle_distributor_mgmt_callback(upd, ctx)
        assert result == MANAGING_DISTRIBUTORS
        dists = await get_distributors()
        assert len(dists) == 1

    async def test_return_from_dist_mgmt_to_settings(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "settings")
        result = await handle_distributor_mgmt_callback(upd, ctx)
        assert result == SHOWING_SETTINGS

    async def test_cancel_settings(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "cancel")
        result = await cancel_conversation(upd, ctx)
        assert result == ConversationHandler.END
