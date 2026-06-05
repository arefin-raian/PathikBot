"""Comprehensive entry creation flow tests using mock PTB objects."""
import sys, os, json, pytest, asyncio, glob
from unittest.mock import AsyncMock, MagicMock, patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, date

from core.file_data_store import (
    OWNER_ID, add_user, is_registered, init_db,
    add_entry, get_entries, get_entry_by_id, update_entry,
    get_last_odo, get_last_day_in_month, get_user_prefs,
    add_distributor, get_distributors
)

TEST_USER = 999999003
TEST_CHAT = -100999003


@pytest.fixture(autouse=True)
def clean_data():
    os.makedirs('data', exist_ok=True)
    os.makedirs('data/user_prefs', exist_ok=True)
    for f in glob.glob('data/users.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/entries_999999*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/user_prefs/999999*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/message_log/999999*.json'):
        try: os.remove(f)
        except: pass
    # Reset distributors for clean test state
    with open('data/distributors.json', 'w', encoding='utf-8') as f:
        json.dump(["টেস্ট ডিস্ট্রিবিউটর"], f, ensure_ascii=False, indent=2)
    yield
    for f in glob.glob('data/users.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/entries_999999*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/user_prefs/999999*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/message_log/999999*.json'):
        try: os.remove(f)
        except: pass


# ── Mock helpers ───────────────────────────────────────────

def make_text_update(user_id, chat_id, text):
    upd = MagicMock(spec=Update)
    upd.effective_user.id = user_id
    upd.effective_chat.id = chat_id
    msg = MagicMock()
    msg.text = text
    msg.message_id = 101
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
    ctx.application.create_task.side_effect = lambda c, *a, **kw: None
    return ctx


# ── Import handler functions ──────────────────────────────

from bot.handlers.new_entry import (
    start_new_entry, handle_type_selection,
    handle_month_selection, handle_date_selection,
    handle_odo_start_confirm, handle_odo_start, handle_distance,
    handle_odo_confirm, handle_petrol_question, handle_liters,
    handle_mobil_question, handle_mobil_liters,
    handle_manager_question, handle_manager_designation,
    handle_distributor_selection, handle_venue,
    handle_transport_fee, handle_transport_confirm,
    show_confirmation, save_entry_callback, handle_last_tour_confirm,
    cancel, push_history, pop_history,
    CHOOSING_TYPE, SELECT_MONTH, SHOW_ALL_MONTHS, SELECT_DATE,
    ENTER_ODO_START, ENTER_DISTANCE, CONFIRM_ODO_END,
    PETROL_QUESTION, ENTER_LITERS, MOBIL_QUESTION, ENTER_MOBIL_LITERS,
    MANAGER_QUESTION, ENTER_MANAGER, SELECT_DISTRIBUTORS,
    CONFIRM_ENTRY, ENTER_VENUE, ENTER_TRANSPORT_FEE,
    CONFIRM_TRANSPORT_FEE, CONFIRM_LAST_TOUR
)


# ── Entry Flow Tests ──────────────────────────────────────

@pytest.mark.asyncio
class TestEntryFlowBasics:

    async def test_start_new_entry_returns_choosing_type(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_text_update(TEST_USER, TEST_CHAT, "/newentry")
        result = await start_new_entry(upd, ctx)
        assert result == CHOOSING_TYPE

    async def test_start_new_entry_from_callback(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "new_entry")
        result = await start_new_entry(upd, ctx)
        assert result == CHOOSING_TYPE

    async def test_type_selection_regular_with_sticky_month(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        ctx.user_data['selected_month'] = 6
        ctx.user_data['selected_year'] = 2026
        push_history(ctx, CHOOSING_TYPE)
        upd = make_callback_update(TEST_USER, TEST_CHAT, "type_regular")
        result = await handle_type_selection(upd, ctx)
        assert result == SELECT_DATE, f"Expected SELECT_DATE, got {result}"

    async def test_type_selection_regular_without_sticky_month(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        push_history(ctx, CHOOSING_TYPE)
        upd = make_callback_update(TEST_USER, TEST_CHAT, "type_regular")
        result = await handle_type_selection(upd, ctx)
        assert result == SELECT_MONTH, f"Expected SELECT_MONTH, got {result}"

    async def test_type_selection_meeting(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        push_history(ctx, CHOOSING_TYPE)
        upd = make_callback_update(TEST_USER, TEST_CHAT, "type_meeting")
        result = await handle_type_selection(upd, ctx)
        assert result == SELECT_MONTH, f"Expected SELECT_MONTH, got {result}"
        # transport_fee is not set at type selection stage; it's set later
        assert 'transport_fee' not in ctx.user_data

    async def test_type_selection_cancel(self, clean_data):
        await add_user(TEST_USER)
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "cancel")
        result = await handle_type_selection(upd, ctx)
        assert result == ConversationHandler.END


@pytest.mark.asyncio
class TestEntryFlowRegular:

    async def _setup_to_select_date(self, ctx):
        """Advance flow to SELECT_DATE with sticky month set."""
        await add_user(TEST_USER)
        push_history(ctx, CHOOSING_TYPE)
        ctx.user_data['selected_month'] = 6
        ctx.user_data['selected_year'] = 2026
        upd = make_callback_update(TEST_USER, TEST_CHAT, "type_regular")
        result = await handle_type_selection(upd, ctx)
        assert result == SELECT_DATE
        return upd

    async def test_date_selection(self, clean_data):
        ctx = make_context()
        await self._setup_to_select_date(ctx)
        upd = make_callback_update(TEST_USER, TEST_CHAT, "select_date_1")
        result = await handle_date_selection(upd, ctx)
        assert result == ENTER_ODO_START, f"Expected ENTER_ODO_START, got {result}"
        assert ctx.user_data.get('date') == '2026-06-01'
        assert 'selected_date' not in ctx.user_data

    async def test_odo_start_confirm_yes(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        await add_entry(TEST_USER, {'date': '2026-05-31', 'total_km': 50,
            'odo_start': 100, 'odo_end': 150, 'entry_type': 'REGULAR'})
        await self._setup_to_select_date(ctx)
        upd = make_callback_update(TEST_USER, TEST_CHAT, "select_date_1")
        result = await handle_date_selection(upd, ctx)
        assert result == ENTER_ODO_START
        # Now odo_start confirm
        suggested = ctx.user_data.get('suggested_odo_start')
        assert suggested == 150  # last entry's odo_end
        upd2 = make_callback_update(TEST_USER, TEST_CHAT, "odo_start_confirm_yes")
        result2 = await handle_odo_start_confirm(upd2, ctx)
        assert result2 == ENTER_DISTANCE, f"Expected ENTER_DISTANCE, got {result2}"
        assert ctx.user_data.get('odo_start') == 150

    async def test_odo_start_confirm_no_then_text(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        await self._setup_to_select_date(ctx)
        upd = make_callback_update(TEST_USER, TEST_CHAT, "select_date_1")
        result = await handle_date_selection(upd, ctx)
        assert result == ENTER_ODO_START
        # Say no to suggested odo
        upd2 = make_callback_update(TEST_USER, TEST_CHAT, "odo_start_confirm_no")
        result2 = await handle_odo_start_confirm(upd2, ctx)
        assert result2 == ENTER_ODO_START
        # Now enter manual odo
        upd3 = make_text_update(TEST_USER, TEST_CHAT, "500")
        result3 = await handle_odo_start(upd3, ctx)
        assert result3 == ENTER_DISTANCE, f"Expected ENTER_DISTANCE, got {result3}"
        assert ctx.user_data.get('odo_start') == 500

    async def test_distance_entry(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        await self._setup_to_select_date(ctx)
        ctx.user_data['odo_start'] = 500
        push_history(ctx, ENTER_ODO_START)
        upd = make_text_update(TEST_USER, TEST_CHAT, "64")
        result = await handle_distance(upd, ctx)
        assert result == CONFIRM_ODO_END, f"Expected CONFIRM_ODO_END, got {result}"
        assert ctx.user_data.get('total_km') == 64
        assert ctx.user_data.get('odo_end') == 564

    async def test_distance_expression_evaluation(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        ctx.user_data['odo_start'] = 500
        push_history(ctx, ENTER_ODO_START)
        upd = make_text_update(TEST_USER, TEST_CHAT, "50 + 14")
        result = await handle_distance(upd, ctx)
        assert result == CONFIRM_ODO_END
        assert ctx.user_data.get('total_km') == 64
        assert ctx.user_data.get('odo_end') == 564

    async def test_odo_confirm_yes(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        ctx.user_data['odo_start'] = 500
        ctx.user_data['odo_end'] = 564
        ctx.user_data['total_km'] = 64
        push_history(ctx, ENTER_DISTANCE)
        upd = make_callback_update(TEST_USER, TEST_CHAT, "odo_confirm_yes")
        result = await handle_odo_confirm(upd, ctx)
        assert result == PETROL_QUESTION

    async def test_petrol_yes_flow(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        ctx.user_data['total_km'] = 64
        push_history(ctx, CONFIRM_ODO_END)
        upd = make_callback_update(TEST_USER, TEST_CHAT, "petrol_yes")
        result = await handle_petrol_question(upd, ctx)
        assert result == ENTER_LITERS

    async def test_petrol_no_flow(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        ctx.user_data['total_km'] = 64
        push_history(ctx, CONFIRM_ODO_END)
        upd = make_callback_update(TEST_USER, TEST_CHAT, "petrol_no")
        result = await handle_petrol_question(upd, ctx)
        assert result == MOBIL_QUESTION
        assert ctx.user_data.get('petrol_liters') == 0
        assert ctx.user_data.get('petrol_cost') == 0

    async def test_liters_entry(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        ctx.user_data['total_km'] = 64
        push_history(ctx, PETROL_QUESTION)
        upd = make_text_update(TEST_USER, TEST_CHAT, "5")
        result = await handle_liters(upd, ctx)
        assert result == MOBIL_QUESTION, f"Expected MOBIL_QUESTION, got {result}"
        assert ctx.user_data.get('petrol_liters') == 5.0
        assert ctx.user_data.get('petrol_cost') is not None

    async def test_mobil_yes_flow(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        push_history(ctx, PETROL_QUESTION)
        upd = make_callback_update(TEST_USER, TEST_CHAT, "mobil_yes")
        result = await handle_mobil_question(upd, ctx)
        assert result == ENTER_MOBIL_LITERS

    async def test_mobil_no_flow(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        push_history(ctx, PETROL_QUESTION)
        upd = make_callback_update(TEST_USER, TEST_CHAT, "mobil_no")
        result = await handle_mobil_question(upd, ctx)
        assert result == MANAGER_QUESTION
        assert ctx.user_data.get('mobil_liters') == 0
        assert ctx.user_data.get('mobil_cost') == 0

    async def test_mobil_liters_entry(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        push_history(ctx, MOBIL_QUESTION)
        upd = make_text_update(TEST_USER, TEST_CHAT, "2")
        result = await handle_mobil_liters(upd, ctx)
        assert result == MANAGER_QUESTION, f"Expected MANAGER_QUESTION, got {result}"
        assert ctx.user_data.get('mobil_liters') == 2.0

    async def test_manager_yes_flow(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        push_history(ctx, MOBIL_QUESTION)
        upd = make_callback_update(TEST_USER, TEST_CHAT, "manager_yes")
        result = await handle_manager_question(upd, ctx)
        assert result == ENTER_MANAGER

    async def test_manager_no_flow(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        push_history(ctx, MOBIL_QUESTION)
        ctx.user_data['da_amount'] = 200
        upd = make_callback_update(TEST_USER, TEST_CHAT, "manager_no")
        result = await handle_manager_question(upd, ctx)
        assert result == SELECT_DISTRIBUTORS, f"Expected SELECT_DISTRIBUTORS, got {result}"

    async def test_manager_designation_then_distributors(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        push_history(ctx, MANAGER_QUESTION)
        ctx.user_data['da_amount'] = 200
        upd = make_text_update(TEST_USER, TEST_CHAT, "জনাব ম্যানেজার")
        result = await handle_manager_designation(upd, ctx)
        assert result == SELECT_DISTRIBUTORS
        assert ctx.user_data.get('others_designation') == "জনাব ম্যানেজার"

    async def test_distributor_selection_toggle(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        ctx.user_data['selected_dist_indices'] = []
        dists = await get_distributors()
        if not dists:
            await add_distributor("টেস্ট ডিস্ট্রিবিউটর")
            dists = await get_distributors()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "toggle_dist_0")
        result = await handle_distributor_selection(upd, ctx)
        assert result == SELECT_DISTRIBUTORS
        assert ctx.user_data['selected_dist_indices'] == [0]

    async def test_distributor_done_flow(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        dists = await get_distributors()
        if not dists:
            await add_distributor("টেস্ট ডিস্ট্রিবিউটর")
            dists = await get_distributors()
        ctx.user_data['selected_dist_indices'] = [0]
        ctx.user_data['entry_type'] = 'REGULAR'
        ctx.user_data['date'] = '2026-06-01'
        ctx.user_data['odo_start'] = 500
        ctx.user_data['odo_end'] = 564
        ctx.user_data['total_km'] = 64
        ctx.user_data['petrol_liters'] = 0
        ctx.user_data['petrol_cost'] = 0
        ctx.user_data['mobil_liters'] = 0
        ctx.user_data['mobil_cost'] = 0
        ctx.user_data['da_amount'] = 200
        ctx.user_data['others_designation'] = ""
        push_history(ctx, ENTER_MANAGER)
        upd = make_callback_update(TEST_USER, TEST_CHAT, "dist_done")
        result = await handle_distributor_selection(upd, ctx)
        # Should return CONFIRM_ENTRY (via show_confirmation)
        assert result == CONFIRM_ENTRY, f"Expected CONFIRM_ENTRY, got {result}"
        assert 'distributors_raw' in ctx.user_data
        assert 'total_cost' in ctx.user_data

    async def test_save_entry(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        ctx.user_data['entry_type'] = 'REGULAR'
        ctx.user_data['date'] = '2026-06-01'
        ctx.user_data['odo_start'] = 500
        ctx.user_data['odo_end'] = 564
        ctx.user_data['total_km'] = 64
        ctx.user_data['petrol_liters'] = 5.0
        ctx.user_data['petrol_cost'] = 704
        ctx.user_data['mobil_liters'] = 0
        ctx.user_data['mobil_cost'] = 0
        ctx.user_data['da_amount'] = 200
        ctx.user_data['others_designation'] = ""
        ctx.user_data['distributors_raw'] = []
        ctx.user_data['transport_fee'] = 0
        ctx.user_data['venu'] = ""
        ctx.user_data['total_cost'] = 904
        push_history(ctx, SELECT_DISTRIBUTORS)
        upd = make_callback_update(TEST_USER, TEST_CHAT, "confirm_save")
        result = await save_entry_callback(upd, ctx)
        # Should finish (not END because tour_count < 16, but returns None)
        entries = await get_entries(TEST_USER, 6, 2026)
        assert len(entries) == 1
        assert entries[0]['total_km'] == 64
        assert entries[0]['petrol_liters'] == 5.0
        assert entries[0]['total_cost'] == 904

    async def test_cancel_flow(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        upd = make_callback_update(TEST_USER, TEST_CHAT, "cancel")
        result = await cancel(upd, ctx)
        assert result == ConversationHandler.END

    async def test_back_from_select_distributors(self, clean_data):
        ctx = make_context()
        await add_user(TEST_USER)
        # pop_history pops 2 entries (current+previous). History before back:
        # [MANAGER_QUESTION, ENTER_MANAGER, SELECT_DISTRIBUTORS] — pop_history
        # pops SELECT_DISTRIBUTORS (current) then ENTER_MANAGER (return)
        push_history(ctx, MANAGER_QUESTION)
        push_history(ctx, ENTER_MANAGER)
        push_history(ctx, SELECT_DISTRIBUTORS)  # state on top to be popped
        ctx.user_data['da_amount'] = 200
        upd = make_callback_update(TEST_USER, TEST_CHAT, "back")
        result = await handle_distributor_selection(upd, ctx)
        assert result == ENTER_MANAGER, f"Expected ENTER_MANAGER, got {result}"
