import os
import asyncio
import jpype
import jpype.imports
from pathlib import Path
import subprocess
from telegram import Update
from telegram.ext import ContextTypes
from core.file_data_store import get_entries
from core.message_store import record_message, record_file_message
from core.audit_logger import log_event
from docx_generator.logsheet_generator import generate_for_user as generate_docx
from docx_generator.odt_generator import generate_for_user as generate_odt
from datetime import datetime
from bot.inline_keyboards import to_bn_number
from bot.text_resources import S
from bot.auth import require_auth

STORAGE_CHANNEL = os.getenv("STORAGE_CHANNEL_ID")
PDF_ENABLED = os.getenv("PDF_ENABLED", "true").lower() == "true"

FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "fonts"


async def _send_to_storage_channel(context: ContextTypes.DEFAULT_TYPE, file_path: Path, user_id: int, month: int, year: int, caption: str = None):
    if not STORAGE_CHANNEL:
        return
    try:
        kwargs = dict(
            chat_id=STORAGE_CHANNEL,
            document=file_path.open("rb"),
            filename=file_path.name,
        )
        if caption:
            kwargs['caption'] = caption
            kwargs['parse_mode'] = 'HTML'
        msg = await context.bot.send_document(**kwargs)
        file_id = msg.document.file_id
        from core.file_data_store import save_logsheet_file_id
        await save_logsheet_file_id(user_id, month, year, file_id, file_path.name)
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
        # ── Single progress message ─────────────────────────────────────
        gen_msg = S('report.generating_docx')
        if query:
            status_msg = await query.message.reply_text(gen_msg, parse_mode='HTML')
        else:
            status_msg = await update.message.reply_text(gen_msg, parse_mode='HTML')
        await record_message(user_id, status_msg.chat_id, status_msg.message_id, 'temporary')

        # ── Step 1: Generate DOCX ───────────────────────────────────────
        docx_path = Path(generate_docx(
            user_id=user_id,
            entries=entries,
            month=month,
            year=year,
            tpl_dir=Path("template_variants/DOCX"),
            out_dir=Path("output/DOCX"),
        ))

        # ── Step 2: Generate ODT ────────────────────────────────────────
        odt_path = Path(generate_odt(
            user_id=user_id,
            entries=entries,
            month=month,
            year=year,
            tpl_dir=Path("template_variants/ODT"),
            out_dir=Path("output/ODT"),
        ))

        # ── Step 3: Convert ODT → PDF ──────────────────────────────────
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

        # ── Delete progress message ────────────────────────────────────
        try:
            await context.bot.delete_message(chat_id=status_msg.chat_id, message_id=status_msg.message_id)
        except Exception:
            pass

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry_count = len(entries)

        # ── Step 4: Send DOCX to user + storage ─────────────────────────
        docx_meta = [
            f"\U0001f4c4 <b>Logsheet — {month}/{year}</b>",
            f"\U0001f550 Generated: <code>{now_str}</code>",
            f"\U0001f464 User: <code>{user_id}</code> ({user.full_name})",
            f"\U0001f4ca Entries: <b>{entry_count}</b>",
            f"\U0001f4c1 File: {docx_path.name}",
            f"\U0001f4c4 Type: DOCX",
        ]
        docx_caption = "\n".join(docx_meta)

        await _send_to_storage_channel(context, docx_path, user_id, month, year, caption=docx_caption)

        await log_event(context, 'docx_generated',
            user_id=user_id, username=user.full_name,
            details=f"Logsheet for {month}/{year} generated",
            changes=[
                f"Entries: <b>{entry_count}</b>",
                f"File: {docx_path.name}",
                f"Path: {docx_path}",
            ]
        )

        if query:
            sent_docx = await query.message.reply_document(
                document=docx_path.open('rb'), filename=docx_path.name,
                caption=docx_caption, parse_mode='HTML'
            )
        else:
            sent_docx = await update.message.reply_document(
                document=docx_path.open('rb'), filename=docx_path.name,
                caption=docx_caption, parse_mode='HTML'
            )
        await record_file_message(user_id, sent_docx.chat_id, sent_docx.message_id, 'docx', month, year, docx_path.name)
        await record_message(user_id, sent_docx.chat_id, sent_docx.message_id, 'temporary')

        # ── Step 5: Send ODT to storage ONLY (not to user) ──────────────
        odt_meta = [
            f"\U0001f4c4 <b>Logsheet — {month}/{year}</b>",
            f"\U0001f550 Generated: <code>{now_str}</code>",
            f"\U0001f464 User: <code>{user_id}</code> ({user.full_name})",
            f"\U0001f4ca Entries: <b>{entry_count}</b>",
            f"\U0001f4c1 File: {odt_path.name}",
            f"\U0001f4c4 Type: ODT",
        ]
        odt_caption = "\n".join(odt_meta)

        await _send_to_storage_channel(context, odt_path, user_id, month, year, caption=odt_caption)

        # ── Step 6: Send PDF to user + storage (if converted) ───────────
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

            await _send_to_storage_channel(context, pdf_path, user_id, month, year, caption=pdf_caption)

            if query:
                pdf_sent = await query.message.reply_document(
                    document=pdf_path.open('rb'), filename=pdf_path.name,
                    caption=pdf_caption, parse_mode='HTML'
                )
            else:
                pdf_sent = await update.message.reply_document(
                    document=pdf_path.open('rb'), filename=pdf_path.name,
                    caption=pdf_caption, parse_mode='HTML'
                )
            await record_file_message(user_id, pdf_sent.chat_id, pdf_sent.message_id, 'pdf', month, year, pdf_path.name)
            await record_message(user_id, pdf_sent.chat_id, pdf_sent.message_id, 'temporary')
            await log_event(context, 'pdf_generated',
                user_id=user_id, username=user.full_name,
                details=f"PDF for {month}/{year} generated from ODT",
                changes=[
                    f"Entries: <b>{entry_count}</b>",
                    f"File: {pdf_path.name}",
                    f"Source ODT: {odt_path.name}",
                ]
            )

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
    """Convert ODT (or DOCX) to PDF via Aspose.Words."""
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
