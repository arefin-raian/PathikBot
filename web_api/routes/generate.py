"""Generate a monthly logsheet (DOCX / ODT / PDF) and stream it back."""
import os
import asyncio
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from core import file_data_store as store
from docx_generator.logsheet_generator import generate_for_user as generate_docx
from docx_generator.odt_generator import generate_for_user as generate_odt
from web_api.deps import current_user

router = APIRouter(prefix="/generate", tags=["generate"])


_MEDIA = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "odt":  "application/vnd.oasis.opendocument.text",
    "pdf":  "application/pdf",
}


@router.get("/logsheet")
async def generate_logsheet(
    month: int,
    year: int,
    format: str = Query("docx", pattern="^(docx|odt|pdf)$"),
    user=Depends(current_user),
):
    uid = user["user_id"]
    entries = await store.get_entries(uid, month, year)
    prefs = await store.get_user_prefs(uid)
    if len(entries) < 3:
        raise HTTPException(400, f"Need at least 3 entries (have {len(entries)})")
    if len(entries) > 30:
        raise HTTPException(400, f"At most 30 entries supported (have {len(entries)})")

    fmt = format.lower()
    try:
        if fmt == "docx":
            out = Path("output/DOCX"); out.mkdir(parents=True, exist_ok=True)
            path = Path(generate_docx(uid, entries, month, year, Path("template_variants/DOCX"), out, prefs=prefs))
        elif fmt == "odt":
            out = Path("output/ODT"); out.mkdir(parents=True, exist_ok=True)
            path = Path(generate_odt(uid, entries, month, year, Path("template_variants/ODT"), out))
        else:  # pdf
            out = Path("output/ODT"); out.mkdir(parents=True, exist_ok=True)
            odt_path = Path(generate_odt(uid, entries, month, year, Path("template_variants/ODT"), out))
            pdf_path = odt_path.with_suffix(".pdf")
            # Reuse the bot's converter (Aspose via JPype, then LibreOffice fallback).
            from bot.handlers.report import _convert_to_pdf  # local import to avoid telegram import at module load
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _convert_to_pdf, str(odt_path), str(pdf_path))
            if not pdf_path.exists():
                raise RuntimeError("PDF conversion produced no file")
            path = pdf_path
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")

    return FileResponse(
        str(path),
        media_type=_MEDIA[fmt],
        filename=os.path.basename(str(path)),
    )
