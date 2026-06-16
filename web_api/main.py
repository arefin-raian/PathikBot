"""FastAPI app exposing PathikBot core to a web UI.

Runs alongside the Telegram bot via web_api/launcher.py on Render.
"""
import os
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from web_api.auth import issue_jwt
from core.credentials import verify_login
from web_api.routes import entries, summary, settings, distributors, generate, admin

logging.basicConfig(level=logging.INFO)

ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("WEB_ALLOWED_ORIGINS", "*").split(",") if o.strip()
] or ["*"]

app = FastAPI(title="PathikBot Web API", version="1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"ok": True}


@app.post("/api/auth/login")
async def auth_login(req: Request):
    """Email + password login.

    Credentials are issued by the bot's /credentials command. The bot stores
    a PBKDF2 hash; this endpoint verifies it and returns a JWT plus the
    minimal user metadata the web UI needs to render its dashboard.
    """
    try:
        data = await req.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    if not isinstance(data, dict):
        raise HTTPException(400, "Invalid payload")

    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not email or not password:
        raise HTTPException(400, "Email and password required")

    info = await verify_login(email, password)
    if not info:
        raise HTTPException(401, "Invalid email or password")

    # Make sure the user still has registered storage. Owner is always allowed.
    try:
        from core.file_data_store import is_registered, init_user_storage
        if not await is_registered(info["user_id"]):
            raise HTTPException(403, "User is no longer registered")
        await init_user_storage(info["user_id"])
    except HTTPException:
        raise
    except Exception as e:
        logging.warning("user check failed: %s", e)

    token = issue_jwt(info["user_id"], info.get("username") or "")
    return {
        "token": token,
        "user_id": info["user_id"],
        "username": info.get("username") or "",
        "name": info.get("display_name") or info.get("username") or info["email"].split("@")[0],
        "email": info["email"],
    }


app.include_router(entries.router, prefix="/api")
app.include_router(summary.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(distributors.router, prefix="/api")
app.include_router(generate.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.exception_handler(Exception)
async def _unhandled(_req: Request, exc: Exception):
    logging.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": str(exc)})
