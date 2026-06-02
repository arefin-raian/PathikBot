# 🏍️ PathikBot — Motorcycle Logsheet Automation System

A **Telegram bot** for Territory Marketing Officers to track daily field visit expenses and auto-generate monthly **DOCX logsheet reports** in Bijoy-encoded Bangla (SutonnyMJ font).

---

## ✨ Features

### 📱 Telegram Bot (Bangla UI)
- **`/newentry`** — Step-by-step guided entry flow: date → type → odometer → distance → fuel → DA → manager → distributor selection
- **`/listentries`** — View all entries for the current or any past month
- **`/summary`** — Aggregated monthly statistics (total tours, km, fuel cost, DA, etc.)
- **`/editentry` / `/delentry`** — Modify or delete existing entries with automatic cascading odometer recalculation
- **`/months`** — Browse and manage records from previous months
- **`/settings`** — Configure petrol price, mobil price, DA rate, transport fee, and manage distributor list
- **`/generate`** — Generate a formatted `.docx` logsheet report

### 🧮 Smart Calculations
- Distance: supports expressions like `14+15` or `2*30+5`
- Petrol cost: `liters × price_per_liter` (auto-calculated)
- Mobil cost: `liters × price_per_liter` (auto-calculated)
- Total cost varies by entry type (Regular Tour vs Monthly Meeting)
- **Cascading odometers**: editing/deleting an entry auto-updates all subsequent entries' readings

### 📄 DOCX Report Generation
- Landscape A4 format with 4 page types:
  - **Type 1** — Header + first 3 entries
  - **Type 2** — Middle pages (4 entries each)
  - **Type 3** — Last entries + totals row
  - **Type 4** — Summary statistics
- All Bangla text encoded in **Bijoy** (`SutonnyMJ` font)
- Uses a customizable DOCX template

### 🗄️ Data Storage
- JSON-based storage (`data/entries.json`, `data/distributors.json`)
- Async file I/O with `aiofiles`
- Distributor management with add/remove UI

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- A Telegram Bot Token (from [@BotFather](https://t.me/botfather))

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/PathikBot.git
cd PathikBot

# Install dependencies
pip install -r requirements.txt
```

### Configuration

1. Copy `.env` and fill in your values:

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

## 📁 Project Structure

```
PathikBot/
├── bot/                        # Telegram Bot layer
│   ├── main.py                 # Entry point, command registration
│   ├── keyboards.py            # Inline keyboards (Bangla)
│   └── handlers/
│       ├── start.py            # /start, /help, main menu
│       ├── new_entry.py        # 19-state entry ConversationHandler
│       ├── report.py           # /generate DOCX report
│       ├── summary.py          # /listentries, /summary
│       ├── settings.py         # /settings, /editentry, /delentry, dist mgmt
│       └── archive.py          # /months (past records browser)
├── core/
│   ├── calculations.py         # Business logic (km, cost, summary)
│   └── database.py             # Async JSON CRUD with cascading odometers
├── docx_generator/
│   ├── generator.py            # LogsheetGenerator (table cloning, data filling)
│   ├── xml_utils.py            # Cell text formatting (SutonnyMJ font)
│   └── bijoy_converter.py      # Unicode → Bijoy encoding converter
├── data/
│   ├── entries.json            # All tour entries
│   └── distributors.json       # Distributor list
├── templates/                  # DOCX templates
├── output/                     # Generated reports
└── .env                        # Configuration
```

---

## 🧰 Tech Stack

| Component | Library |
|-----------|---------|
| Bot Framework | `python-telegram-bot` (async, v20.x) |
| Document Generation | `python-docx` + custom XML |
| Bangla Encoding | Custom Unicode → Bijoy converter |
| Data Storage | JSON (via `aiofiles`) |
| Environment | `python-dotenv` |

---

## 🤝 Contributing

This is a specialized tool built for a specific workflow. Feel free to fork and adapt for your needs.

---

## 📝 License

MIT
