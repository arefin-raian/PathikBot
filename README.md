# PathikBot — Motorcycle Logsheet Automation System

A **Telegram bot** for Territory Marketing Officers to track daily field-visit expenses and auto-generate monthly **DOCX logsheet reports** in Bijoy-encoded Bangla (SutonnyMJ font).

---

## Features

### Telegram Bot (Bangla UI)
- **`/newentry`** — 20-step guided entry flow: type → month → date → odometer → distance → petrol → mobil → DA → manager → distributor selection → confirmation
- **`/listentries`** — View entries with optional filters (petrol, mobil, meeting, manager) saved per-user
- **`/summary`** — Aggregated monthly statistics (total tours, km, fuel cost, DA, etc.)
- **`/editentry` / `/delentry`** — Modify or delete entries with automatic cascading odometer recalculation
- **`/months`** — Browse and manage records from previous months (list, summary, generate report)
- **`/settings`** — Per-user configurable petrol price, mobil price, DA rate, transport fee, and distributor list
- **`/generate`** — Generate a formatted `.docx` logsheet report
- **`/adduser`**, **`/removeuser`**, **`/users`** — Owner-only interactive user management

### Smart Calculations
- **Distance**: supports expressions like `14+15` or `2*30+5`
- **Petrol cost**: `liters × price_per_liter` (auto-calculated)
- **Mobil cost**: `liters × price_per_liter` (auto-calculated)
- **Total cost** varies by entry type (Regular Tour vs Monthly Meeting)
- **Cascading odometers**: editing/deleting an entry auto-updates all subsequent entries' readings
- **Threshold tracking**: petrol (480 km) / mobil (1000 km) — carry-forward excess distance adjusts next threshold; due reminders shown when threshold reached

### Data Storage (Dual Backend)
- **File-based** (local dev) — JSON files in `data/`
- **MongoDB** (production) — via `motor` async driver; auto-migrates legacy data on startup
- **Telegram Channel** — Generated DOCX reports uploaded to a private channel for persistent file storage

### Per-User Pricing
- Petrol price, mobil price, DA amount, and transport fee are **stored per user**, not in `.env`
- Configured via the bot's `/settings` menu — each user can have their own rates
- Hardcoded defaults apply if no custom value is set

### DOCX Report Generation & PDF Conversion
- Landscape A4 format with 4 page types:
  - **Type 1** — Header + first 3 entries
  - **Type 2** — Middle pages (4 entries each, cloned as needed)
  - **Type 3** — Last entries + totals row
  - **Type 4** — Summary statistics
- All Bangla text encoded in **Bijoy** (`SutonnyMJ` font)
- Report files uploaded to a Telegram channel for persistent access
- **PDF conversion** via Aspose.Words (no system dependencies — cross-platform, no headless server needed)

### All Bangla Strings in One Place
All user-facing text is externalized to `bot/text_resources.json`. Edit text without touching code.

---

## Installation

