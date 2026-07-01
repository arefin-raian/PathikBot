"""CRUD over journey entries — delegates to core.file_data_store."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import file_data_store as store
from core.expense_calculations import (
    calculate_km, calculate_petrol_cost, calculate_mobil_cost,
    calculate_total_entry_cost, calc_carry_forward,
)
from web_api.deps import current_user
from core.timezone import current_month_year

router = APIRouter(prefix="/entries", tags=["entries"])


class EntryIn(BaseModel):
    entry_type: str = Field(..., description="REGULAR | MEETING | OTHERS")
    date: str
    odo_start: float = 0
    odo_end: float = 0
    total_km: Optional[float] = None
    petrol_liters: float = 0
    mobil_liters: float = 0
    da_amount: float = 0
    transport_fee: float = 0
    others_designation: str = ""
    venue: str = ""
    distributors_raw: List[str] = []
    petrol_price: Optional[float] = None
    mobil_price: Optional[float] = None


def _eval_distance(value) -> float:
    """Accept '14+15', '29', 29 — sum simple +-separated numbers."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return 0.0
    total = 0.0
    for chunk in s.replace("-", "+-").split("+"):
        chunk = chunk.strip()
        if chunk:
            total += float(chunk)
    return total


def _compact_number(value):
    """Store whole-number floats as ints so bot output does not show 10.0."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


@router.get("")
async def list_entries(
    month: Optional[int] = None,
    year: Optional[int] = None,
    all: bool = False,
    user=Depends(current_user),
):
    if not all and (month is None or year is None):
        month, year = current_month_year()
    rows = await store.get_entries(user["user_id"], month, year)
    return {"entries": rows}


@router.get("/{entry_id}")
async def get_entry(entry_id: int, user=Depends(current_user)):
    row = await store.get_entry_by_id(user["user_id"], entry_id)
    if not row:
        raise HTTPException(404, "Entry not found")
    return row


@router.post("")
async def create_entry(body: EntryIn, user=Depends(current_user)):
    uid = user["user_id"]
    prefs = await store.get_user_prefs(uid)
    # Fallback to user prefs when price not explicitly provided
    petrol_price = body.petrol_price if body.petrol_price is not None else float(prefs.get("petrol_price", 140.7))
    mobil_price = body.mobil_price if body.mobil_price is not None else float(prefs.get("mobil_price", 560.0))
    total_km = _eval_distance(body.total_km) if body.total_km not in (None, 0) else \
        calculate_km(body.odo_start, body.odo_end)
    petrol_cost = calculate_petrol_cost(body.petrol_liters, petrol_price)
    mobil_cost = calculate_mobil_cost(body.mobil_liters, mobil_price)
    total_cost = calculate_total_entry_cost(
        body.entry_type, body.petrol_liters, body.mobil_liters,
        body.da_amount, body.transport_fee, petrol_price, mobil_price,
    )

    all_entries = await store.get_entries(uid)
    petrol_overflow = mobil_overflow = 0
    if body.petrol_liters > 0:
        petrol_overflow = calc_carry_forward(
            all_entries, total_km, "petrol_liters", "petrol_overflow", 480
        )
    if body.mobil_liters > 0:
        mobil_overflow = calc_carry_forward(
            all_entries, total_km, "mobil_liters", "mobil_overflow", 1000
        )

    payload = {
        "entry_type": body.entry_type,
        "date": body.date,
        "odo_start": _compact_number(body.odo_start),
        "odo_end": _compact_number(body.odo_end),
        "total_km": _compact_number(total_km),
        "petrol_liters": _compact_number(body.petrol_liters),
        "petrol_price": _compact_number(body.petrol_price),
        "petrol_cost": _compact_number(petrol_cost),
        "petrol_overflow": _compact_number(petrol_overflow),
        "mobil_liters": _compact_number(body.mobil_liters),
        "mobil_price": _compact_number(body.mobil_price),
        "mobil_cost": _compact_number(mobil_cost),
        "mobil_overflow": _compact_number(mobil_overflow),
        "da_amount": _compact_number(body.da_amount),
        "transport_fee": _compact_number(body.transport_fee),
        "others_designation": body.others_designation,
        "venue": body.venue,
        "distributors_raw": body.distributors_raw,
        "total_cost": _compact_number(total_cost),
    }
    entry_id = await store.add_entry(uid, payload)
    return {"id": entry_id, **payload}


@router.patch("/{entry_id}")
async def patch_entry(entry_id: int, body: dict, user=Depends(current_user)):
    uid = user["user_id"]
    current = await store.get_entry_by_id(uid, entry_id)
    if not current:
        raise HTTPException(404, "Entry not found")

    merged = {**current, **body}
    prefs = await store.get_user_prefs(uid)
    # Use the entry's stored price if available, otherwise fallback to user prefs or defaults
    petrol_price = merged.get("petrol_price")
    if petrol_price is None:
        petrol_price = float(prefs.get("petrol_price", 140.7))
    mobil_price = merged.get("mobil_price")
    if mobil_price is None:
        mobil_price = float(prefs.get("mobil_price", 560.0))
    petrol_liters = float(merged.get("petrol_liters") if merged.get("petrol_liters") is not None else 0)
    mobil_liters = float(merged.get("mobil_liters") if merged.get("mobil_liters") is not None else 0)
    body["petrol_cost"] = _compact_number(calculate_petrol_cost(petrol_liters, petrol_price))
    body["mobil_cost"] = _compact_number(calculate_mobil_cost(mobil_liters, mobil_price))
    body["total_cost"] = _compact_number(calculate_total_entry_cost(
        merged.get("entry_type", "REGULAR"),
        petrol_liters,
        mobil_liters,
        merged.get("da_amount"),
        merged.get("transport_fee", 0),
        petrol_price,
        mobil_price,
    ))

    # Use cascade update to keep odometers consistent
    ok = await store.update_entry_and_cascade(uid, entry_id, body)
    if not ok:
        raise HTTPException(404, "Entry not found")
    return await store.get_entry_by_id(uid, entry_id)


@router.delete("/{entry_id}")
async def delete_entry(entry_id: int, user=Depends(current_user)):
    ok = await store.delete_entry(user["user_id"], entry_id)
    if not ok:
        raise HTTPException(404, "Entry not found")
    return {"ok": True}


@router.get("/meta/last-odo")
async def last_odo(user=Depends(current_user)):
    return {"last_odo": await store.get_last_odo(user["user_id"])}
