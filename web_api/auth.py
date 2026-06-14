"""Telegram Login Widget verification + JWT issuance."""
import os
import hmac
import hashlib
import time
import json
import base64
from typing import Optional

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
JWT_SECRET = os.getenv("WEB_JWT_SECRET", "change-me")
JWT_TTL = 60 * 60 * 24 * 30  # 30 days
MAX_AUTH_AGE = 60 * 60 * 24  # 1 day for Telegram auth_date


def verify_telegram_login(data: dict) -> bool:
    """Verify the HMAC of a Telegram Login Widget payload.

    See https://core.telegram.org/widgets/login#checking-authorization
    """
    if not BOT_TOKEN:
        return False
    recv_hash = data.get("hash")
    if not recv_hash:
        return False
    pairs = sorted(
        f"{k}={v}" for k, v in data.items() if k != "hash" and v is not None
    )
    check_string = "\n".join(pairs)
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    computed = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, recv_hash):
        return False
    try:
        auth_date = int(data.get("auth_date", 0))
    except (TypeError, ValueError):
        return False
    if time.time() - auth_date > MAX_AUTH_AGE:
        return False
    return True


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def issue_jwt(user_id: int, username: Optional[str] = None) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "uid": user_id,
        "username": username or "",
        "iat": now,
        "exp": now + JWT_TTL,
    }
    h = _b64url(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(JWT_SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{_b64url(sig)}"


def verify_jwt(token: str) -> Optional[dict]:
    try:
        h, p, s = token.split(".")
    except ValueError:
        return None
    expected = hmac.new(JWT_SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url(expected), s):
        return None
    try:
        payload = json.loads(_b64url_decode(p))
    except Exception:
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload
