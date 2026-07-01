from typing import Optional
from fastapi import APIRouter, Depends
from core import file_data_store as store
from core.expense_calculations import (
    calculate_summary, get_petrol_status, get_mobil_status, get_thresholds,
)
from web_api.deps import current_user
from core.timezone import current_month_year

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("")
async def summary(month: Optional[int] = None, year: Optional[int] = None,
                  user=Depends(current_user)):
    uid = user["user_id"]
    if month is None or year is None:
        month, year = current_month_year()
    entries = await store.get_entries(uid, month, year)
    prefs = await store.get_user_prefs(uid)
    petrol_th, mobil_th = get_thresholds(prefs)
    return {
        "summary": calculate_summary(entries),
        "petrol_status": get_petrol_status(entries, petrol_th),
        "mobil_status": get_mobil_status(entries, mobil_th),
        "count": len(entries),
    }
