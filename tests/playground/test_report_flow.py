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


class TestStripBlankPages:
    """Bug 2 safety net: ``_strip_blank_pages`` removes template-artifact
    blank pages from ODT-converted PDFs. These tests mock pypdf's PdfReader /
    PdfWriter so we can exercise the page-classification logic without needing
    LibreOffice or a real PDF fixture."""

    @staticmethod
    def _blank_page():
        class _Blank:
            def extract_text(self):
                return ""
            def get(self, key, default=None):
                return {}
        return _Blank()

    @staticmethod
    def _text_page(text):
        class _Text:
            def __init__(self, t):
                self._t = t
            def extract_text(self):
                return self._t
            def get(self, key, default=None):
                return {}
        return _Text(text)

    @staticmethod
    def _xobject_only_page():
        """A page with only an embedded image: no extractable text but a
        /XObject resource. Must NOT be classified as blank."""
        class _ImagePage:
            def extract_text(self):
                return ""
            def get(self, key, default=None):
                if key == "/Resources":
                    return {"/XObject": True}
                return default
        return _ImagePage()

    def test_strip_removes_blank_pages_around_text(self, monkeypatch, tmp_path):
        from bot.handlers import report
        import pypdf

        pdf = tmp_path / "out.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")

        # Mirrors the failing layout: frame-anchor pages on either side of
        # real content pages.
        pages = [
            self._blank_page(),
            self._text_page("page 1 content"),
            self._blank_page(),
            self._text_page("page 3 content"),
        ]

        monkeypatch.setattr(
            pypdf, "PdfReader",
            lambda path: type("_R", (), {"pages": pages})(),
        )

        written_writers = []

        def _writer_factory():
            class _Writer:
                def __init__(self):
                    self.pages = []
                    written_writers.append(self)
                def add_page(self, p):
                    self.pages.append(p)
                def write(self, fh):
                    fh.write(b"%PDF-stripped")
            return _Writer()
        monkeypatch.setattr(pypdf, "PdfWriter", _writer_factory)

        report._strip_blank_pages(str(pdf))

        assert len(written_writers) == 1
        assert len(written_writers[0].pages) == 2
        assert pdf.read_bytes() == b"%PDF-stripped"

    def test_strip_keeps_page_with_xobject_only(self, monkeypatch, tmp_path):
        """Image-only pages (no extractable text, has /XObject) must NOT be
        removed — otherwise image-heavy reports would lose content."""
        from bot.handlers import report
        import pypdf

        pdf = tmp_path / "out.pdf"
        original = b"%PDF-original\n"
        pdf.write_bytes(original)

        pages = [self._xobject_only_page(), self._xobject_only_page()]

        monkeypatch.setattr(
            pypdf, "PdfReader",
            lambda path: type("_R", (), {"pages": pages})(),
        )
        monkeypatch.setattr(pypdf, "PdfWriter", lambda: type("_W", (), {
            "pages": [],
            "add_page": lambda self, p: None,
            "write": lambda self, fh: None,
        })())

        report._strip_blank_pages(str(pdf))

        # Nothing should have been written (no blank pages existed).
        assert pdf.read_bytes() == original

    def test_strip_does_not_write_empty_pdf(self, monkeypatch, tmp_path):
        """If every page classifies as blank, leave the file alone rather
        than rewrite it as zero pages (Bijoy glyph pages sometimes extract
        as empty text — better to keep the original than to truncate it)."""
        from bot.handlers import report
        import pypdf

        pdf = tmp_path / "out.pdf"
        original = b"%PDF-original-keeps-blank-pages\n"
        pdf.write_bytes(original)

        pages = [self._blank_page(), self._blank_page()]
        write_calls = []

        class _Writer:
            def __init__(self):
                self.pages = []
            def add_page(self, p):
                self.pages.append(p)
            def write(self, fh):
                write_calls.append(fh)

        monkeypatch.setattr(
            pypdf, "PdfReader",
            lambda path: type("_R", (), {"pages": pages})(),
        )
        monkeypatch.setattr(pypdf, "PdfWriter", _Writer)

        report._strip_blank_pages(str(pdf))

        assert write_calls == [], (
            "_strip_blank_pages must not write a 0-page PDF — "
            "would silently truncate the file."
        )
        assert pdf.read_bytes() == original

    def test_strip_leaves_file_alone_when_nothing_changes(self, monkeypatch, tmp_path):
        """Conservation guarantee: a (text page) → (text page) PDF must be
        byte-identical before and after, since no blank page exists."""
        from bot.handlers import report
        import pypdf

        pdf = tmp_path / "out.pdf"
        original = b"%PDF-text-only\n"
        pdf.write_bytes(original)

        pages = [self._text_page("a"), self._text_page("b")]
        write_calls = []

        class _Writer:
            def __init__(self):
                self.pages = []
            def add_page(self, p):
                self.pages.append(p)
            def write(self, fh):
                write_calls.append(fh)

        monkeypatch.setattr(
            pypdf, "PdfReader",
            lambda path: type("_R", (), {"pages": pages})(),
        )
        monkeypatch.setattr(pypdf, "PdfWriter", _Writer)

        report._strip_blank_pages(str(pdf))

        assert write_calls == []
        assert pdf.read_bytes() == original

    def test_strip_handles_unreadable_pdf_without_raising(self, monkeypatch, tmp_path):
        """A corrupt/unreadable PDF must not bubble up; the PDF stays as-is
        and the conversion path still has the (un-stripped) file to send."""
        from bot.handlers import report
        import pypdf

        pdf = tmp_path / "out.pdf"
        original = b"%PDF-unreadable\n"
        pdf.write_bytes(original)

        def _bad_reader(_):
            raise RuntimeError("not a PDF")
        monkeypatch.setattr(pypdf, "PdfReader", _bad_reader)
        # PdfWriter should never be reached.
        def _should_not_be_called():
            raise AssertionError("PdfWriter must not be invoked when PdfReader fails")
        monkeypatch.setattr(pypdf, "PdfWriter", _should_not_be_called)

        report._strip_blank_pages(str(pdf))

        assert pdf.read_bytes() == original

    def test_convert_to_pdf_invokes_strip_after_jpype_success(
        self, monkeypatch, tmp_path,
    ):
        """End-to-end wiring: when jpype conversion succeeds,
        `_strip_blank_pages` MUST run (this is the actual fix path)."""
        from bot.handlers import report

        called = []
        monkeypatch.setattr(
            report, "_convert_via_jpype",
            lambda i, o: called.append(("jpype", i, o)) or None,
        )
        monkeypatch.setattr(
            report, "_convert_via_libreoffice",
            lambda i, o: called.append(("lo", i, o)) or (_ for _ in ()).throw(
                AssertionError("LibreOffice path should not run on jpype success")
            ),
        )
        monkeypatch.setattr(
            report, "_strip_blank_pages",
            lambda p: called.append(("strip", p)),
        )

        report._convert_to_pdf(str(tmp_path / "in.odt"), str(tmp_path / "out.pdf"))

        assert [c[0] for c in called] == ["jpype", "strip"]

    def test_convert_to_pdf_invokes_strip_after_libreoffice_fallback(
        self, monkeypatch, tmp_path,
    ):
        """When jpype fails, LibreOffice runs, AND `_strip_blank_pages`
        still runs afterwards."""
        from bot.handlers import report

        called = []
        monkeypatch.setattr(
            report, "_convert_via_jpype",
            lambda i, o: (_ for _ in ()).throw(RuntimeError("no JVM")),
        )
        monkeypatch.setattr(
            report, "_convert_via_libreoffice",
            lambda i, o: called.append(("lo", i, o)),
        )
        monkeypatch.setattr(
            report, "_strip_blank_pages",
            lambda p: called.append(("strip", p)),
        )

        report._convert_to_pdf(str(tmp_path / "in.odt"), str(tmp_path / "out.pdf"))

        assert [c[0] for c in called] == ["lo", "strip"]