### Prerequisites
- Python 3.10+
- A Telegram Bot Token (from [@BotFather](https://t.me/botfather))

### Windows

```powershell
git clone https://github.com/YOUR_USERNAME/PathikBot.git
cd PathikBot
python -m venv venv
.\venv\Scripts\Activate
pip install -r requirements.txt
```

### Linux (Ubuntu/Debian)

```bash
git clone https://github.com/YOUR_USERNAME/PathikBot.git
cd PathikBot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Termux (Android)

```bash
pkg update && pkg upgrade
pkg install python git
git clone https://github.com/YOUR_USERNAME/PathikBot.git
cd PathikBot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> **Note**: Running 24/7 on Termux requires extra tools like `termux-services` or `tmux`. See the **Deployment** section below for persistent hosting options.

---

## Configuration

### 1. Basic Configuration (`.env`)

Create `.env` in the project root:

```env
# Required
BOT_TOKEN=your_telegram_bot_token

# Optional (MongoDB — enables persistence across restarts)
MONGODB_URL=mongodb+srv://user:pass@cluster.mongodb.net/...
MONGODB_DB_NAME=pathikbot

# Optional (Telegram channel — stores generated DOCX files persistently)
STORAGE_CHANNEL_ID=@your_channel_username

# Company info (used in generated reports)
COMPANY_NAME=বিএআই এগিকালচারাল ইন্ডাস্ট্রিজ লিমিটেড
OFFICER_NAME=মো: আশরাফ আলী
DESIGNATION=টেরিটরি মার্কেটিং অফিসার
POSTING_AREA=ডোমার
MOTORCYCLE_BRAND=বাজাজ ডিসকভার
DEPO_NAME=রংপুর

# PDF_ENABLED=false to skip PDF conversion (default: true)
# PDF_ENABLED=true

# Aspose.Words license (optional — removes evaluation watermark)
# Set path to license file or leave unset for evaluation mode
# ASPOSE_LICENSE=aspose.lic
```

### 2. Storage Backend Options

| Backend | When to use | How to enable |
|---------|-------------|---------------|
| **File-based** | Local dev, testing | Leave `MONGODB_URL` unset |
| **MongoDB** | Production (Render, Railway, VPS) | Set `MONGODB_URL` + `MONGODB_DB_NAME` |
| **Telegram Channel** | Persistent file storage | Set `STORAGE_CHANNEL_ID` |

When `MONGODB_URL` is set, the bot automatically:
- Connects to MongoDB Atlas (or your self-hosted MongoDB)
- Creates collections: `users`, `entries`, `user_prefs`, `distributors`, `logsheets`
- Migrates existing JSON data (`entries_*.json`, `users.json`, `user_prefs/*.json`) into MongoDB

### 3. Telegram Channel Setup (for DOCX storage)

1. Create a **private Telegram channel**
2. Add your bot as an **administrator** (needs "Post Messages" permission)
3. Set `STORAGE_CHANNEL_ID` in `.env` — can be `@channel_username` or numeric ID (e.g. `-1001234567890`)

---

## Run

### Local Development

```bash
python -m bot.main
```

Or double-click `run.bat` on Windows.

### Verify It's Running

Send `/start` to your bot on Telegram. If you're the owner (ID `6161189904`), you'll be auto-registered.

---

## Testing

```bash
python -m pytest tests/ -v
```

**61 tests total:**
- `test_calculations.py` — 31 scenarios: threshold tracking, signed carry-forward, edge cases
- `test_user_mgmt.py` — 30 scenarios: user CRUD, data isolation, auth, edge cases

> Tests always use the **file-based backend** (clears `MONGODB_URL` automatically in `conftest.py`).

---

## Deployment

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "bot.main"]
```

```yaml
# docker-compose.yml
services:
  bot:
    build: .
    env_file: .env
    restart: unless-stopped
```

```bash
docker compose up -d
```

### Render

1. Push your repo to GitHub
2. Go to [dashboard.render.com](https://dashboard.render.com) → **New +** → **Web Service**
3. Connect your repo
4. Fill:
   - **Name**: `pathikbot`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python -m bot.main`
   - **Plan**: Free
5. Add Environment Variables:
   - `BOT_TOKEN` (required)
   - `MONGODB_URL` (required for persistence — use [MongoDB Atlas](https://www.mongodb.com/atlas) free tier)
   - `MONGODB_DB_NAME` = `pathikbot`
   - `STORAGE_CHANNEL_ID` (optional)
   - `COMPANY_NAME`, `OFFICER_NAME`, etc.
6. Click **Deploy Web Service**

> **Note**: Render's free tier spins down after inactivity. The bot itself is event-driven (Telegram webhook), so it responds on demand. For polling mode, set **Health Check Path** to `/` and add a simple health endpoint, or use a **Cron Job** to ping it periodically.

### Railway

1. Push repo to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. Add Environment Variables (same as Render above)
4. Set Start Command: `python -m bot.main`
5. Railway auto-detects Python — no build command needed

### Koyeb / Fly.io / Heroku

Same pattern: set env vars, start command is `python -m bot.main`. Use MongoDB Atlas for persistence across restarts.

### VPS (Linux)

```bash
# Using systemd
sudo nano /etc/systemd/system/pathikbot.service
```

```ini
[Unit]
Description=PathikBot Telegram Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/PathikBot
EnvironmentFile=/home/youruser/PathikBot/.env
ExecStart=/home/youruser/PathikBot/venv/bin/python -m bot.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pathikbot
```

### Termux (Android — 24/7)

```bash
# Install termux-services
pkg install termux-services
# Start bot in a tmux session
pkg install tmux
tmux new -s pathikbot
cd PathikBot && source venv/bin/activate && python -m bot.main
# Detach: Ctrl+B, D
# Reattach: tmux attach -t pathikbot
```

---

## Project Structure

```
PathikBot/
├── bot/                            # Telegram Bot layer
│   ├── main.py                     # Entry point, handler registrations
│   ├── auth.py                     # Authorization gate (require_auth)
│   ├── inline_keyboards.py         # Inline keyboard builders (Bangla)
│   ├── text_resources.py           # S(key, **kwargs) string loader
│   ├── text_resources.json         # ALL user-facing Bangla text
│   └── handlers/
│       ├── start.py                # /start, /help, main menu
│       ├── new_entry.py            # 20-state entry ConversationHandler
│       ├── summary.py              # /listentries (with filter UI), /summary
│       ├── settings.py             # Per-user prefs, edit/delete entries, dist mgmt
│       ├── archive.py              # /months (past records browser)
│       ├── admin.py                # Interactive /adduser, /removeuser, /users
│       └── report.py               # /generate DOCX report + channel upload
├── core/
│   ├── file_data_store.py          # User mgmt, entries CRUD, cascading odos, dispatch
│   ├── mongo_db.py                 # MongoDB async backend (motor) + legacy migration
│   └── expense_calculations.py     # Cost, summary, threshold tracking
├── docx_generator/
│   ├── __init__.py
│   ├── logsheet_generator.py       # Main generator (lxml, used by bot)
│   ├── legacy_docx_generator.py    # Alternate python-docx generator (legacy)
│   ├── docx_xml_helpers.py         # Cell formatting helpers
│   ├── bijoy_converter.py          # Unicode → Bijoy conversion wrapper
│   ├── bijoy_conversion_rules.py   # Bijoy mapping engine
│   └── character_map_utils.py      # String/character utilities
├── scripts/
│   ├── template_variant_generator.py
│   └── test_data_generator.py
├── data/
│   ├── users.json                  # User registry (file backend)
│   ├── distributors.json           # Shared distributor list
│   ├── entries_{user_id}.json      # Per-user entries (file backend)
│   └── user_prefs/{user_id}.json   # Per-user preferences (file backend)
├── templates/
├── generated_logsheets/
├── outputs/
├── tests/
│   ├── conftest.py                 # Forces file-based backend for tests
│   ├── test_user_mgmt.py           # 30 user mgmt tests
│   └── test_calculations.py        # 31 calculation tests
├── .env.example                    # Template for .env (no secrets)
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── run.bat                         # Windows launcher
└── README.md
```

---

## Tech Stack

| Component | Library |
|-----------|---------|
| Bot Framework | [`python-telegram-bot`](https://github.com/python-telegram-bot/python-telegram-bot) (async, v20.x) |
| MongoDB Driver (production) | [`motor`](https://github.com/mongodb/motor) (async) |
| MongoDB Driver (tests) | [`pymongo`](https://github.com/mongodb/mongo-python-driver) (synchronous) |
| Document Generation | `python-docx` + custom XML |
| Standalone Generator | `lxml` |
| PDF Conversion | [`aspose-words`](https://products.aspose.com/words/python/) (no system deps) |
| Bangla Encoding | Custom Unicode → Bijoy converter |
| File Storage (dev) | `aiofiles` + JSON |
| Environment | `python-dotenv` |
| Testing | `pytest` + `pytest-asyncio` |

---

## Contributing

This is a specialized tool built for a specific workflow. Feel free to fork and adapt for your needs.

---

## License

MIT
