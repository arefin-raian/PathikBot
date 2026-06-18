from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core import file_data_store as store
from web_api.deps import owner_only
from web_api.auth import issue_jwt

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


class ImpersonateIn(BaseModel):
    user_id: int


@router.post("/impersonate")
async def impersonate(body: ImpersonateIn, owner=Depends(owner_only)):
    """Owner-only: mint a short-lived JWT for `user_id` so the owner can view
    and act in the website AS that user. The bot is not affected — it uses
    Telegram identity, not these tokens."""
    users = await store.get_all_users()
    # users keys are stringified ids; normalize
    target_key = str(body.user_id)
    if target_key not in {str(k) for k in users.keys()}:
        raise HTTPException(404, "Target user not registered")
    if body.user_id == owner["user_id"]:
        raise HTTPException(400, "Already signed in as this user")
    token = issue_jwt(body.user_id, username=str(body.user_id))
    return {
        "token": token,
        "user_id": body.user_id,
        "username": str(body.user_id),
        "impersonated_by": owner["user_id"],
    }
