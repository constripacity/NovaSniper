# 🎯 NovaSniper v2.0

Multi-platform price tracking service with real-time alerts.

## Features
- Multi-platform: Amazon, eBay, Walmart, Best Buy, Target
- Multi-channel notifications: Email, Discord, Telegram, SMS, Slack, Webhooks
- User authentication (JWT + API keys)
- Price history tracking
- Watchlists
- Admin dashboard
- Docker support

## Quick Start
```bash
git clone https://github.com/constripacity/NovaSniper.git
cd NovaSniper
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Visit http://localhost:8000/dashboard

## API Docs
http://localhost:8000/docs
# NovaSniper Price Tracker

A minimal, ToS-friendly price tracking service for Amazon and eBay built with FastAPI. The app tracks products, checks prices on a schedule, and emails you when your target price is reached. It is designed to use official APIs and intentionally avoids any anti-bot circumvention.

## Features
- FastAPI backend with endpoints to create, list, and delete tracked products
- SQLite persistence with SQLAlchemy
- Background scheduler to refresh prices at a configurable interval
- Email notifications via SMTP when targets are met
- Clear placeholders for Amazon Product Advertising API and an **eBay Shopping API integration** that works when `EBAY_APP_ID` is set
- Clear placeholders for Amazon Product Advertising API and eBay API integrations

## Safety and compliance
- No CAPTCHA bypassing or anti-bot evasion
- No automated checkout or human-behavior simulation
- Built to use official APIs; placeholder logic should be replaced with compliant API calls

## Project structure
```
app/
  main.py                # FastAPI app & lifecycle hooks
  config.py              # Environment-driven settings
  database.py            # SQLAlchemy engine/session
  models.py              # ORM models
  schemas.py             # Pydantic schemas
  routers/
    tracked_products.py  # CRUD endpoints for tracked products
  services/
    price_fetcher.py     # Safe placeholder price fetching logic
    scheduler.py         # APScheduler-based background checks
    notifier.py          # Email notifications
.env.example             # Sample environment configuration
requirements.txt         # Python dependencies
README.md               
```

## Installation
1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\\Scripts\\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your values (database path, scheduler interval, SMTP credentials, and API keys). If you
   provide `EBAY_APP_ID`, live eBay price checks will be used; otherwise a safe placeholder price is generated.
3. Copy `.env.example` to `.env` and fill in your values (database path, scheduler interval, SMTP credentials, and API keys).

## Configuration
Key environment variables:
- `DATABASE_URL` – SQLite URL (default `sqlite:///./tracked_products.db`)
- `CHECK_INTERVAL_SECONDS` – How often to run price checks
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL` – SMTP settings for email alerts
- `AMAZON_ACCESS_KEY`, `AMAZON_SECRET_KEY`, `AMAZON_PARTNER_TAG` – Amazon Product Advertising API
- `EBAY_APP_ID` – eBay API application key (enables live eBay price fetching via Shopping API)
- `EBAY_APP_ID` – eBay API application key

## Running the app
Start the FastAPI server:
```bash
uvicorn app.main:app --reload
```
FastAPI will create the SQLite tables on startup and initialize the scheduler to run every `CHECK_INTERVAL_SECONDS`.

## Beginner-friendly Quick Start (Windows, no Git)
1. **Install Python** from [python.org/downloads](https://www.python.org/downloads/). During setup, check the box **"Add Python to PATH."**
2. **Download the project ZIP (no Git needed):**
   - Open the repository page in your browser.
   - Click the green **Code** button → **Download ZIP**.
   - Extract the ZIP to a folder such as `C:\\NovaSniper`.
3. **Open Command Prompt inside the project folder:**
   - In File Explorer, open `C:\\NovaSniper`.
   - Click the address bar, type `cmd`, and press **Enter** to open Command Prompt here.
1. **Install Python** from [python.org/downloads](https://www.python.org/downloads/) and check "Add Python to PATH" during setup.
2. **Download the project ZIP:**
   - Visit the repository page and click the green **Code** button → **Download ZIP**.
   - Extract the ZIP to a folder such as `C:\\NovaSniper`.
3. **Open Command Prompt in the project folder:**
   - In File Explorer, open the extracted folder.
   - Click the address bar, type `cmd`, and press Enter.
4. **Create a virtual environment and activate it:**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
5. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
6. **Create your `.env` file (copy-paste configuration):**
   - Copy `.env.example` (in the project root) to `.env`.
   - Keep the default SQLite path if you're unsure.
   - Optionally add SMTP credentials and `EBAY_APP_ID` to enable live email alerts and real eBay price lookups.
6. **Create your `.env` file:**
   - Copy `.env.example` (in the project root) to `.env`.
   - You can keep the default SQLite path; optionally add SMTP and API keys for full functionality.
7. **Start the app:**
   ```bash
   uvicorn app.main:app --reload
   ```
8. **Open NovaSniper in your browser:**
   - Dashboard UI: http://127.0.0.1:8000/
8. **Open in your browser:**
   - Dashboard: http://127.0.0.1:8000/
   - API docs: http://127.0.0.1:8000/docs

### Mac/Linux notes
- Use `python3 -m venv venv` and `source venv/bin/activate` to create/activate the virtual environment.
- The rest of the commands are the same (replace `python` with `python3` if needed).

## Web dashboard
- Visit `http://localhost:8000/` to open the NovaSniper dashboard.
- Add products via the form (platform, URL/ID, target price, currency, notify email).
- View existing tracked products in the table, delete entries, or trigger a manual "Check Now" refresh for a single item.
- The dashboard is a thin layer over the same JSON API, so `/docs` remains available for API exploration.

## API usage
### Add a product to tracking
```bash
curl -X POST http://localhost:8000/tracked-products \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "amazon",
    "product_id": "https://www.amazon.com/dp/B000000000",
    "target_price": 99.99,
    "currency": "USD",
    "notify_email": "you@example.com"
  }'
```

### List tracked products
```bash
curl http://localhost:8000/tracked-products
```

### Remove a tracked product
```bash
curl -X DELETE http://localhost:8000/tracked-products/1
```

## Scheduler
An APScheduler job runs every `CHECK_INTERVAL_SECONDS` seconds. For each tracked product it:
1. Fetches the current price using the platform-specific logic (live eBay Shopping API when `EBAY_APP_ID` is configured; otherwise a safe placeholder).
2. Updates the record with the latest price and timestamp.
3. Sends an email alert once when the current price is at or below the target.

## Price fetching
`app/services/price_fetcher.py` contains:
- URL/ID extraction helpers for Amazon and eBay
- A live **eBay Shopping API** lookup when `EBAY_APP_ID` is available
- A safe placeholder price generator for Amazon (and as a fallback)

To extend pricing:
- Replace Amazon logic with Product Advertising API calls (SearchItems/GetItems)
- Swap the placeholder logic for other platforms while respecting each ToS
1. Fetches the current price using the platform-specific logic (placeholder now; replace with official API calls).
2. Updates the record with the latest price and timestamp.
3. Sends an email alert once when the current price is at or below the target.

## Extending price fetching
`app/services/price_fetcher.py` contains extraction helpers and a placeholder price generator. Replace `get_current_price` with calls to:
- **Amazon Product Advertising API** (SearchItems/GetItems)
- **eBay Browse or Finding APIs**
Make sure to follow platform Terms of Service and keep requests light.

## Disclaimer
This project is intended for personal price tracking. It uses (or should use) official APIs and avoids any techniques that bypass website protections or automate purchases.
