import os
import asyncio
import jpype
import jpype.imports
from pathlib import Path
import subprocess
import tempfile
import shutil
import platform
from telegram import Update
from telegram.ext import ContextTypes
from core.file_data_store import get_entries, get_user_prefs
from core.message_store import record_message, record_file_message
from core.audit_logger import log_event, build_event_message
from docx_generator.logsheet_generator import generate_for_user as generate_docx
from docx_generator.odt_generator import generate_for_user as generate_odt
from datetime import datetime
from core.timezone import now_dhaka, dhaka_timestamp
from bot.inline_keyboards import to_bn_number
from bot.text_resources import S
from bot.auth import require_auth

STORAGE_CHANNEL = os.getenv("STORAGE_CHANNEL_ID")
PDF_ENABLED = os.getenv("PDF_ENABLED", "true").lower() == "true"
SOFFICE_PATH = os.getenv("SOFFICE_PATH", "soffice")

FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "fonts"

BAR_WIDTH = 20


def _progress_bar(percent: int) -> str:
    filled = percent * BAR_WIDTH // 100
    empty = BAR_WIDTH - filled
    return "█" * filled + "░" * empty


async def _update_progress(context, chat_id: int, msg_id: int, step_num: int, percent: int, done: bool = False):
    step = S(f"report.progress.steps.{step_num}")
    bar = _progress_bar(percent)
    if done:
        text = (
            f"<b>{S('report.progress.title')}</b>\n\n"
            f"<b>Step {step_num}:</b> {step['name']}\n"
            f"[{bar}] {percent}%\n"
            f"<i>{step['status']}</i>\n\n"
            f"<b>{S('report.progress.done')}</b>"
        )
    else:
        text = (
            f"<b>{S('report.progress.title')}</b>\n\n"
            f"<b>Step {step_num}:</b> {step['name']}\n"
            f"[{bar}] {percent}%\n"
            f"<i>{step['status']}</i>"
        )
    await context.bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, parse_mode="HTML")


