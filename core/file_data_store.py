import json
import os
import shutil
import aiofiles
import json
import os
import re
import glob
from pathlib import Path
from datetime import datetime
from core.timezone import dhaka_iso_now
from bot.inline_keyboards import to_bn_number

OWNER_ID = 6161189904
DIST_PATH = 'data/distributors.json'
USERS_PATH = 'data/users.json'
USER_PREFS_BASE = 'data/user_prefs'
ENTRIES_BASE = 'data'


def _ensure_data_dir():
    if not os.path.exists('data'):
        os.makedirs('data')


def _entries_path(user_id: int) -> str:
    return os.path.join(ENTRIES_BASE, f'entries_{user_id}.json')


def _user_prefs_path(user_id: int) -> str:
    return os.path.join(USER_PREFS_BASE, f'{user_id}.json')


# ── User management (sync — fast, small file) ─────────────


def _load_users_raw() -> dict:
    try:
        if not os.path.exists(USERS_PATH):
            return {}
        with open(USERS_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
            return json.loads(content) if content.strip() else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_users_raw(users: dict):
    _ensure_data_dir()
    with open(USERS_PATH, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def load_users() -> dict:
    return _load_users_raw()


def save_users(users: dict):
    _save_users_raw(users)


async def is_registered(user_id: int) -> bool:
    users = _load_users_raw()
    return str(user_id) in users


async def add_user(user_id: int, role: str = 'user') -> bool:
    users = _load_users_raw()
    key = str(user_id)
    if key in users:
        return False
    users[key] = {
        'role': role,
        'added_at': dhaka_iso_now()
    }
    _save_users_raw(users)
    await init_user_storage(user_id)
    return True


async def remove_user(user_id: int) -> bool:
    users = _load_users_raw()
    key = str(user_id)
    if key not in users:
        return False
    del users[key]
    _save_users_raw(users)
    return True


async def get_all_users() -> dict:
    return _load_users_raw()


async def init_user_storage(user_id: int):
    """Ensure a user's data files exist."""
    _ensure_data_dir()
    prefs_dir = os.path.dirname(_user_prefs_path(user_id))
    if not os.path.exists(prefs_dir):
        os.makedirs(prefs_dir)

    ep = _entries_path(user_id)
    if not os.path.exists(ep):
        with open(ep, 'w', encoding='utf-8') as f:
            json.dump([], f)

    pp = _user_prefs_path(user_id)
    if not os.path.exists(pp):
        with open(pp, 'w', encoding='utf-8') as f:
            json.dump({}, f)


async def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


async def init_db():
    """Initialize data directory and migrate legacy entries to owner."""
    _ensure_data_dir()

    # Auto-register owner
    if not await is_registered(OWNER_ID):
        await add_user(OWNER_ID, role='owner')

    # Migrate legacy data/entries.json → data/entries_{owner_id}.json
    legacy = 'data/entries.json'
    owner_path = _entries_path(OWNER_ID)
    if os.path.exists(legacy) and not os.path.exists(owner_path):
        shutil.copy2(legacy, owner_path)

    # Migrate legacy data/logsheet.db → data/entries_{owner_id}.json
    logsheet = 'data/logsheet.db'
    if os.path.exists(logsheet) and (not os.path.exists(owner_path) or os.path.getsize(owner_path) <= 4):
        try:
            with open(logsheet, 'r', encoding='utf-8') as f:
                logsheet_data = json.load(f)
            if logsheet_data:
                with open(owner_path, 'w', encoding='utf-8') as of:
                    json.dump(logsheet_data, of, indent=4, ensure_ascii=False)
        except (json.JSONDecodeError, Exception):
            pass

    # Ensure owner has storage files
    await init_user_storage(OWNER_ID)

    # Migrate legacy user_prefs.json → data/user_prefs/{owner_id}.json
    legacy_prefs = 'data/user_prefs.json'
    owner_prefs_path = _user_prefs_path(OWNER_ID)
    if os.path.exists(legacy_prefs) and not os.path.exists(owner_prefs_path):
        try:
            with open(legacy_prefs, 'r', encoding='utf-8') as f:
                content = f.read()
                all_prefs = json.loads(content) if content.strip() else {}
            owner_prefs = all_prefs.get(str(OWNER_ID), {})
            if owner_prefs:
                from bot.text_resources import S
                with open(owner_prefs_path, 'w', encoding='utf-8') as f:
                    json.dump(owner_prefs, f, ensure_ascii=False, indent=2)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    # Remove legacy files after successful migration
    legacy_files = ['data/entries.json', 'data/user_prefs.json']
    for lf in legacy_files:
        if os.path.exists(lf):
            try:
                os.remove(lf)
            except OSError:
                pass


# ── Distributor management (shared) ───────────────────────


async def get_distributors():
    try:
        if not os.path.exists(DIST_PATH):
            return []
        async with aiofiles.open(DIST_PATH, mode='r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content)
    except Exception:
        return []


async def save_distributors(dist_list):
    async with aiofiles.open(DIST_PATH, mode='w', encoding='utf-8') as f:
        await f.write(json.dumps(dist_list, indent=4, ensure_ascii=False))


async def add_distributor(name):
    dists = await get_distributors()
    if name not in dists:
        dists.append(name)
        dists.sort()
        await save_distributors(dists)
        return True
    return False


async def remove_distributor(name):
    dists = await get_distributors()
    if name in dists:
        dists.remove(name)
        await save_distributors(dists)
        return True
    return False


# ── Per-user entry storage ────────────────────────────────


async def _read_entries(user_id: int):
    path = _entries_path(user_id)
    try:
        if not os.path.exists(path):
            return []
        async with aiofiles.open(path, mode='r', encoding='utf-8') as f:
            content = await f.read()
            if not content.strip():
                return []
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


async def _write_entries(user_id: int, entries):
    path = _entries_path(user_id)
    async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
        await f.write(json.dumps(entries, indent=4, ensure_ascii=False))


async def add_entry(user_id: int, entry_data):
    entries = await _read_entries(user_id)
    entry_id = 1 if not entries else max(e.get('id', 0) for e in entries) + 1
    entry_data['id'] = entry_id
    entry_data['created_at'] = dhaka_iso_now()
    entries.append(entry_data)
    entries.sort(key=lambda x: x['date'])
    await _write_entries(user_id, entries)
    return entry_id


async def get_entries(user_id: int, month=None, year=None):
    entries = await _read_entries(user_id)
    if month and year:
        filtered = []
        for e in entries:
            e_date = datetime.strptime(e['date'], '%Y-%m-%d')
            if e_date.month == int(month) and e_date.year == int(year):
                filtered.append(e)
        return filtered
    return entries


async def get_entry_by_id(user_id: int, entry_id):
    entries = await _read_entries(user_id)
    for e in entries:
        if e['id'] == entry_id:
            return e
    return None


async def update_entry(user_id: int, entry_id, updated_data):
    entries = await _read_entries(user_id)
    for i, e in enumerate(entries):
        if e['id'] == entry_id:
            entries[i].update(updated_data)
            entries[i]['updated_at'] = dhaka_iso_now()
            entries.sort(key=lambda x: x['date'])
            await _write_entries(user_id, entries)
            return True
    return False


async def delete_entry(user_id: int, entry_id):
    entries = await _read_entries(user_id)
    initial_len = len(entries)
    del_idx = -1
    for i, e in enumerate(entries):
        if e['id'] == entry_id:
            del_idx = i
            break
    if del_idx == -1:
        return False
    entries.pop(del_idx)
    if del_idx < len(entries):
        await _recalculate_odometers(entries, del_idx)
    await _write_entries(user_id, entries)
    return True


async def _recalculate_odometers(entries, start_idx):
    for i in range(start_idx, len(entries)):
        if i == 0:
            continue
        prev_entry = entries[i-1]
        entries[i]['odo_start'] = prev_entry['odo_end']
        entries[i]['odo_end'] = entries[i]['odo_start'] + entries[i].get('total_km', 0)
        entries[i]['updated_at'] = dhaka_iso_now()


async def update_entry_and_cascade(user_id: int, entry_id, updated_data):
    entries = await _read_entries(user_id)
    target_idx = -1
    for i, e in enumerate(entries):
        if e['id'] == entry_id:
            target_idx = i
            break
    if target_idx == -1:
        return False
    if 'odo_start' in updated_data and 'total_km' not in updated_data:
        updated_data['odo_end'] = updated_data['odo_start'] + entries[target_idx].get('total_km', 0)
    elif 'odo_end' in updated_data and 'total_km' not in updated_data:
        updated_data['total_km'] = updated_data['odo_end'] - entries[target_idx]['odo_start']
    elif 'total_km' in updated_data:
        updated_data['odo_end'] = entries[target_idx]['odo_start'] + updated_data['total_km']
    entries[target_idx].update(updated_data)
    entries[target_idx]['updated_at'] = dhaka_iso_now()
    if target_idx + 1 < len(entries):
        await _recalculate_odometers(entries, target_idx + 1)
    await _write_entries(user_id, entries)
    return True


async def get_last_day_in_month(user_id: int, month, year):
    entries = await get_entries(user_id, month, year)
    if not entries:
        return None
    last_date = datetime.strptime(entries[-1]['date'], '%Y-%m-%d')
    return last_date.day


async def get_last_odo(user_id: int):
    entries = await _read_entries(user_id)
    if not entries:
        return 0
    return entries[-1].get('odo_end', 0)


# ── Per-user preferences ──────────────────────────────────


async def get_user_prefs(user_id: int) -> dict:
    path = _user_prefs_path(user_id)
    try:
        if not os.path.exists(path):
            return {}
        async with aiofiles.open(path, mode='r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content) if content.strip() else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


async def set_user_prefs(user_id: int, prefs: dict):
    path = _user_prefs_path(user_id)
    async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
        await f.write(json.dumps(prefs, ensure_ascii=False, indent=2))


# ── Logsheet file tracking (no-op fallback for file backend) ──

async def save_logsheet_file_id(user_id: int, month: int, year: int, file_id: str, file_name: str):
    pass


async def get_logsheet_file_id(user_id: int, month: int, year: int):
    return None


async def delete_logsheet_file_id(user_id: int, month: int, year: int):
    pass


# ── Dispatch to MongoDB when configured ─────────────────────
if os.getenv("MONGODB_URL"):
    import core.mongo_db as _mongo

    # Save file-based references for fallback
    _file = {
        'is_registered': is_registered,
        'add_user': add_user,
        'remove_user': remove_user,
        'get_all_users': get_all_users,
        'init_user_storage': init_user_storage,
        'init_db': init_db,
        'add_entry': add_entry,
        'get_entries': get_entries,
        'get_entry_by_id': get_entry_by_id,
        'update_entry': update_entry,
        'delete_entry': delete_entry,
        'update_entry_and_cascade': update_entry_and_cascade,
        'get_last_day_in_month': get_last_day_in_month,
        'get_last_odo': get_last_odo,
        'get_user_prefs': get_user_prefs,
        'set_user_prefs': set_user_prefs,
        'get_distributors': get_distributors,
        'save_distributors': save_distributors,
        'add_distributor': add_distributor,
        'remove_distributor': remove_distributor,
        'save_logsheet_file_id': save_logsheet_file_id,
        'get_logsheet_file_id': get_logsheet_file_id,
        'delete_logsheet_file_id': delete_logsheet_file_id,
    }

    _mongo_available = False

    async def _use_mongo():
        """Check if MongoDB is reachable and update the flag."""
        global _mongo_available
        db = await _mongo.get_db()
        _mongo_available = db is not None
        return _mongo_available

    async def is_registered(user_id):  # noqa: F811
        if _mongo_available:
            return await _mongo.is_registered(user_id)
        return await _file['is_registered'](user_id)

    async def add_user(user_id, role="user"):  # noqa: F811
        if _mongo_available:
            return await _mongo.add_user(user_id, role)
        return await _file['add_user'](user_id, role)

    async def remove_user(user_id):  # noqa: F811
        if _mongo_available:
            return await _mongo.remove_user(user_id)
        return await _file['remove_user'](user_id)

    async def get_all_users():  # noqa: F811
        if _mongo_available:
            return await _mongo.get_all_users()
        return await _file['get_all_users']()

    async def init_user_storage(user_id):  # noqa: F811
        if _mongo_available:
            return await _mongo.init_user_storage(user_id)
        return await _file['init_user_storage'](user_id)

    async def _sync_mongo_to_local():
        """Pull all data from MongoDB and write to local JSON files."""

        def _write_json(path, data):
            _ensure_data_dir()
            parent = os.path.dirname(path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        # Users
        users = await _mongo.get_all_users()
        _write_json(USERS_PATH, users)

        # Per-user entries & prefs
        for uid_str in users:
            uid = int(uid_str)

            entries = await _mongo.get_entries(uid)
            for e in entries:
                e.pop("_id", None)
                e.pop("user_id", None)
            _write_json(_entries_path(uid), entries)

            prefs = await _mongo.get_user_prefs(uid)
            _write_json(_user_prefs_path(uid), prefs)

        # Distributors
        dists = await _mongo.get_distributors()
        _write_json(DIST_PATH, dists)

    async def init_db():  # noqa: F811
        await _use_mongo()
        if _mongo_available:
            await _mongo.init_db()
            await _sync_mongo_to_local()
            return
        return await _file['init_db']()

    async def add_entry(user_id, entry_data):  # noqa: F811
        if _mongo_available:
            return await _mongo.add_entry(user_id, entry_data)
        return await _file['add_entry'](user_id, entry_data)

    async def get_entries(user_id, month=None, year=None):  # noqa: F811
        if _mongo_available:
            return await _mongo.get_entries(user_id, month, year)
        return await _file['get_entries'](user_id, month, year)

    async def get_entry_by_id(user_id, entry_id):  # noqa: F811
        if _mongo_available:
            return await _mongo.get_entry_by_id(user_id, entry_id)
        return await _file['get_entry_by_id'](user_id, entry_id)

    async def update_entry(user_id, entry_id, updated_data):  # noqa: F811
        if _mongo_available:
            return await _mongo.update_entry(user_id, entry_id, updated_data)
        return await _file['update_entry'](user_id, entry_id, updated_data)

    async def delete_entry(user_id, entry_id):  # noqa: F811
        if _mongo_available:
            return await _mongo.delete_entry(user_id, entry_id)
        return await _file['delete_entry'](user_id, entry_id)

    async def update_entry_and_cascade(user_id, entry_id, updated_data):  # noqa: F811
        if _mongo_available:
            return await _mongo.update_entry_and_cascade(user_id, entry_id, updated_data)
        return await _file['update_entry_and_cascade'](user_id, entry_id, updated_data)

    async def get_last_day_in_month(user_id, month, year):  # noqa: F811
        if _mongo_available:
            return await _mongo.get_last_day_in_month(user_id, month, year)
        return await _file['get_last_day_in_month'](user_id, month, year)

    async def get_last_odo(user_id):  # noqa: F811
        if _mongo_available:
            return await _mongo.get_last_odo(user_id)
        return await _file['get_last_odo'](user_id)

    async def get_user_prefs(user_id):  # noqa: F811
        if _mongo_available:
            return await _mongo.get_user_prefs(user_id)
        return await _file['get_user_prefs'](user_id)

    async def set_user_prefs(user_id, prefs):  # noqa: F811
        if _mongo_available:
            return await _mongo.set_user_prefs(user_id, prefs)
        return await _file['set_user_prefs'](user_id, prefs)

    async def get_distributors():  # noqa: F811
        if _mongo_available:
            return await _mongo.get_distributors()
        return await _file['get_distributors']()

    async def save_distributors(dist_list):  # noqa: F811
        if _mongo_available:
            return await _mongo.save_distributors(dist_list)
        return await _file['save_distributors'](dist_list)

    async def add_distributor(name):  # noqa: F811
        if _mongo_available:
            return await _mongo.add_distributor(name)
        return await _file['add_distributor'](name)

    async def remove_distributor(name):  # noqa: F811
        if _mongo_available:
            return await _mongo.remove_distributor(name)
        return await _file['remove_distributor'](name)

    async def save_logsheet_file_id(user_id, month, year, file_id, file_name):  # noqa: F811
        if _mongo_available:
            return await _mongo.save_logsheet_file_id(user_id, month, year, file_id, file_name)
        return await _file['save_logsheet_file_id'](user_id, month, year, file_id, file_name)

    async def get_logsheet_file_id(user_id, month, year):  # noqa: F811
        if _mongo_available:
            return await _mongo.get_logsheet_file_id(user_id, month, year)
        return await _file['get_logsheet_file_id'](user_id, month, year)

    async def delete_logsheet_file_id(user_id, month, year):  # noqa: F811
        if _mongo_available:
            return await _mongo.delete_logsheet_file_id(user_id, month, year)
        return await _file['delete_logsheet_file_id'](user_id, month, year)
