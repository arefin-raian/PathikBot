"""Async MongoDB storage backend for PathikBot."""
import os
import json
import asyncio
from urllib.parse import quote_plus
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

MONGO_URL = os.getenv("MONGODB_URL")
MONGO_DB = os.getenv("MONGODB_DB_NAME", "pathikbot")

# Auto-encode special chars in the password portion of the URI
if MONGO_URL and '@' in MONGO_URL:
    try:
        prefix, rest = MONGO_URL.split('@', 1)
        if '//' in prefix:
            scheme_part = prefix.split('//', 1)
            if ':' in scheme_part[1]:
                user, pw = scheme_part[1].split(':', 1)
                scheme_part[1] = f"{user}:{quote_plus(pw)}"
            prefix = '//'.join(scheme_part)
        MONGO_URL = f"{prefix}@{rest}"
    except Exception:
        pass  # fall through to original on parse errors
_clients_by_loop = {}
_dbs_by_loop = {}
_connected_loops = set()


def _loop_key():
    """Motor clients are bound to the asyncio loop that creates them."""
    return id(asyncio.get_running_loop())


async def get_db() -> AsyncIOMotorDatabase:
    if not MONGO_URL:
        return None

    key = _loop_key()
    client = _clients_by_loop.get(key)
    db = _dbs_by_loop.get(key)

    if db is None:
        client = AsyncIOMotorClient(
            MONGO_URL,
            serverSelectionTimeoutMS=5000,
            tlsAllowInvalidCertificates=True,
        )
        db = client[MONGO_DB]
        _clients_by_loop[key] = client
        _dbs_by_loop[key] = db

    if key not in _connected_loops:
        try:
            await client.admin.command("ping")
            _connected_loops.add(key)
        except Exception:
            client.close()
            _clients_by_loop.pop(key, None)
            _dbs_by_loop.pop(key, None)
            _connected_loops.discard(key)
            return None

    return db


async def close():
    key = _loop_key()
    client = _clients_by_loop.pop(key, None)
    _dbs_by_loop.pop(key, None)
    _connected_loops.discard(key)
    if client:
        client.close()


# ── Indexes ──────────────────────────────────────────────────

async def ensure_indexes():
    db = await get_db()
    if db is None:
        return
    await db.users.create_index("_id")
    await db.entries.create_index([("user_id", 1), ("id", 1)], unique=True)
    await db.entries.create_index([("user_id", 1), ("date", 1)])
    await db.logsheets.create_index([("user_id", 1), ("month", 1), ("year", 1)], unique=True)
    await db.user_prefs.create_index("_id")


# ── User management ──────────────────────────────────────────

async def is_registered(user_id: int) -> bool:
    db = await get_db()
    if db is None:
        return False
    doc = await db.users.find_one({"_id": str(user_id)})
    return doc is not None


async def add_user(user_id: int, role: str = "user") -> bool:
    db = await get_db()
    if db is None:
        return False
    key = str(user_id)
    existing = await db.users.find_one({"_id": key})
    if existing:
        return False
    await db.users.insert_one({
        "_id": key,
        "role": role,
        "added_at": datetime.now().isoformat()
    })
    await init_user_storage(user_id)
    return True


async def remove_user(user_id: int) -> bool:
    db = await get_db()
    if db is None:
        return False
    result = await db.users.delete_one({"_id": str(user_id)})
    return result.deleted_count > 0


async def get_all_users() -> dict:
    db = await get_db()
    if db is None:
        return {}
    cursor = db.users.find()
    users = {}
    async for doc in cursor:
        users[doc["_id"]] = {"role": doc.get("role", "user"), "added_at": doc.get("added_at", "")}
    return users


async def init_user_storage(user_id: int):
    db = await get_db()
    if db is None:
        return
    key = str(user_id)
    await db.user_prefs.update_one(
        {"_id": key},
        {"$setOnInsert": {"_id": key}},
        upsert=True
    )


async def is_owner(user_id: int) -> bool:
    return user_id == 6161189904


async def init_db():
    db = await get_db()
    if db is None:
        return
    await ensure_indexes()

    owner_id = str(6161189904)
    existing = await db.users.find_one({"_id": owner_id})
    if not existing:
        await db.users.insert_one({
            "_id": owner_id,
            "role": "owner",
            "added_at": datetime.now().isoformat()
        })

    await init_user_storage(6161189904)

    await _migrate_legacy_if_needed(db)


