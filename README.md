# PathikBot — Motorcycle Logsheet Automation System

A **Telegram bot** for Territory Marketing Officers to track daily field visit expenses and auto-generate monthly **DOCX logsheet reports** in Bijoy-encoded Bangla (SutonnyMJ font).

---

## Features

### Telegram Bot (Bangla UI)
- **`/newentry`** — 20-step guided entry flow: type → month → date → odometer → distance → petrol → mobil → DA → manager → distributor selection → confirmation
- **`/listentries`** — View entries with optional filters (petrol, mobil, meeting, manager) saved per-user
- **`/summary`** — Aggregated monthly statistics (total tours, km, fuel cost, DA, etc.)
- **`/editentry` / `/delentry`** — Modify or delete entries with automatic cascading odometer recalculation
- **`/months`** — Browse and manage records from previous months (list, summary, generate report)
- **`/settings`** — Configure petrol price, mobil price, DA rate, transport fee, and manage distributor list
- **`/generate`** — Generate a formatted `.docx` logsheet report
- **`/adduser`, `/removeuser`, `/users`** — Owner-only user management commands

### Smart Calculations
- **Distance**: supports expressions like `14+15` or `2*30+5`
- **Petrol cost**: `liters × price_per_liter` (auto-calculated)
- **Mobil cost**: `liters × price_per_liter` (auto-calculated)
- **Total cost** varies by entry type (Regular Tour vs Monthly Meeting)
- **Cascading odometers**: editing/deleting an entry auto-updates all subsequent entries' readings
- **Threshold tracking**: petrol (480 km) / mobil (1000 km) — carry-forward excess distance adjusts next threshold; due reminders shown when threshold reached

### Data Isolation & User Management
- **Owner + registered users** — Owner (ID: 6161189904) auto-registered on startup; unregistered users are blocked at every handler
- **Per-user data storage** — `data/entries_{user_id}.json` and `data/user_prefs/{user_id}.json`
- **Legacy migration** — Auto-migrates `data/logsheet.db` (old JSON format) and `data/entries.json` to per-user files on startup

### Archive Browser
- Browse months with entries, pick any month and:
  - List all entries for that month
  - View monthly summary
  - Generate DOCX report

### DOCX Report Generation
- Landscape A4 format with 4 page types:
  - **Type 1** — Header + first 3 entries
  - **Type 2** — Middle pages (4 entries each, cloned as needed)
  - **Type 3** — Last entries + totals row
  - **Type 4** — Summary statistics
- All Bangla text encoded in **Bijoy** (`SutonnyMJ` font)
- Uses a customizable DOCX template
- Standalone `docx_generator/generate.py` alternative (lxml-based, no python-docx dependency)

### All Bangla Strings in One Place
All user-facing text is externalized to `bot/strings.json`. Edit text without touching code.

### Entry Display
- Each entry sent as a separate message with `blockquote` headers & bold values
- Distributors in collapsible `expandable` blockquote
- Monthly summary sent after all entries

---

## Quick Start

### Prerequisites
- Python 3.10+
- A Telegram Bot Token (from [@BotFather](https://t.me/botfather))

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/PathikBot.git
cd PathikBot
pip install -r requirements.txt
```

### Configuration

Create `.env` in the project root:

```env
BOT_TOKEN=your_telegram_bot_token
PETROL_PRICE_PER_LITER=140.7
MOBIL_PRICE_PER_LITER=560.0
COMPANY_NAME=বিএআই এগিকালচারাল ইন্ডাস্ট্রিজ লিমিটেড
OFFICER_NAME=মো: আশরাফ আলী
DESIGNATION=টেরিটরি মার্কেটিং অফিসার
POSTING_AREA=ডোমার
MOTORCYCLE_BRAND=বাজাজ ডিসকভার
DEPO_NAME=রংপুর
```

### Run

```bash
python -m bot.main
```

Or double-click `run.bat` on Windows.

---

## Project Structure

```
PathikBot/
├── bot/                            # Telegram Bot layer
│   ├── main.py                     # Entry point, 18 handler registrations
│   ├── auth.py                     # Authorization gate (require_auth)
│   ├── keyboards.py                # 18 inline keyboard types (Bangla)
│   ├── strings.py                  # S(key, **kwargs) string loader
│   ├── strings.json                # ALL user-facing Bangla text
│   └── handlers/
│       ├── start.py                # /start, /help, main menu
│       ├── new_entry.py            # 20-state entry ConversationHandler
│       ├── summary.py              # /listentries (with filter UI), /summary
│       ├── settings.py             # /settings, /editentry, /delentry, dist mgmt
│       ├── archive.py              # /months (past records browser)
│       ├── admin.py                # /adduser, /removeuser, /users
│       └── report.py               # /generate DOCX report
├── core/
│   ├── database.py                 # User mgmt, per-user entries CRUD, cascading odos
│   └── calculations.py             # Cost, summary, threshold tracking
├── docx_generator/
│   ├── __init__.py
│   ├── generate.py                 # Main logsheet generator (lxml, used by bot)
│   ├── generator.py                # Alternate python-docx generator (legacy)
│   ├── xml_utils.py                # Cell text formatting helpers
│   ├── converter.py                # Unicode → Bijoy converter (main impl)
│   ├── bijoy_converter.py          # Unified interface for conversion
│   └── util.py                     # Helper utilities for converter
├── scripts/
│   ├── generate_templates.py       # Pre-generates all 28 template variants
│   └── populate_test_data.py       # Populates templates with sample data
├── data/
│   ├── users.json                  # User registry (auto-created)
│   ├── distributors.json           # Shared distributor list
│   ├── entries_{user_id}.json      # Per-user entries (auto-created)
│   └── user_prefs/{user_id}.json   # Per-user preferences (auto-created)
├── templates/                      # Master DOCX template
├── generated_logsheets/            # Pre-generated 28 template variants
├── outputs/                        # Generated reports
├── bot/
│   ├── main.py                     # Entry point
│   ├── auth.py                     # Authentication
│   ├── keyboards.py                # Inline keyboards
│   ├── strings.json                # User-facing strings
│   ├── strings.py                  # String loader
│   └── handlers/                   # Conversation handlers
└── .env                            # Configuration
```

### Conversation Flows

```
Entry flow:
  /newentry → type → sticky month → date (skip Fridays) → odo start
  → distance (expression support) → odo end → petrol? → mobil?
  → manager? → DA confirm → distributor picker → confirmation
  → save → "last entry?" prompt

Settings flow:
  /settings → settings menu → any sub-action (stays in conv)
  → back → settings → main menu

Archive flow:
  /months → month list → pick month → list/summary/generate

Edit/Delete flow:
  /editentry or /delentry → pick entry → edit field or confirm delete
  → cascade odometer recalculation → back to entry list
```

---

## Tech Stack

| Component | Library |
|-----------|---------|
| Bot Framework | `python-telegram-bot` (async, v20.x) |
| Document Generation | `python-docx` + custom XML |
| Standalone Generator | `lxml` (docx_generator/generate.py) |
| Bangla Encoding | Custom Unicode → Bijoy converter |
| Data Storage | JSON (via `aiofiles`) |
| Environment | `python-dotenv` |
| Testing | `pytest` + `pytest-asyncio` |

---

## Testing

```bash
python -m pytest tests/ -v
```

**45 tests total:**
- `test_calculations.py` — 16 scenarios: threshold tracking, carry-forward, edge cases
- `test_user_mgmt.py` — 29 scenarios: user CRUD, data isolation, auth, edge cases

---

## Contributing

This is a specialized tool built for a specific workflow. Feel free to fork and adapt for your needs.

---

## License

MIT
