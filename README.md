# PathikBot — Motorcycle Logsheet Automation System

A **Telegram bot** for Territory Marketing Officers to track daily field-visit expenses and auto-generate monthly **DOCX + PDF logsheet reports** in Bijoy-encoded Bangla (SutonnyMJ font).

---

## Features

### Telegram Bot (Bangla UI)
- **`/newentry`** — 20-step guided entry flow: type → month → date → odometer → distance → petrol → mobil → DA → manager → distributor selection → confirmation
- **`/listentries`** — View entries with optional filters (petrol, mobil, meeting, manager) saved per-user
- **`/summary`** — Aggregated monthly statistics (total tours, km, fuel cost, DA, etc.)
- **`/editentry` / `/delentry`** — Modify or delete entries with automatic cascading odometer recalculation
- **`/months`** — Browse and manage records from previous months (list, summary, generate report)
- **`/settings`** — Per-user configurable petrol price, mobil price, DA rate, transport fee, and distributor list
- **`/generate`** — Generate a formatted `.docx` logsheet report (converted to PDF automatically)
- **`/adduser`**, **`/removeuser`**, **`/users`** — Owner-only interactive user management

### Smart Calculations
- **Distance**: supports expressions like `14+15` or `2*30+5`
- **Petrol cost**: `liters × price_per_liter` (auto-calculated)
- **Mobil cost**: `liters × price_per_liter` (auto-calculated)
- **Total cost** varies by entry type (Regular Tour vs Monthly Meeting)
- **Cascading odometers**: editing/deleting an entry auto-updates all subsequent entries' readings
- **Signed carry-forward tracking**: petrol (480 km) / mobil (1000 km) — negative carry-forward = remaining km, positive = excess km carried over; due reminders shown when threshold reached

### Data Storage (Dual Backend)
- **File-based** (local dev) — JSON files in `data/`
- **MongoDB** (production) — via `motor` async driver; auto-syncs from MongoDB to local JSON on startup
- **Telegram Channel** — Generated DOCX/PDF reports uploaded to a private channel for persistent file storage

### Per-User Pricing
- Petrol price, mobil price, DA amount, and transport fee are **stored per user**, not in `.env`
- Configured via the bot's `/settings` menu — each user can have their own rates
- Hardcoded defaults apply if no custom value is set

### DOCX/PDF Report Generation
- Landscape A4 format with template variants for 3–30 entries
- All Bangla text encoded in **Bijoy** (`SutonnyMJ` font)
- Distributor names converted via **Unicode-to-Bijoy REST API** (`bijoy.converteraz.com`) — ensures accurate Bijoy output without browser overhead
- PDF conversion via **Aspose.Words for Java** (cracked JAR, no evaluation watermark)
- Reports uploaded to Telegram channel for persistent access

### All Bangla Strings in One Place
All user-facing text is externalized to `bot/text_resources.json`. Edit text without touching code.

---

## Installation

### Prerequisites
- Python 3.10+
- A Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Java 17+ (for PDF conversion via Aspose.Words)

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
pkg install python git openjdk-17
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
- Syncs MongoDB data to local JSON files on startup

### 3. Telegram Channel Setup (for DOCX/PDF storage)

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

**226 tests (1 xfailed):**
- `tests/test_calculations.py` — 61 scenarios: signed carry-forward, threshold tracking, fuel efficiency, edge cases
- `tests/test_user_mgmt.py` — 30 scenarios: user CRUD, data isolation, auth, edge cases
- `tests/playground/` — 135 scenarios: entry flow, edit/delete flow, settings, summary, report, data edge cases

> Tests always use the **file-based backend** (clears `MONGODB_URL` automatically in `conftest.py`).

---

## Deployment

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app

# Java (required for Aspose.Words JAR via JPype)
RUN apt-get update && apt-get install -y \
    fontconfig openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*

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

### Render (Recommended)

