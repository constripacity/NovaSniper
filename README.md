# NovaSniper v2.0

A production‑ready, multi‑platform price tracking service with real‑time alerts and notifications. Built with FastAPI, SQLAlchemy and APScheduler.

## Highlights

- **Multi‑platform price fetching:** Amazon, eBay, Walmart, Best Buy and Target.
- **Multi‑channel notifications:** Email, Discord, Telegram, Pushover, SMS (Twilio), Slack and webhooks.
- **User management & auth:** JWT‑based login and API keys, profile management and admin tools.
- **Watchlists & analytics:** Shareable watchlists, price history, alert thresholds and dashboards.
- **Extensible architecture:** Class‑based fetchers and notifiers make it easy to add new platforms or channels.
- **Dockerized & tested:** Comes with Dockerfile, docker‑compose and a pytest suite.

## Quick Start

### Prerequisites

- Python 3.11+
- pip
- (optional) Docker & docker‑compose

### Local development

1. **Clone the repository:**

   ```bash
   git clone https://github.com/constripacity/NovaSniper.git
   cd NovaSniper
   ```

2. **Create and activate a virtual environment (optional but recommended):**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\\Scripts\\activate`
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Copy the example environment file and configure variables:**

   ```bash
   cp .env.example .env
   ```

   Open `.env` and fill in your API keys (Amazon, eBay, Walmart, Best Buy, Target) and notification credentials (SMTP, Discord, Telegram, Pushover, Twilio, Slack). Set `SECRET_KEY` to a strong random value.

5. **Run the application:**

   ```bash
   uvicorn app.main:app --reload
   ```

   The API will be available at `http://localhost:8000`. Open `http://localhost:8000/docs` for interactive API docs.

### Docker

You can run NovaSniper entirely in containers:

```bash
docker-compose up --build
```

The application will expose port 8000 (configured via `docker-compose.yml`). Environment variables can be set in an `.env` file or passed through the compose file.

## Project Structure

```
NovaSniper/
├── app/                    # Main application package
│   ├── __init__.py
│   ├── main.py            # FastAPI app and router registration
│   ├── config.py          # Pydantic settings
│   ├── database.py        # Database session and engine
│   ├── models.py          # SQLAlchemy models and enums
│   ├── schemas.py         # Pydantic schemas
│   ├── routers/           # API routers (auth, tracked_products, watchlists, notifications, webhooks, admin)
│   ├── services/          # Business logic (price fetchers, notifiers, scheduler)
│   ├── utils/             # Utilities (authentication helpers)
│   ├── templates/         # Jinja2 templates for dashboard pages
│   └── static/            # Static assets (CSS/JS)
├── tests/                 # Pytest test suite
├── .env.example           # Sample environment configuration
├── Dockerfile             # Container build file
├── docker-compose.yml     # Docker compose setup
├── requirements.txt       # Python dependencies
├── pytest.ini             # Test configuration
└── README.md              # Project documentation
```

## Configuration

Environment variables are loaded via [Pydantic Settings](app/config.py). Copy `.env.example` to `.env` and provide values for the following (all keys shown as placeholders):

- **Database:** `DATABASE_URL` (default uses SQLite).
- **Scheduler:** `CHECK_INTERVAL_SECONDS` (how often to check prices).
- **Amazon Product Advertising API:** `AMAZON_ACCESS_KEY`, `AMAZON_SECRET_KEY`, `AMAZON_PARTNER_TAG`.
- **eBay API:** `EBAY_APP_ID`.
- **Walmart API:** `WALMART_CLIENT_ID`, `WALMART_CLIENT_SECRET`.
- **Best Buy API:** `BESTBUY_API_KEY`.
- **Target API:** `TARGET_API_KEY`.
- **SMTP Email:** `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL`.
- **Discord:** `DISCORD_WEBHOOK_URL`, `DISCORD_ENABLED`.
- **Telegram:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ENABLED`.
- **Pushover:** `PUSHOVER_APP_TOKEN`, `PUSHOVER_ENABLED`.
- **Twilio SMS:** `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `TWILIO_ENABLED`.
- **Slack:** `SLACK_WEBHOOK_URL`, `SLACK_ENABLED`.
- **Secret key:** `SECRET_KEY` for JWT signing.

## Running Tests

To run the test suite with coverage:

```bash
pytest --cov=app -q
```

## Extending NovaSniper

- **Add a new platform:** Implement a new subclass of `BasePriceFetcher` in `app/services/price_fetcher.py` and register it in `PriceFetcherService`.
- **Add a new notification channel:** Create a subclass of `BaseNotifier` in `app/services/notifier.py` and register it in `NotificationService`.
- **Customize scheduler:** Modify `app/services/scheduler.py` to change how often background jobs run.

---

Released under the MIT License. Contributions are welcome!
