from typing import Optional
from fastapi import APIRouter, Depends
from core import file_data_store as store
from core.expense_calculations import calculate_summary, get_petrol_status, get_mobil_status
from web_api.deps import current_user

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("")
async def summary(month: Optional[int] = None, year: Optional[int] = None,
                  user=Depends(current_user)):
    entries = await store.get_entries(user["user_id"], month, year)
    return {
        "summary": calculate_summary(entries),
        "petrol_status": get_petrol_status(entries),
        "mobil_status": get_mobil_status(entries),
        "count": len(entries),
    }
