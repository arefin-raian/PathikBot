import os
import sys
import subprocess
import tempfile
import shutil
import asyncio
import platform
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes
from core.file_data_store import get_entries
from core.message_store import record_file_message
from core.audit_logger import log_event
from docx_generator.logsheet_generator import generate_for_user
from datetime import datetime
from bot.inline_keyboards import to_bn_number
from bot.text_resources import S
from bot.auth import require_auth

STORAGE_CHANNEL = os.getenv("STORAGE_CHANNEL_ID")
PDF_ENABLED = os.getenv("PDF_ENABLED", "false").lower() == "true"
SOFFICE_PATH = os.getenv("SOFFICE_PATH", "soffice")

FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "fonts"


def _ensure_fonts_installed():
    """Install SutonnyMJ fonts so LibreOffice can find them during PDF conversion.

    On Windows, fonts are copied to %APPDATA%/LibreOffice/4/user/fonts/
    so that LibreOffice picks them up without admin privileges.
    On Linux/macOS, they are copied to ~/.fonts/ and fc-cache is run.
    Skips if the target already has the font (checked by filename).
    """
    if not FONTS_DIR.is_dir():
        return

    system = platform.system()
    if system == "Windows":
        lo_user_fonts = Path(os.environ.get("APPDATA", "")) / "LibreOffice" / "4" / "user" / "fonts"
    elif system == "Linux":
        lo_user_fonts = Path.home() / ".fonts"
    elif system == "Darwin":
        lo_user_fonts = Path.home() / "Library" / "Fonts"
    else:
        return

    lo_user_fonts.mkdir(parents=True, exist_ok=True)

    installed = False
    for ttf in FONTS_DIR.glob("*.ttf"):
        dest = lo_user_fonts / ttf.name
        if not dest.exists():
            try:
                shutil.copy2(str(ttf), str(dest))
                installed = True
            except PermissionError:
                pass

    if installed and system == "Linux":
        subprocess.run(["fc-cache", "-f"], capture_output=True, timeout=30)
    elif installed and system == "Darwin":
        subprocess.run(["atsutil", "databases", "-remove"], capture_output=True, timeout=30)

async def _send_to_storage_channel(context: ContextTypes.DEFAULT_TYPE, docx_path: Path, user_id: int, month: int, year: int):
    """Send the generated file to the storage channel and save file_id in MongoDB."""
    if not STORAGE_CHANNEL:
        return
    try:
        msg = await context.bot.send_document(
            chat_id=STORAGE_CHANNEL,
            document=docx_path.open("rb"),
            filename=docx_path.name,
        )
        file_id = msg.document.file_id
        from core.file_data_store import save_logsheet_file_id
        await save_logsheet_file_id(user_id, month, year, file_id, docx_path.name)
    except Exception:
        pass


async def generate_report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_auth(update, context): return
    query = update.callback_query
    if query:
        await query.answer()

    month, year = None, None
    if query and query.data and query.data.startswith("generate_"):
        parts = query.data.split("_")
        if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
            year, month = int(parts[1]), int(parts[2])

    if not month or not year:
        now = datetime.now()
        month, year = now.month, now.year

    user_id = update.effective_user.id
    user = update.effective_user
    entries = await get_entries(user_id, month, year)
    if not entries:
        msg = S('report.no_entries', month=to_bn_number(month), year=to_bn_number(year))
        if query:
            await query.edit_message_text(msg, parse_mode='HTML')
        else:
            await update.message.reply_text(msg, parse_mode='HTML')
        return

    try:
        output_path = generate_for_user(
            user_id=user_id,
            entries=entries,
            month=month,
            year=year,
            tpl_dir=Path("generated_logsheets"),
            out_dir=Path("outputs"),
        )

        docx_path = Path(output_path)

        await _send_to_storage_channel(context, docx_path, user_id, month, year)

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry_count = len(entries)
        file_type = "DOCX"
        filename_short = docx_path.name
        metadata_lines = [
            f"\U0001f4c4 <b>Logsheet — {month}/{year}</b>",
            f"\U0001f550 Generated: <code>{now_str}</code>",
            f"\U0001f464 User: <code>{user_id}</code> ({user.full_name})",
            f"\U0001f4ca Entries: <b>{entry_count}</b>",
            f"\U0001f4c1 File: {filename_short}",
            f"\U0001f4c4 Type: {file_type}",
        ]
        caption = "\n".join(metadata_lines)

        await log_event(context, 'docx_generated',
            user_id=user_id, username=user.full_name,
            details=f"Logsheet for {month}/{year} generated",
            changes=[
                f"Entries: <b>{entry_count}</b>",
                f"File: {filename_short}",
                f"Path: {docx_path}",
            ]
        )

        if query:
            sent = await query.message.reply_document(
                document=docx_path.open('rb'), filename=docx_path.name,
                caption=caption, parse_mode='HTML'
            )
        else:
            sent = await update.message.reply_document(
                document=docx_path.open('rb'), filename=docx_path.name,
                caption=caption, parse_mode='HTML'
            )
        await record_file_message(user_id, sent.chat_id, sent.message_id, 'docx', month, year, docx_path.name)

        # PDF conversion (toggle with PDF_ENABLED env var)
        if PDF_ENABLED:
            _ensure_fonts_installed()
            pdf_path = docx_path.with_suffix('.pdf')
            gen_pdf_msg = S('report.generating_pdf')
            if query:
                pdf_status = await query.message.reply_text(gen_pdf_msg, parse_mode='HTML')
            else:
                pdf_status = await update.message.reply_text(gen_pdf_msg, parse_mode='HTML')
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _convert_to_pdf, str(docx_path), str(pdf_path))
                pdf_caption = "\n".join([
                    f"\U0001f4d5 <b>Logsheet — {month}/{year}</b>",
                    f"\U0001f550 Generated: <code>{now_str}</code>",
                    f"\U0001f464 User: <code>{user_id}</code> ({user.full_name})",
                    f"\U0001f4ca Entries: <b>{entry_count}</b>",
                    f"\U0001f4c1 File: {pdf_path.name}",
                    f"\U0001f4d5 Type: PDF",
                ])
                if query:
                    await query.message.reply_document(
                        document=pdf_path.open('rb'), filename=pdf_path.name,
                        caption=pdf_caption, parse_mode='HTML'
                    )
                else:
                    await update.message.reply_document(
                        document=pdf_path.open('rb'), filename=pdf_path.name,
                        caption=pdf_caption, parse_mode='HTML'
                    )
                await log_event(context, 'pdf_generated',
                    user_id=user_id, username=user.full_name,
                    details=f"PDF for {month}/{year} generated",
                    changes=[
                        f"Entries: <b>{entry_count}</b>",
                        f"File: {pdf_path.name}",
                    ]
                )
            except Exception as pdf_err:
                await pdf_status.edit_text(S('report.pdf_error', error=str(pdf_err)), parse_mode='HTML')
                await log_event(context, 'warning',
                    user_id=user_id, username=user.full_name,
                    details=f"PDF conversion failed: {pdf_err}"
                )

    except Exception as e:
        error_msg = S('report.error', error=str(e))
        await log_event(context, 'critical_error',
            user_id=user_id, username=user.full_name,
            details=f"DOCX generation failed: {e}"
        )
        if query:
            await query.edit_message_text(error_msg, parse_mode='HTML')
        else:
            await update.message.reply_text(error_msg, parse_mode='HTML')


def _convert_to_pdf(docx_path: str, pdf_path: str) -> None:
    """Convert DOCX to PDF using LibreOffice headless mode.
    
    Falls back to commented docx2pdf method if soffice is unavailable.
    Set SOFFICE_PATH env var to override the soffice binary location.
    """
    _ensure_fonts_installed()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_docx = os.path.join(tmpdir, os.path.basename(docx_path))
        shutil.copy2(docx_path, tmp_docx)
        result = subprocess.run(
            [SOFFICE_PATH, "--headless", "--norestore", "--nofirststartwizard",
             "--convert-to", "pdf", "--outdir", tmpdir, tmp_docx],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise RuntimeError(f"soffice exited {result.returncode}: {result.stderr}")
        tmp_pdf = os.path.join(tmpdir, os.path.basename(pdf_path))
        if not os.path.exists(tmp_pdf):
            raise RuntimeError(f"LibreOffice did not create PDF output")
        shutil.copy2(tmp_pdf, pdf_path)

# def _convert_to_pdf_docx2pdf(docx_path, pdf_path):
#     """Windows-only: uses MS Word via win32com. Kept for reference."""
#     from docx2pdf import convert
#     convert(docx_path, pdf_path)
