"""Comprehensive tests for user management system."""

import sys
import os
import json
import pytest
import asyncio
from unittest.mock import patch, mock_open, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.file_data_store import (
    OWNER_ID, load_users, save_users, is_registered,
    add_user, remove_user, get_all_users, init_user_storage,
    is_owner, init_db, _read_entries, _write_entries,
    get_entries, add_entry, get_last_odo, get_last_day_in_month,
    delete_entry, update_entry_and_cascade,
    get_user_prefs, set_user_prefs
)


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_data_files():
    """Ensure clean state before each test. Preserves owner's production data."""
    import glob
    OWNER_ID = 6161189904
    os.makedirs('data', exist_ok=True)
    # Clean users.json (test state) and test-only user data files
    for f in glob.glob('data/users.json'):
        os.remove(f)
    for f in glob.glob('data/entries_*.json'):
        uid = os.path.basename(f).replace('entries_', '').replace('.json', '')
        if uid != str(OWNER_ID):
            os.remove(f)
    for f in glob.glob('data/user_prefs/*.json'):
        uid = os.path.basename(f).replace('.json', '')
        if uid != str(OWNER_ID):
            os.remove(f)
    yield
    for f in glob.glob('data/users.json'):
        os.remove(f)
    for f in glob.glob('data/entries_*.json'):
        uid = os.path.basename(f).replace('entries_', '').replace('.json', '')
        if uid != str(OWNER_ID):
            os.remove(f)
    for f in glob.glob('data/user_prefs/*.json'):
        uid = os.path.basename(f).replace('.json', '')
        if uid != str(OWNER_ID):
            os.remove(f)


# ── Helpers ───────────────────────────────────────────────

def run_async(coro):
    return asyncio.run(coro)


# ── User Management Tests ────────────────────────────────


class TestAddUser:

    def test_add_new_user(self):
        assert add_user(12345) is True
        users = load_users()
        assert '12345' in users
        assert users['12345']['role'] == 'user'
        assert 'added_at' in users['12345']

    def test_add_duplicate_user(self):
        assert add_user(12345) is True
        assert add_user(12345) is False

    def test_add_user_with_custom_role(self):
        add_user(99999, role='manager')
        assert load_users()['99999']['role'] == 'manager'

    def test_add_user_creates_storage_files(self):
        add_user(77777)
        ep = f'data/entries_77777.json'
        pp = f'data/user_prefs/77777.json'
        assert os.path.exists(ep)
        assert os.path.exists(pp)
        with open(ep) as f:
            assert json.load(f) == []
        with open(pp) as f:
            assert json.load(f) == {}


class TestRemoveUser:

    def test_remove_existing_user(self):
        add_user(12345)
        assert remove_user(12345) is True
        assert not is_registered(12345)

    def test_remove_nonexistent_user(self):
        assert remove_user(99999) is False

    def test_remove_doesnt_affect_others(self):
        add_user(111)
        add_user(222)
        remove_user(111)
        users = load_users()
        assert '111' not in users
        assert '222' in users


class TestIsRegistered:

    def test_unregistered_user(self):
        assert is_registered(99999) is False

    def test_registered_user(self):
        add_user(12345)
        assert is_registered(12345) is True

    def test_owner_check(self):
        assert is_owner(OWNER_ID) is True
        assert is_owner(12345) is False


class TestListUsers:

    def test_list_all_users(self):
        add_user(111)
        add_user(222)
        users = get_all_users()
        assert '111' in users
        assert '222' in users
        assert len(users) == 2

    def test_empty_user_list(self):
        assert get_all_users() == {}


# ── Data Isolation Tests ─────────────────────────────────

@pytest.mark.asyncio
class TestDataIsolation:

    async def test_users_have_separate_entries(self):
        user_a, user_b = 1001, 1002
        add_user(user_a)
        add_user(user_b)

        entry_a = {'date': '2026-06-01', 'total_km': 50, 'odo_start': 0, 'odo_end': 50, 'entry_type': 'REGULAR'}
        entry_b = {'date': '2026-06-02', 'total_km': 100, 'odo_start': 50, 'odo_end': 150, 'entry_type': 'REGULAR'}

        id_a = await add_entry(user_a, entry_a.copy())
        id_b = await add_entry(user_b, entry_b.copy())

        entries_a = await get_entries(user_a)
        entries_b = await get_entries(user_b)

        assert len(entries_a) == 1
        assert len(entries_b) == 1
        assert entries_a[0]['total_km'] == 50
        assert entries_b[0]['total_km'] == 100

    async def test_delete_only_affects_own_user(self):
        user_a, user_b = 1001, 1002
        add_user(user_a)
        add_user(user_b)

        entry_a = {'date': '2026-06-01', 'total_km': 50, 'odo_start': 0, 'odo_end': 50, 'entry_type': 'REGULAR'}
        entry_b = {'date': '2026-06-02', 'total_km': 100, 'odo_start': 50, 'odo_end': 150, 'entry_type': 'REGULAR'}

        id_a = await add_entry(user_a, entry_a.copy())
        await add_entry(user_b, entry_b.copy())

        await delete_entry(user_a, id_a)

        assert len(await get_entries(user_a)) == 0
        assert len(await get_entries(user_b)) == 1

    async def test_get_last_odo_isolation(self):
        user_a, user_b = 1001, 1002
        add_user(user_a)
        add_user(user_b)

        await add_entry(user_a, {'date': '2026-06-01', 'total_km': 50, 'odo_start': 0, 'odo_end': 50, 'entry_type': 'REGULAR'})
        await add_entry(user_b, {'date': '2026-06-02', 'total_km': 200, 'odo_start': 100, 'odo_end': 300, 'entry_type': 'REGULAR'})

        assert await get_last_odo(user_a) == 50
        assert await get_last_odo(user_b) == 300

    async def test_user_prefs_isolation(self):
        user_a, user_b = 1001, 1002
        add_user(user_a)
        add_user(user_b)

        await set_user_prefs(user_a, {'theme': 'dark'})
        await set_user_prefs(user_b, {'theme': 'light'})

        assert await get_user_prefs(user_a) == {'theme': 'dark'}
        assert await get_user_prefs(user_b) == {'theme': 'light'}

    async def test_get_last_day_in_month_isolation(self):
        user_a, user_b = 1001, 1002
        add_user(user_a)
        add_user(user_b)

        await add_entry(user_a, {'date': '2026-06-05', 'total_km': 50, 'odo_start': 0, 'odo_end': 50, 'entry_type': 'REGULAR'})
        await add_entry(user_b, {'date': '2026-06-20', 'total_km': 100, 'odo_start': 50, 'odo_end': 150, 'entry_type': 'REGULAR'})

        assert await get_last_day_in_month(user_a, 6, 2026) == 5
        assert await get_last_day_in_month(user_b, 6, 2026) == 20

    async def test_update_entry_and_cascade_isolation(self):
        user_a, user_b = 1001, 1002
        add_user(user_a)
        add_user(user_b)

        id_a = await add_entry(user_a, {'date': '2026-06-01', 'total_km': 50, 'odo_start': 0, 'odo_end': 50, 'entry_type': 'REGULAR'})
        await add_entry(user_b, {'date': '2026-06-02', 'total_km': 100, 'odo_start': 50, 'odo_end': 150, 'entry_type': 'REGULAR'})

        await update_entry_and_cascade(user_a, id_a, {'total_km': 99})

        entries_a = await get_entries(user_a)
        assert entries_a[0]['total_km'] == 99

        entries_b = await get_entries(user_b)
        assert entries_b[0]['total_km'] == 100


# ── Edge Cases ────────────────────────────────────────────

class TestEdgeCases:

    def test_no_entries_for_new_user(self):
        add_user(99999)
        result = run_async(get_entries(99999))
        assert result == []

    def test_get_last_odo_no_entries(self):
        result = run_async(get_last_odo(99999))
        assert result == 0

    def test_get_last_day_in_month_no_entries(self):
        result = run_async(get_last_day_in_month(99999, 6, 2026))
        assert result is None

    def test_init_user_storage_creates_files(self):
        init_user_storage(55555)
        assert os.path.exists(f'data/entries_55555.json')
        assert os.path.exists(f'data/user_prefs/55555.json')

    def test_users_file_not_exists(self):
        assert load_users() == {}

    def test_corrupted_users_file(self):
        with open('data/users.json', 'w') as f:
            f.write('{corrupted')
        assert load_users() == {}

    def test_owner_auto_registered_on_init_db(self):
        run_async(init_db())
        assert is_registered(OWNER_ID)

    def test_is_registered_empty_file(self):
        assert is_registered(99999) is False


# ── Auth Module Tests ────────────────────────────────────

class TestRequireAuth:

    def test_is_owner_returns_true(self):
        assert is_owner(OWNER_ID) is True

    def test_is_owner_returns_false(self):
        assert is_owner(54321) is False

    def test_registered_user_is_recognized(self):
        add_user(77777)
        assert is_registered(77777) is True
