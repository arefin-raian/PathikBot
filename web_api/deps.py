"""FastAPI dependencies."""
import os
from fastapi import Header, HTTPException, status
from web_api.auth import verify_jwt

OWNER_ID = int(os.getenv("OWNER_TELEGRAM_ID", "0") or 0)


async def current_user(authorization: str = Header(default="")) -> dict:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = verify_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    try:
        uid = int(payload.get("uid") or payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return {"user_id": uid, "username": payload.get("username", "")}


async def owner_only(user=__import__("fastapi").Depends(current_user)) -> dict:
    if not OWNER_ID or user["user_id"] != OWNER_ID:
        raise HTTPException(status_code=403, detail="Owner only")
    return user
