from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core import file_data_store as store
from web_api.deps import current_user

router = APIRouter(prefix="/distributors", tags=["distributors"])


class NameIn(BaseModel):
    name: str


@router.get("")
async def list_distributors(_user=Depends(current_user)):
    return {"distributors": await store.get_distributors()}


@router.post("")
async def add_distributor(body: NameIn, _user=Depends(current_user)):
    ok = await store.add_distributor(body.name)
    if not ok:
        raise HTTPException(409, "Distributor already exists")
    return {"ok": True}


@router.delete("/{name}")
async def remove_distributor(name: str, _user=Depends(current_user)):
    ok = await store.remove_distributor(name)
    if not ok:
        raise HTTPException(404, "Distributor not found")
    return {"ok": True}