1. Push your repo to GitHub
2. Go to [dashboard.render.com](https://dashboard.render.com) → **New +** → **Web Service**
3. Connect your repo
4. The included `render.yaml` will be auto-detected (Blueprint). Or manually:
   - **Name**: `pathikbot`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python -m bot.main`
   - **Plan**: Free
5. Add Environment Variables:
   - `BOT_TOKEN` (required)
   - `MONGODB_URL` (required for persistence — use [MongoDB Atlas](https://www.mongodb.com/atlas) free tier)
   - `COMPANY_NAME`, `OFFICER_NAME`, etc.
6. Click **Deploy Web Service**

> **Note**: Render's free tier spins down after inactivity. Since the bot uses **polling** (not webhook), set a **Cron Job** (e.g., [cron-job.org](https://cron-job.org)) to ping `https://your-app.onrender.com/` every 10 minutes to keep it awake. The health check endpoint returns 200 immediately.

### Railway

1. Push repo to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. Add Environment Variables (same as Render above)
4. Set Start Command: `python -m bot.main`

### VPS (Linux)

```bash
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
pkg install tmux
tmux new -s pathikbot
cd PathikBot && source venv/bin/activate && python -m bot.main
# Detach: Ctrl+B, D   |   Reattach: tmux attach -t pathikbot
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
│   ├── audit_logger.py             # Event logging to Telegram channel
│   └── handlers/
│       ├── start.py                # /start, /help, main menu
│       ├── new_entry.py            # 20-state entry ConversationHandler
│       ├── summary.py              # /listentries (with filter UI), /summary
│       ├── settings.py             # Per-user prefs, edit/delete entries, dist mgmt
│       ├── archive.py              # /months (past records browser)
│       ├── admin.py                # Interactive /adduser, /removeuser, /users
│       └── report.py               # /generate DOCX + PDF report + channel upload
├── core/
│   ├── file_data_store.py          # User mgmt, entries CRUD, cascading odos, dispatch
│   ├── mongo_db.py                 # MongoDB async backend (motor) + sync to local
│   ├── expense_calculations.py     # Cost, summary, signed carry-forward tracking
│   └── audit_logger.py             # Log events to Telegram channel
├── docx_generator/
│   ├── __init__.py
│   ├── logsheet_generator.py       # Main generator (lxml) — populates DOCX templates
│   ├── legacy_docx_generator.py    # Alternate python-docx generator (legacy)
│   ├── docx_xml_helpers.py         # Cell formatting helpers
│   ├── bijoy_converter.py          # Unicode → Bijoy conversion (dates, venue, labels)
│   ├── bijoy_conversion_rules.py   # Bijoy mapping engine
│   ├── character_map_utils.py      # String/character utilities
│   └── web_converter.py            # REST API converter (bijoy.converteraz.com)
├── scripts/
│   ├── template_variant_generator.py
│   └── test_data_generator.py
├── data/
│   ├── users.json                  # User registry (file backend)
│   ├── distributors.json           # Shared distributor list
│   ├── entries_{user_id}.json      # Per-user entries (file backend)
│   └── user_prefs/{user_id}.json   # Per-user preferences (file backend)
├── templates/                      # Aspose-compatible DOCX templates
├── generated_logsheets/            # Logsheet template variants
│   ├── DOCX/                       #   Pre-generated DOCX templates (lxml-based)
│   └── ODT/                        #   Pre-generated ODT templates
├── outputs/                        # Generated DOCX/PDF output (legacy, now uses generated_logsheets/DOCX/ and ODT/)
├── tests/
│   ├── conftest.py                 # Forces file-based backend for tests
│   ├── test_calculations.py        # 61 calculation tests
│   ├── test_user_mgmt.py           # 30 user mgmt tests
│   └── playground/                 # 135 flow/integration tests
├── aspose-words-20.12-jdk17-cracked.jar  # Aspose.Words for Java (PDF)
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── render.yaml
├── requirements.txt
├── run.bat
└── README.md
```

---

## Tech Stack

| Component | Library |
|-----------|---------|
| Bot Framework | [`python-telegram-bot`](https://github.com/python-telegram-bot/python-telegram-bot) (async, v20.x) |
| MongoDB Driver (production) | [`motor`](https://github.com/mongodb/motor) (async) |
| MongoDB Driver (tests) | [`pymongo`](https://github.com/mongodb/mongo-python-driver) (sync) |
| DOCX Generation | `lxml` (reads/writes OpenXML directly) |
| PDF Conversion | **Aspose.Words for Java** (cracked JAR via [`jpype`](https://jpype.readthedocs.io/)) |
| Bangla Converter (distributor names) | REST API (`bijoy.converteraz.com`) via `urllib` |
| Bangla Converter (other fields) | Custom Unicode → Bijoy mapping (`bijoy_converter.py`) |
| File Storage (dev) | `aiofiles` + JSON |
| Environment | `python-dotenv` |
| Testing | `pytest` + `pytest-asyncio` |

---

## Contributing

This is a specialized tool built for a specific workflow. Feel free to fork and adapt for your needs.

---

## License

MIT