async def _migrate_legacy_if_needed(db):
    """One-time migration from JSON files to MongoDB."""
    entry_count = await db["entries"].count_documents({})
    if entry_count > 0:
        return

    if not os.path.exists("data"):
        return

    import glob
    for fpath in glob.glob("data/entries_*.json"):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except Exception:
            continue
        if not entries:
            continue
        uid = int(fpath.split("_")[-1].replace(".json", ""))
        for e in entries:
            e["user_id"] = uid
            e.pop("_id", None)
        if entries:
            await db["entries"].insert_many(entries, ordered=False)

    users_path = "data/users.json"
    if os.path.exists(users_path):
        try:
            with open(users_path, "r", encoding="utf-8") as f:
                users = json.load(f)
        except Exception:
            users = {}
        for uid_str, info in users.items():
            existing = await db["users"].find_one({"_id": uid_str})
            if not existing:
                await db["users"].insert_one({
                    "_id": uid_str,
                    "role": info.get("role", "user"),
                    "added_at": info.get("added_at", datetime.now().isoformat())
                })

    dist_path = "data/distributors.json"
    if os.path.exists(dist_path):
        try:
            with open(dist_path, "r", encoding="utf-8") as f:
                dists = json.load(f)
        except Exception:
            dists = []
        if dists:
            await db["distributors"].delete_many({})
            for name in dists:
                await db["distributors"].insert_one({"name": name})

    prefs_dir = "data/user_prefs"
    if os.path.exists(prefs_dir):
        for fpath in glob.glob(os.path.join(prefs_dir, "*.json")):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    prefs = json.load(f)
            except Exception:
                continue
            if prefs:
                uid = fpath.split("\\")[-1].replace(".json", "")
                await db["user_prefs"].update_one(
                    {"_id": uid},
                    {"$set": prefs},
                    upsert=True
                )


# ── Distributors ─────────────────────────────────────────────

async def get_distributors():
    db = await get_db()
    if db is None:
        return []
    cursor = db.distributors.find().sort("name", 1)
    return [doc["name"] async for doc in cursor]


async def save_distributors(dist_list: list):
    db = await get_db()
    if db is None:
        return
    await db.distributors.delete_many({})
    if dist_list:
        await db.distributors.insert_many([{"name": n} for n in dist_list])


async def add_distributor(name: str) -> bool:
    db = await get_db()
    if db is None:
        return False
    existing = await db.distributors.find_one({"name": name})
    if existing:
        return False
    await db.distributors.insert_one({"name": name})
    return True


async def remove_distributor(name: str) -> bool:
    db = await get_db()
    if db is None:
        return False
    result = await db.distributors.delete_one({"name": name})
    return result.deleted_count > 0


# ── Per-user entries ─────────────────────────────────────────

async def add_entry(user_id: int, entry_data: dict) -> int:
    db = await get_db()
    if db is None:
        return 0
    last = await db.entries.find_one({"user_id": user_id}, sort=[("id", -1)])
    entry_id = (last["id"] + 1) if last else 1
    doc = {**entry_data, "user_id": user_id, "id": entry_id, "created_at": datetime.now().isoformat()}
    await db.entries.insert_one(doc)
    return entry_id


async def get_entries(user_id: int, month=None, year=None):
    db = await get_db()
    if db is None:
        return []
    query = {"user_id": user_id}
    if month is not None and year is not None:
        query["$expr"] = {
            "$and": [
                {"$eq": [{"$month": {"$dateFromString": {"dateString": "$date", "format": "%Y-%m-%d"}}}, month]},
                {"$eq": [{"$year": {"$dateFromString": {"dateString": "$date", "format": "%Y-%m-%d"}}}, year]}
            ]
        }
    cursor = db.entries.find(query).sort("date", 1)
    docs = await cursor.to_list(length=None)
    for d in docs:
        d.pop("_id", None)
    return docs


async def get_entry_by_id(user_id: int, entry_id: int):
    db = await get_db()
    if db is None:
        return None
    doc = await db.entries.find_one({"user_id": user_id, "id": entry_id})
    if doc is not None:
        doc.pop("_id", None)
    return doc


async def update_entry(user_id: int, entry_id: int, updated_data: dict) -> bool:
    db = await get_db()
    if db is None:
        return False
    updated_data["updated_at"] = datetime.now().isoformat()
    result = await db.entries.update_one(
        {"user_id": user_id, "id": entry_id},
        {"$set": updated_data}
    )
    return result.modified_count > 0


