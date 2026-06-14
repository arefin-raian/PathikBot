from fastapi import APIRouter, Depends
from core import file_data_store as store
from web_api.deps import current_user

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_settings(user=Depends(current_user)):
    return await store.get_user_prefs(user["user_id"])


@router.put("")
async def update_settings(body: dict, user=Depends(current_user)):
    await store.set_user_prefs(user["user_id"], body)
    return await store.get_user_prefs(user["user_id"])
