                                                                           
### Telegram-Based Record Store Manager

## About

A standalone Telegram bot to manage your **vinyl record store** — inventory, Discogs-powered additions, multi-item cart-based sales, and Excel report generation — all from your phone or desktop via Telegram.

---

## Features

- 🔎 `/inventory` — View current vinyl stock  
- ➕ `/add` — Add vinyls via Discogs search (with formats, condition, pricing)  
- 🛒 `/sell` — Add multiple vinyls to a cart and register sale (cash/POS)  
- 📊 `/report` — Generate and receive a daily Excel report with payment breakdown  

---

## Tech Stack

- Python 3.9+
- `python-telegram-bot` v20+
- `discogs-client`
- `openpyxl`

---

## Getting Started

### 1. Clone & install

```bash
git clone https://github.com/amstrd-cpc/record-store-bot.git
cd record-store-bot
pip install -r requirements.txt
```

2. Set up your Bot Token
Create a .env file:

```bash

BOT_TOKEN=123456:ABC-your-telegram-token
DISCOGS_TOKEN=your_discogs_token
```
3. Run the Bot
```bash
python bot.py
```


🗃 Folder Structure
```bash

record-store-bot/
├── bot.py               # Main bot logic
├── add_record.py        # /add command logic with Discogs
├── sales.py             # /sell with cart and payment
├── reports.py           # /report generation and sending
├── inventory.py         # Inventory loader
├── clime_db.xlsx        # Your Excel-based inventory
├── sales/               # Auto-generated sales reports
├── requirements.txt
└── .env                 # Your Telegram bot token
```

🏗 Deployment Options
✅ Run locally
✅ Host on Railway, Render, or Heroku

Start command:

```bash
pip install -r requirements.txt && python bot.py
```

🧠 Credits
Discogs API via discogs-client
Telegram Bot by python-telegram-bot

🖖 Contributing
PRs welcome. Want a web UI, analytics, or cloud inventory? Open an issue and let's build!

📜 License
MIT — use freely, credit appreciated 🎧