async def _send_to_storage_channel(context: ContextTypes.DEFAULT_TYPE, file_path: Path, user_id: int, month: int, year: int, caption: str = None, gen_event: str = None, gen_kw: dict = None):
    """Send a file to the storage channel with the detailed logsheet info as the
    file caption, then post the corresponding "Generated" log message as a reply
    to that file message."""
    if not STORAGE_CHANNEL:
        return
    try:
        msg = await context.bot.send_document(
            chat_id=STORAGE_CHANNEL,
            document=file_path.open("rb"),
            filename=file_path.name,
            caption=caption,
            parse_mode='HTML' if caption else None,
        )
        file_id = msg.document.file_id
        from core.file_data_store import save_logsheet_file_id
        await save_logsheet_file_id(user_id, month, year, file_id, file_path.name)
        if gen_event:
            await msg.reply_text(
                build_event_message(gen_event, **(gen_kw or {})),
                parse_mode='HTML',
            )
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
        now = now_dhaka()
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
        # ── Send initial progress message at step 1 / 20% ───────────────
        if query:
            prog_msg = await query.message.reply_text("...", parse_mode='HTML')
        else:
            prog_msg = await update.message.reply_text("...", parse_mode='HTML')
        chat_id = prog_msg.chat_id
        msg_id = prog_msg.message_id
        await record_message(user_id, chat_id, msg_id, 'temporary')
        await _update_progress(context, chat_id, msg_id, 1, 20)

        # ── Step 2 (40%): Load template ─────────────────────────────────
        await _update_progress(context, chat_id, msg_id, 2, 40)

        # ── Generate DOCX (happens during step 2→3) ────────────────────
        prefs = await get_user_prefs(user_id)
        docx_path = Path(generate_docx(
            user_id=user_id,
            entries=entries,
            month=month,
            year=year,
            tpl_dir=Path("template_variants/DOCX"),
            out_dir=Path("output/DOCX"),
            prefs=prefs,
        ))

        # ── Step 3 (60%): Processing data ───────────────────────────────
        await _update_progress(context, chat_id, msg_id, 3, 60)

        # ── Generate ODT ───────────────────────────────────────────────
        odt_path = Path(generate_odt(
            user_id=user_id,
            entries=entries,
            month=month,
            year=year,
            tpl_dir=Path("template_variants/ODT"),
            out_dir=Path("output/ODT"),
            prefs=prefs,
        ))

        # ── Convert ODT → PDF ──────────────────────────────────────────
        pdf_path = None
        if PDF_ENABLED:
            pdf_path = odt_path.with_suffix('.pdf')
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _convert_to_pdf, str(odt_path), str(pdf_path))
            except Exception as pdf_err:
                await log_event(context, 'warning',
                    user_id=user_id, username=user.full_name,
                    details=f"ODT→PDF conversion failed: {pdf_err}"
                )
                pdf_path = None

        # ── Step 4 (80%): Generating files ──────────────────────────────
        await _update_progress(context, chat_id, msg_id, 4, 80)

        now_str = dhaka_timestamp()
        entry_count = len(entries)

        # ── Send to storage channel (background, user doesn't see) ──────
        docx_meta = [
            f"\U0001f4c4 <b>Logsheet — {month}/{year}</b>",
            f"\U0001f550 Generated: <code>{now_str}</code>",
            f"\U0001f464 User: <code>{user_id}</code> ({user.full_name})",
            f"\U0001f4ca Entries: <b>{entry_count}</b>",
            f"\U0001f4c1 File: {docx_path.name}",
            f"\U0001f4c4 Type: DOCX",
        ]
        docx_caption = "\n".join(docx_meta)
        await _send_to_storage_channel(
            context, docx_path, user_id, month, year, caption=docx_caption,
            gen_event='docx_generated',
            gen_kw=dict(
                user_id=user_id, username=user.full_name,
                details=f"Logsheet for {month}/{year} generated",
                changes=[
                    f"Entries: <b>{entry_count}</b>",
                    f"File: {docx_path.name}",
                    f"Path: {docx_path}",
                ],
            ),
        )

        odt_meta = [
            f"\U0001f4c4 <b>Logsheet — {month}/{year}</b>",
            f"\U0001f550 Generated: <code>{now_str}</code>",
            f"\U0001f464 User: <code>{user_id}</code> ({user.full_name})",
            f"\U0001f4ca Entries: <b>{entry_count}</b>",
            f"\U0001f4c1 File: {odt_path.name}",
            f"\U0001f4c4 Type: ODT",
        ]
        odt_caption = "\n".join(odt_meta)
        await _send_to_storage_channel(
            context, odt_path, user_id, month, year, caption=odt_caption,
            gen_event='odt_generated',
            gen_kw=dict(
                user_id=user_id, username=user.full_name,
                details=f"Logsheet for {month}/{year} generated",
                changes=[
                    f"Entries: <b>{entry_count}</b>",
                    f"File: {odt_path.name}",
                    f"Path: {odt_path}",
                ],
            ),
        )

        pdf_caption = None
        if pdf_path and pdf_path.exists():
            pdf_meta = [
                f"\U0001f4d5 <b>Logsheet — {month}/{year}</b>",
                f"\U0001f550 Generated: <code>{now_str}</code>",
                f"\U0001f464 User: <code>{user_id}</code> ({user.full_name})",
                f"\U0001f4ca Entries: <b>{entry_count}</b>",
                f"\U0001f4c1 File: {pdf_path.name}",
                f"\U0001f4d5 Type: PDF",
            ]
            pdf_caption = "\n".join(pdf_meta)
            await _send_to_storage_channel(
                context, pdf_path, user_id, month, year, caption=pdf_caption,
                gen_event='pdf_generated',
                gen_kw=dict(
                    user_id=user_id, username=user.full_name,
                    details=f"PDF for {month}/{year} generated from ODT",
                    changes=[
                        f"Entries: <b>{entry_count}</b>",
                        f"File: {pdf_path.name}",
                        f"Source ODT: {odt_path.name}",
                    ],
                ),
            )

        # ── Step 5 (100%): Finalizing & uploading ───────────────────────
        await _update_progress(context, chat_id, msg_id, 5, 100, done=True)

        # ── Delete progress message ────────────────────────────────────
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

        # ── Send files to user (both at once, after 100%) ──────────────
        reply_target = query.message if query else update.message

        sent_docx = await reply_target.reply_document(
            document=docx_path.open('rb'), filename=docx_path.name,
            caption=docx_caption, parse_mode='HTML'
        )
        await record_file_message(user_id, sent_docx.chat_id, sent_docx.message_id, 'docx', month, year, docx_path.name)
        await record_message(user_id, sent_docx.chat_id, sent_docx.message_id, 'temporary')

        if pdf_caption:
            sent_pdf = await reply_target.reply_document(
                document=pdf_path.open('rb'), filename=pdf_path.name,
                caption=pdf_caption, parse_mode='HTML'
            )
            await record_file_message(user_id, sent_pdf.chat_id, sent_pdf.message_id, 'pdf', month, year, pdf_path.name)
            await record_message(user_id, sent_pdf.chat_id, sent_pdf.message_id, 'temporary')

    except Exception as e:
        error_msg = S('report.error', error=str(e))
        await log_event(context, 'critical_error',
            user_id=user_id, username=user.full_name,
            details=f"Logsheet generation failed: {e}"
        )
        if query:
            await query.edit_message_text(error_msg, parse_mode='HTML')
        else:
            await update.message.reply_text(error_msg, parse_mode='HTML')


def _find_jvm_dll() -> str:
    if os.name == "nt":
        lib_name = "jvm.dll"
    else:
        lib_name = "libjvm.so"

    java_home = os.environ.get("JAVA_HOME") or os.environ.get("JDK_HOME")
    if java_home:
        for sub in ("jre", ""):
            candidate = Path(java_home) / sub / "bin" / "server" / lib_name
            if candidate.is_file():
                return str(candidate)

    if os.name == "nt":
        for base in [
            Path("C:/Program Files/Eclipse Adoptium"),
            Path("C:/Program Files/Java"),
        ]:
            if not base.is_dir():
                continue
            for jdk_dir in base.iterdir():
                candidate = jdk_dir / "bin" / "server" / lib_name
                if candidate.is_file():
                    return str(candidate)

    try:
        if os.name == "nt":
            result = subprocess.run(["where", "java"], capture_output=True, text=True, timeout=5)
            java_path = result.stdout.strip().splitlines()[0]
            if java_path:
                home = Path(java_path).resolve().parent.parent
                for sub in ("jre", ""):
                    candidate = home / sub / "bin" / "server" / lib_name
                    if candidate.is_file():
                        return str(candidate)
        else:
            result = subprocess.run(
                ["sh", "-c", "readlink -f $(which java)"],
                capture_output=True, text=True, timeout=5,
            )
            java_path = result.stdout.strip()
            if java_path:
                # readlink resolves /usr/bin/java -> /etc/alternatives/java -> /usr/lib/jvm/...
                home = Path(java_path).resolve().parent.parent
                for sub in ("jre", ""):
                    candidate = home / sub / "lib" / "server" / lib_name
                    if candidate.is_file():
                        return str(candidate)
    except Exception:
        pass

    raise RuntimeError(
        f"No JVM shared library file ({lib_name}) found. "
        "Set the JAVA_HOME environment variable to your JDK installation path."
    )


def _convert_to_pdf(input_path: str, pdf_path: str) -> None:
    """Convert DOCX/ODT to PDF. Tries Aspose.Words (JPype + JAR) first,
    falls back to LibreOffice headless if JVM is unavailable."""
    try:
        _convert_via_jpype(input_path, pdf_path)
        return
    except Exception as jvm_err:
        import logging
        logging.getLogger(__name__).warning(
            f"JVM/Aspose conversion failed, falling back to LibreOffice: {jvm_err}"
        )
    _convert_via_libreoffice(input_path, pdf_path)


def _convert_via_jpype(input_path: str, pdf_path: str) -> None:
    jar_path = str(Path(__file__).resolve().parent.parent.parent / 'aspose-words-20.12-jdk17-cracked.jar')

    if not jpype.isJVMStarted():
        jvm_path = _find_jvm_dll()
        jpype.startJVM(jvm_path, classpath=[jar_path], convertStrings=True)

    from com.aspose.words import Document, SaveFormat, FontSettings

    font_settings = FontSettings()
    if FONTS_DIR.is_dir():
        font_settings.setFontsFolder(str(FONTS_DIR), True)

    doc = Document(input_path)
    doc.setFontSettings(font_settings)
    doc.save(pdf_path, SaveFormat.PDF)


def _convert_via_libreoffice(input_path: str, pdf_path: str) -> None:
    """Convert DOCX/ODT to PDF using LibreOffice headless mode."""
    _ensure_fonts_installed()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_docx = os.path.join(tmpdir, os.path.basename(input_path))
        shutil.copy2(input_path, tmp_docx)
        result = subprocess.run(
            [SOFFICE_PATH, "--headless", "--norestore", "--nofirststartwizard",
             "--convert-to", "pdf", "--outdir", tmpdir, tmp_docx],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise RuntimeError(f"soffice exited {result.returncode}: {result.stderr}")
        tmp_pdf = os.path.join(tmpdir, os.path.basename(pdf_path))
        if not os.path.exists(tmp_pdf):
            raise RuntimeError("LibreOffice did not create PDF output")
        shutil.copy2(tmp_pdf, pdf_path)


def _ensure_fonts_installed() -> None:
    """Install SutonnyMJ fonts so LibreOffice can find them during PDF conversion."""
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
    for ttf in FONTS_DIR.glob("*.ttf") if FONTS_DIR.is_dir() else []:
        dest = lo_user_fonts / ttf.name
        if dest.exists():
            continue
        try:
            shutil.copy2(str(ttf), str(dest))
            installed = True
        except PermissionError:
            pass

    if installed and system == "Linux":
        subprocess.run(["fc-cache", "-f"], capture_output=True, timeout=30)
    elif installed and system == "Darwin":
        subprocess.run(["atsutil", "databases", "-remove"], capture_output=True, timeout=30)
