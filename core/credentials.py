"""Email/password credentials for web login.

Each registered Telegram user can generate a stable email (derived from
their Telegram first/last name) plus a freshly rotated random password
via the bot's /credentials command. The password is hashed with PBKDF2
and stored either in MongoDB (collection: credentials) when available,
or in data/credentials.json as a fallback.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import string
import unicodedata
from datetime import datetime
from typing import Optional

CREDS_PATH = "data/credentials.json"
EMAIL_DOMAIN = "pathikbot.tg"
PBKDF2_ITERS = 200_000


# ── helpers ────────────────────────────────────────────────

def _slug(name: str) -> str:
    if not name:
        return ""
    # Transliterate unicode to closest ASCII, drop non-letters
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]", "", ascii_only).lower()


def build_email_local(first_name: str = "", last_name: str = "", username: str = "") -> str:
    """Construct the local-part of the email: firstlast (no separator)."""
    local = _slug(first_name) + _slug(last_name)
    if not local:
        local = _slug(username)
    if not local:
        local = "user"
    return local[:48]  # keep it reasonable


def _gen_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _hash_password(password: str, salt: bytes) -> str:
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERS)
    return f"pbkdf2_sha256${PBKDF2_ITERS}${salt.hex()}${h.hex()}"


def _verify_hash(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    try:
        iters_i = int(iters)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters_i)
    return hmac.compare_digest(h, expected)


# ── storage backends ───────────────────────────────────────

def _ensure_dir():
    if not os.path.exists("data"):
        os.makedirs("data")


def _file_load() -> dict:
    if not os.path.exists(CREDS_PATH):
        return {}
    try:
        with open(CREDS_PATH, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (json.JSONDecodeError, OSError):
        return {}


def _file_save(data: dict):
    _ensure_dir()
    with open(CREDS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def _mongo_db():
    if not os.getenv("MONGODB_URL"):
        return None
    try:
        from core.mongo_db import get_db
        return await get_db()
    except Exception:
        return None


async def _all_records() -> dict:
    """Return {user_id_str: record} from active backend."""
    db = await _mongo_db()
    if db is not None:
        out = {}
        async for doc in db.credentials.find():
            uid = str(doc.get("_id"))
            out[uid] = {
                "email": doc.get("email"),
                "password_hash": doc.get("password_hash"),
                "display_name": doc.get("display_name", ""),
                "username": doc.get("username", ""),
                "updated_at": doc.get("updated_at", ""),
            }
        return out
    return _file_load()


async def _save_record(user_id: int, record: dict):
    db = await _mongo_db()
    if db is not None:
        await db.credentials.update_one(
            {"_id": str(user_id)},
            {"$set": {**record, "_id": str(user_id)}},
            upsert=True,
        )
        return
    data = _file_load()
    data[str(user_id)] = record
    _file_save(data)


# ── public API ─────────────────────────────────────────────

async def get_credentials(user_id: int) -> Optional[dict]:
    records = await _all_records()
    return records.get(str(user_id))


async def list_taken_emails() -> set:
    records = await _all_records()
    return {r["email"] for r in records.values() if r.get("email")}


async def pick_unique_email(base_local: str, *, exclude_user_id: Optional[int] = None) -> str:
    records = await _all_records()
    taken = {
        r["email"] for uid, r in records.items()
        if r.get("email") and uid != str(exclude_user_id or "")
    }
    candidate = f"{base_local}@{EMAIL_DOMAIN}"
    if candidate not in taken:
        return candidate
    n = 2
    while True:
        candidate = f"{base_local}{n}@{EMAIL_DOMAIN}"
        if candidate not in taken:
            return candidate
        n += 1


async def issue_credentials(
    user_id: int,
    first_name: str = "",
    last_name: str = "",
    username: str = "",
) -> tuple[str, str]:
    """Generate (or rotate) credentials for a user.

    Returns (email, plaintext_password). The email stays stable for repeated
    calls; the password is always freshly generated and the hash overwritten.
    """
    existing = await get_credentials(user_id)
    if existing and existing.get("email"):
        email = existing["email"]
    else:
        base = build_email_local(first_name, last_name, username)
        email = await pick_unique_email(base, exclude_user_id=user_id)

    password = _gen_password(16)
    salt = secrets.token_bytes(16)
    record = {
        "email": email,
        "password_hash": _hash_password(password, salt),
        "display_name": (f"{first_name or ''} {last_name or ''}").strip() or username or "",
        "username": username or "",
        "updated_at": datetime.utcnow().isoformat(),
    }
    await _save_record(user_id, record)
    return email, password


async def verify_login(email: str, password: str) -> Optional[dict]:
    """Return {user_id, username, display_name, email} on success, else None."""
    if not email or not password:
        return None
    email = email.strip().lower()
    records = await _all_records()
    for uid_str, rec in records.items():
        if (rec.get("email") or "").lower() != email:
            continue
        if _verify_hash(password, rec.get("password_hash") or ""):
            try:
                uid = int(uid_str)
            except ValueError:
                return None
            return {
                "user_id": uid,
                "email": rec.get("email"),
                "username": rec.get("username", ""),
                "display_name": rec.get("display_name", ""),
            }
        return None
    return None
