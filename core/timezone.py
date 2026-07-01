"""Timezone helpers for PathikBot.

All user-facing month/date defaults should use Bangladesh time (GMT+6).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

DHAKA_TZ = ZoneInfo("Asia/Dhaka")

def now_dhaka() -> datetime:
    return datetime.now(DHAKA_TZ)

def current_month_year() -> tuple[int, int]:
    now = now_dhaka()
    return now.month, now.year

def dhaka_iso_now() -> str:
    return now_dhaka().isoformat()

def dhaka_timestamp() -> str:
    return now_dhaka().strftime('%Y-%m-%d %H:%M:%S')
