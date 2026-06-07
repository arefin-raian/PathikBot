"""Report generation tests using mock PTB objects."""
import sys, os, json, glob, tempfile
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from core.file_data_store import (
    add_user, add_entry, init_db, OWNER_ID
)

TEST_USER = 554433004
TEST_CHAT = -100554433


@pytest.fixture(autouse=True)
def clean_data():
    os.makedirs('data', exist_ok=True)
    os.makedirs('data/user_prefs', exist_ok=True)
    for f in glob.glob('data/users.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/entries_554433*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/user_prefs/554433*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/message_log/554433*.json'):
        try: os.remove(f)
        except: pass
    yield
    for f in glob.glob('data/users.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/entries_554433*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/user_prefs/554433*.json'):
        try: os.remove(f)
        except: pass
    for f in glob.glob('data/message_log/554433*.json'):
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


from bot.handlers.report import generate_report_handler


@pytest.mark.asyncio
class TestReportFlow:

    ENTRY = {'date': '2026-06-01', 'total_km': 64,
             'odo_start': 0, 'odo_end': 64, 'entry_type': 'REGULAR',
             'total_cost': 903, 'petrol_liters': 5.0, 'petrol_cost': 703,
             'mobil_liters': 0, 'mobil_cost': 0, 'da_amount': 200,
             'distributors_raw': [], 'venue': '', 'transport_fee': 0,
             'others_designation': ''}

    @patch('bot.handlers.report.generate_docx')
    @patch('bot.handlers.report.generate_odt')
    async def test_generate_report_command_no_entries(self, mock_odt, mock_docx, clean_data):
        """No entries — should not try to generate."""
        await add_user(TEST_USER)
        mock_docx.return_value = ''
        mock_odt.return_value = ''
        ctx = make_context()
        upd = make_text_update(TEST_USER, TEST_CHAT, "/generate")
        result = await generate_report_handler(upd, ctx)
        assert result is None

    @patch('bot.handlers.report.generate_docx')
    @patch('bot.handlers.report.generate_odt')
    async def test_generate_report_command_with_entries(self, mock_odt, mock_docx, clean_data):
        """Generate report via command with entries."""
        await add_user(TEST_USER)
        await add_entry(TEST_USER, self.ENTRY)
        mock_docx.return_value = 'dummy_output.docx'
        mock_odt.return_value = 'dummy_output.odt'
        ctx = make_context()
        upd = make_text_update(TEST_USER, TEST_CHAT, "/generate")
        result = await generate_report_handler(upd, ctx)
        assert result is None
        mock_docx.assert_called_once()
        mock_odt.assert_called_once()

    @patch('bot.handlers.report.generate_docx')
    @patch('bot.handlers.report.generate_odt')
    async def test_generate_report_callback(self, mock_odt, mock_docx, clean_data):
        """Generate report via callback."""
        await add_user(TEST_USER)
        await add_entry(TEST_USER, self.ENTRY)
        mock_docx.return_value = 'dummy_output.docx'
        mock_odt.return_value = 'dummy_output.odt'
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "generate_report")
        result = await generate_report_handler(upd, ctx)
        assert result is None
        mock_docx.assert_called_once()
        mock_odt.assert_called_once()

    @patch('bot.handlers.report.generate_docx')
    @patch('bot.handlers.report.generate_odt')
    async def test_generate_report_specific_month(self, mock_odt, mock_docx, clean_data):
        """Generate report for specific month."""
        await add_user(TEST_USER)
        await add_entry(TEST_USER, self.ENTRY)
        mock_docx.return_value = 'dummy_output.docx'
        mock_odt.return_value = 'dummy_output.odt'
        ctx = make_context()
        upd = make_callback_update(TEST_USER, TEST_CHAT, "generate_2026_6")
        result = await generate_report_handler(upd, ctx)
        assert result is None
        mock_docx.assert_called_once()
        mock_odt.assert_called_once()