async def delete_entry(user_id: int, entry_id: int) -> bool:
    db = await get_db()
    if db is None:
        return False
    result = await db.entries.delete_one({"user_id": user_id, "id": entry_id})
    if result.deleted_count == 0:
        return False
    await _recalculate_odometers(user_id, entry_id)
    return True


async def _recalculate_odometers(user_id: int, from_id: int):
    db = await get_db()
    if db is None:
        return
    entries = await db.entries.find({"user_id": user_id}).sort("date", 1).to_list(length=None)
    found = False
    for i, e in enumerate(entries):
        if e["id"] == from_id:
            found = True
        if found and i > 0:
            prev = entries[i - 1]
            await db.entries.update_one(
                {"_id": e["_id"]},
                {"$set": {
                    "odo_start": prev["odo_end"],
                    "odo_end": prev["odo_end"] + e.get("total_km", 0),
                    "updated_at": datetime.now().isoformat()
                }}
            )


async def update_entry_and_cascade(user_id: int, entry_id: int, updated_data: dict) -> bool:
    db = await get_db()
    if db is None:
        return False
    entry = await db.entries.find_one({"user_id": user_id, "id": entry_id})
    if not entry:
        return False

    if "odo_start" in updated_data and "total_km" not in updated_data:
        updated_data["odo_end"] = updated_data["odo_start"] + entry.get("total_km", 0)
    elif "odo_end" in updated_data and "total_km" not in updated_data:
        updated_data["total_km"] = updated_data["odo_end"] - entry["odo_start"]
    elif "total_km" in updated_data:
        updated_data["odo_end"] = entry["odo_start"] + updated_data["total_km"]

    updated_data["updated_at"] = datetime.now().isoformat()
    await db.entries.update_one(
        {"_id": entry["_id"]},
        {"$set": updated_data}
    )

    remaining = await db.entries.find(
        {"user_id": user_id, "date": {"$gte": entry["date"]}}
    ).sort("date", 1).to_list(length=None)

    target_idx = -1
    for i, e in enumerate(remaining):
        if e["id"] == entry_id:
            target_idx = i
            break

    if target_idx >= 0 and target_idx + 1 < len(remaining):
        for i in range(target_idx + 1, len(remaining)):
            prev = remaining[i - 1]
            await db.entries.update_one(
                {"_id": remaining[i]["_id"]},
                {"$set": {
                    "odo_start": prev["odo_end"],
                    "odo_end": prev["odo_end"] + remaining[i].get("total_km", 0),
                    "updated_at": datetime.now().isoformat()
                }}
            )
    return True


async def get_last_day_in_month(user_id: int, month: int, year: int):
    entries = await get_entries(user_id, month, year)
    if not entries:
        return None
    return datetime.strptime(entries[-1]["date"], "%Y-%m-%d").day


async def get_last_odo(user_id: int) -> int:
    db = await get_db()
    if db is None:
        return 0
    last = await db.entries.find_one({"user_id": user_id}, sort=[("date", -1)])
    return last.get("odo_end", 0) if last else 0


# ── Preferences ──────────────────────────────────────────────

async def get_user_prefs(user_id: int) -> dict:
    db = await get_db()
    if db is None:
        return {}
    doc = await db.user_prefs.find_one({"_id": str(user_id)})
    if not doc:
        return {}
    doc.pop("_id", None)
    return doc


async def set_user_prefs(user_id: int, prefs: dict):
    db = await get_db()
    if db is None:
        return
    await db.user_prefs.update_one(
        {"_id": str(user_id)},
        {"$set": prefs},
        upsert=True
    )


# ── Logsheet file tracking ──────────────────────────────────

async def save_logsheet_file_id(user_id: int, month: int, year: int, file_id: str, file_name: str):
    db = await get_db()
    if db is None:
        return
    await db.logsheets.update_one(
        {"user_id": user_id, "month": month, "year": year},
        {"$set": {
            "file_id": file_id,
            "file_name": file_name,
            "created_at": datetime.now().isoformat()
        }},
        upsert=True
    )


async def get_logsheet_file_id(user_id: int, month: int, year: int):
    db = await get_db()
    if db is None:
        return None
    doc = await db.logsheets.find_one({"user_id": user_id, "month": month, "year": year})
    return doc


async def delete_logsheet_file_id(user_id: int, month: int, year: int):
    db = await get_db()
    if db is None:
        return
    await db.logsheets.delete_one({"user_id": user_id, "month": month, "year": year})
