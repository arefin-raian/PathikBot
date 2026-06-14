"""Generate a monthly logsheet DOCX and stream it back."""
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from core import file_data_store as store
from docx_generator.logsheet_generator import generate_for_user
from web_api.deps import current_user

router = APIRouter(prefix="/generate", tags=["generate"])


@router.get("/logsheet")
async def generate_logsheet(month: int, year: int, user=Depends(current_user)):
    uid = user["user_id"]
    entries = await store.get_entries(uid, month, year)
    if len(entries) < 3:
        raise HTTPException(400, f"Need at least 3 entries (have {len(entries)})")
    if len(entries) > 30:
        raise HTTPException(400, f"At most 30 entries supported (have {len(entries)})")

    tpl_dir = Path("template_variants/DOCX")
    out_dir = Path("output/DOCX")
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        path = generate_for_user(uid, entries, month, year, tpl_dir, out_dir)
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")

    filename = os.path.basename(path)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )
