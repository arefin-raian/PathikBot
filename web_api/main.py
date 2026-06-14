"""FastAPI app exposing PathikBot core to a web UI.

Runs alongside the Telegram bot via web_api/launcher.py on Render.
"""
import os
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from web_api.auth import verify_telegram_login, issue_jwt
from web_api.routes import entries, summary, settings, distributors, generate, admin

logging.basicConfig(level=logging.INFO)

ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("WEB_ALLOWED_ORIGINS", "*").split(",") if o.strip()
] or ["*"]

app = FastAPI(title="PathikBot Web API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Note: init_db() is invoked by the bot's post_init in bot/main.py.
# Calling it again here closes the shared Mongo client and breaks the bot.

@app.get("/api/health")
async def health():
    return {"ok": True}


@app.post("/api/auth/telegram")
async def auth_telegram(req: Request):
    data = await req.json()
    if not isinstance(data, dict):
        raise HTTPException(400, "Invalid payload")
    # Telegram Login Widget sends string values; normalize for HMAC
    norm = {k: str(v) for k, v in data.items()}
    if not verify_telegram_login(norm):
        raise HTTPException(401, "Invalid Telegram signature")
    try:
        uid = int(norm["id"])
    except (KeyError, ValueError):
        raise HTTPException(400, "Missing user id")
    username = norm.get("username") or norm.get("first_name") or ""

    # Ensure user is registered (mirrors bot /start behavior)
    try:
        from core.file_data_store import is_registered, add_user, init_user_storage
        if not await is_registered(uid):
            # Owner is allow-listed; others require admin to add them
            await init_user_storage(uid)
    except Exception as e:
        logging.warning("user init failed: %s", e)

    token = issue_jwt(uid, username)
    return {"token": token, "user_id": uid, "username": username}


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
