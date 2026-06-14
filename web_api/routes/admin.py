from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core import file_data_store as store
from web_api.deps import owner_only

router = APIRouter(prefix="/admin", tags=["admin"])


class UserIn(BaseModel):
    user_id: int
    role: str = "user"


@router.get("/users")
async def list_users(_owner=Depends(owner_only)):
    return await store.get_all_users()


@router.post("/users")
async def add_user(body: UserIn, _owner=Depends(owner_only)):
    ok = await store.add_user(body.user_id, body.role)
    if not ok:
        raise HTTPException(409, "User already exists")
    await store.init_user_storage(body.user_id)
    return {"ok": True}


@router.delete("/users/{user_id}")
async def remove_user(user_id: int, _owner=Depends(owner_only)):
    ok = await store.remove_user(user_id)
    if not ok:
        raise HTTPException(404, "User not found")
    return {"ok": True}
