import json
import os
import aiofiles
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv('DB_PATH', 'data/entries.json')
DIST_PATH = 'data/distributors.json'

async def init_db():
    """Initialize the JSON files if they don't exist."""
    if not os.path.exists(os.path.dirname(DB_PATH)):
        os.makedirs(os.path.dirname(DB_PATH))
    
    if not os.path.exists(DB_PATH):
        async with aiofiles.open(DB_PATH, mode='w', encoding='utf-8') as f:
            await f.write(json.dumps([], indent=4))
            
    if not os.path.exists(DIST_PATH):
        # Default list will be written by a script or manual creation if not found
        pass

async def get_distributors():
    """Read distributors from JSON file."""
    try:
        if not os.path.exists(DIST_PATH):
            return []
        async with aiofiles.open(DIST_PATH, mode='r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content)
    except Exception:
        return []

async def save_distributors(dist_list):
    """Save distributors to JSON file."""
    async with aiofiles.open(DIST_PATH, mode='w', encoding='utf-8') as f:
        await f.write(json.dumps(dist_list, indent=4, ensure_ascii=False))

async def add_distributor(name):
    """Add a new distributor."""
    dists = await get_distributors()
    if name not in dists:
        dists.append(name)
        dists.sort()
        await save_distributors(dists)
        return True
    return False

async def remove_distributor(name):
    """Remove a distributor."""
    dists = await get_distributors()
    if name in dists:
        dists.remove(name)
        await save_distributors(dists)
        return True
    return False

async def _read_entries():
    """Read all entries from the JSON file."""
    try:
        if not os.path.exists(DB_PATH):
            return []
        async with aiofiles.open(DB_PATH, mode='r', encoding='utf-8') as f:
            content = await f.read()
            if not content.strip():
                return []
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

async def _write_entries(entries):
    """Write all entries to the JSON file."""
    async with aiofiles.open(DB_PATH, mode='w', encoding='utf-8') as f:
        await f.write(json.dumps(entries, indent=4, ensure_ascii=False))

async def add_entry(entry_data):
    """Add a new entry to the storage."""
    entries = await _read_entries()
    
    # Generate a simple ID
    entry_id = 1 if not entries else max(e.get('id', 0) for e in entries) + 1
    entry_data['id'] = entry_id
    entry_data['created_at'] = datetime.now().isoformat()
    
    entries.append(entry_data)
    # Sort entries by date
    entries.sort(key=lambda x: x['date'])
    
    await _write_entries(entries)
    return entry_id

async def get_entries(month=None, year=None):
    """Get entries, optionally filtered by month and year."""
    entries = await _read_entries()
    if month and year:
        filtered = []
        for e in entries:
            # Assume date format is YYYY-MM-DD
            e_date = datetime.strptime(e['date'], '%Y-%m-%d')
            if e_date.month == int(month) and e_date.year == int(year):
                filtered.append(e)
        return filtered
    return entries

async def get_entry_by_id(entry_id):
    """Get a single entry by its ID."""
    entries = await _read_entries()
    for e in entries:
        if e['id'] == entry_id:
            return e
    return None

async def update_entry(entry_id, updated_data):
    """Update an existing entry."""
    entries = await _read_entries()
    for i, e in enumerate(entries):
        if e['id'] == entry_id:
            entries[i].update(updated_data)
            entries[i]['updated_at'] = datetime.now().isoformat()
            # Re-sort in case date changed
            entries.sort(key=lambda x: x['date'])
            await _write_entries(entries)
            return True
    return False

async def delete_entry(entry_id):
    """Delete an entry by ID and recalculate following odometers."""
    entries = await _read_entries()
    initial_len = len(entries)
    
    # Find the index of the entry to delete
    del_idx = -1
    for i, e in enumerate(entries):
        if e['id'] == entry_id:
            del_idx = i
            break
            
    if del_idx == -1:
        return False
        
    entries.pop(del_idx)
    
    # Recalculate cascading odometers if not the last entry
    if del_idx < len(entries):
        await _recalculate_odometers(entries, del_idx)
    
    await _write_entries(entries)
    return True

async def _recalculate_odometers(entries, start_idx):
    """Internal helper to cascade odometer changes."""
    for i in range(start_idx, len(entries)):
        if i == 0:
            # First entry ever, we can't auto-calculate start odo
            # but usually this won't happen in a mid-list delete
            continue
            
        prev_entry = entries[i-1]
        # Current entry start = previous entry end
        entries[i]['odo_start'] = prev_entry['odo_end']
        # Recalculate end based on stored total_km
        entries[i]['odo_end'] = entries[i]['odo_start'] + entries[i].get('total_km', 0)
        entries[i]['updated_at'] = datetime.now().isoformat()

async def update_entry_and_cascade(entry_id, updated_data):
    """Update an entry and cascade odometer changes to all following entries."""
    entries = await _read_entries()
    target_idx = -1
    for i, e in enumerate(entries):
        if e['id'] == entry_id:
            target_idx = i
            break
            
    if target_idx == -1:
        return False
        
    # Logic for manual Odometer updates
    if 'odo_start' in updated_data and 'total_km' not in updated_data:
        # If user only changed start, end must change too
        updated_data['odo_end'] = updated_data['odo_start'] + entries[target_idx].get('total_km', 0)
    elif 'odo_end' in updated_data and 'total_km' not in updated_data:
        # If user only changed end, total_km (distance) must be recalculated
        updated_data['total_km'] = updated_data['odo_end'] - entries[target_idx]['odo_start']
    elif 'total_km' in updated_data:
        # If distance changed, end must change
        updated_data['odo_end'] = entries[target_idx]['odo_start'] + updated_data['total_km']

    # Update the target entry
    entries[target_idx].update(updated_data)
    entries[target_idx]['updated_at'] = datetime.now().isoformat()
    
    # Cascade to all following
    if target_idx + 1 < len(entries):
        await _recalculate_odometers(entries, target_idx + 1)
        
    await _write_entries(entries)
    return True

async def get_last_day_in_month(month, year):
    """Get the last entry day for a specific month and year."""
    entries = await get_entries(month, year)
    if not entries:
        return None
    # Entries are sorted by date
    last_date = datetime.strptime(entries[-1]['date'], '%Y-%m-%d')
    return last_date.day

async def get_last_odo():
    """Get the last odometer reading from the most recent entry."""
    entries = await _read_entries()
    if not entries:
        return 0
    # entries are sorted by date, so last one is most recent
    return entries[-1].get('odo_end', 0)

# ── User preferences (persistent across bot restarts) ─────

USER_PREFS_PATH = 'data/user_prefs.json'

async def get_user_prefs(user_id: int) -> dict:
    try:
        if not os.path.exists(USER_PREFS_PATH):
            return {}
        async with aiofiles.open(USER_PREFS_PATH, mode='r', encoding='utf-8') as f:
            content = await f.read()
            if not content.strip():
                return {}
            all_prefs = json.loads(content)
            return all_prefs.get(str(user_id), {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

async def set_user_prefs(user_id: int, prefs: dict):
    try:
        if os.path.exists(USER_PREFS_PATH):
            async with aiofiles.open(USER_PREFS_PATH, mode='r', encoding='utf-8') as f:
                content = await f.read()
                all_prefs = json.loads(content) if content.strip() else {}
        else:
            all_prefs = {}
    except (FileNotFoundError, json.JSONDecodeError):
        all_prefs = {}
    all_prefs[str(user_id)] = prefs
    async with aiofiles.open(USER_PREFS_PATH, mode='w', encoding='utf-8') as f:
        await f.write(json.dumps(all_prefs, ensure_ascii=False, indent=2))
