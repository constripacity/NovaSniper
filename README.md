```markdown
# 🎯 NovaSniper v2.0

A production-ready, multi-platform price tracking service with real-time alerts and notifications. Built with FastAPI, SQLAlchemy, and APScheduler.

---

## Highlights

- Multi-platform price fetching (Amazon, eBay, Walmart, Best Buy, Target)
- Multi-channel notifications (Email, Discord, Telegram, Pushover, SMS, Slack, Webhooks)
- Price history, watchlists, alert thresholds, and dashboards
- RESTful API with OpenAPI docs, JWT & API key auth
- Extensible fetcher & notifier architecture

---

```markdown
## Quick Start

### Prerequisites
- Python 3.11+
- pip
- (optional) Docker & docker-compose

### Local (development)

1. Clone the repository:
   ```bash
   git clone https://github.com/constripacity/NovaSniper.git
   cd NovaSniper
   ```

2. Create and activate a virtual environment:

   - macOS / Linux:
     ```bash
     python -m venv venv
     source venv/bin/activate
     ```

   - Windows (PowerShell):
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```

   - Windows (Command Prompt):
     ```cmd
     python -m venv venv
     .\venv\Scripts\activate
     ```

3. Upgrade pip and install dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Copy the environment template and edit `.env`:
   ```bash
   # macOS / Linux
   cp .env.example .env

   # Windows (Command Prompt)
   copy .env.example .env

   # Windows (PowerShell)
   Copy-Item .env.example .env
   ```
   Then open `.env` and fill in your API keys and notification credentials.

5. Run the development server:
   ```bash
   uvicorn app.main:app --reload
   ```

6. Open the app in your browser:
- Dashboard: http://localhost:8000/dashboard
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Docker

Build and run:
```bash
docker-compose up -d --build
docker-compose logs -f
```

Notes:
- If you're working from a fork, clone your fork URL instead of the main repo URL.
- On Windows, use PowerShell or WSL for the cleanest experience with the shown commands.
```
---

## Configuration

Edit `.env` to provide platform API credentials and notification settings. At minimum, add one platform API key and at least one notification channel.

Example `.env` entries

```env
# General
DEBUG=true
SECRET_KEY=change-me
DATABASE_URL=sqlite:///./db.sqlite3

# Amazon (Product Advertising API)
AMAZON_ACCESS_KEY=your-access-key
AMAZON_SECRET_KEY=your-secret-key
AMAZON_PARTNER_TAG=your-partner-tag-20

# eBay
EBAY_APP_ID=your-app-id

# Walmart
WALMART_CLIENT_ID=your-client-id
WALMART_CLIENT_SECRET=your-client-secret

# Best Buy
BESTBUY_API_KEY=your-api-key

# Target
TARGET_API_KEY=your-api-key

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=app-password
FROM_EMAIL=your@gmail.com

# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_ENABLED=true

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ENABLED=true

# Twilio (SMS)
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=+10000000000
TWILIO_ENABLED=true
```

---

## Scheduler & Price Fetching

- Platform-specific fetchers are implemented under `app/services/price_fetcher.py`. They extract product IDs, call provider APIs, and normalize results into a common `PriceResult`.
- A scheduler (e.g., APScheduler) in `app/services/scheduler.py` enqueues recurring price checks, persists history, and dispatches notifications asynchronously to avoid blocking the API.

---

## API Usage

### Authentication

Supported methods:
- API Key: send header `X-API-Key: your-api-key`
- JWT: send header `Authorization: Bearer <token>`

### Example endpoints

```bash
# Register a user
POST /api/v1/auth/register
{
  "email": "user@example.com",
  "password": "securepassword123"
}

# Login (get JWT)
POST /api/v1/auth/login
{
  "email": "user@example.com",
  "password": "securepassword123"
}

# Track a product
POST /api/v1/tracked-products
{
  "platform": "amazon",
  "product_id": "https://amazon.com/dp/B08N5WRWNW",
  "target_price": 79.99,
  "notify_email": "user@example.com"
}

# List tracked products
GET /api/v1/tracked-products

# Get price history
GET /api/v1/tracked-products/{id}/history
```

Full interactive API docs are available at `/docs` when the server is running.

---

## Project Structure (overview)

```
novasniper/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── tracked_products.py
│   │   ├── watchlists.py
│   │   ├── notifications.py
│   │   ├── webhooks.py
│   │   └── admin.py
│   ├── services/
│   │   ├── price_fetcher.py
│   │   ├── notifier.py
│   │   └── scheduler.py
│   ├── templates/
│   └── static/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

Database model summary:

- User
  - TrackedProduct (many)
    - PriceHistory (many)
    - Alert (many)
  - Watchlist (many)
    - WatchlistItem (many)
  - NotificationSetting (many)
  - OutboundWebhook (many)

---

## Platform API Setup (brief)

- Amazon PA-API: join Amazon Associates and request Product Advertising API access
- eBay: register an app at eBay Developers to obtain App ID
- Walmart: register for Walmart Affiliate Program and request API access
- Best Buy: obtain API key via Best Buy Developer portal
- Target: consult Redsky endpoints and follow key provisioning steps

Refer to provider documentation for full setup and quotas.

---

## Running Tests

Run all tests:
```bash
pytest
```

With coverage:
```bash
pytest --cov=app --cov-report=html
```

Run a single test file:
```bash
pytest tests/test_tracked_products.py -v
```

---

## Deployment / Production Checklist

- [ ] Set a strong SECRET_KEY
- [ ] Use PostgreSQL or a managed database (avoid SQLite in production)
- [ ] Configure CORS and secure origins
- [ ] Use SSL/TLS (HTTPS)
- [ ] Configure rate limiting
- [ ] Set up monitoring and centralized logging
- [ ] Consider Redis for caching / task queues
- [ ] Run with a process manager (gunicorn/uvicorn workers) behind a reverse proxy

Example production env snippet:
```env
DEBUG=false
SECRET_KEY=<generated-secret>
DATABASE_URL=postgresql://user:pass@host:5432/novasniper
```

---

## Extending

### Add a new platform fetcher
1. Implement a fetcher class (e.g., in `app/services/price_fetcher.py`) inheriting from the base fetcher and implement:
   - `is_configured(self) -> bool`
   - `extract_product_id(self, url_or_id: str) -> Optional[str]`
   - `async def fetch_price(self, product_id: str) -> PriceResult`
2. Add the platform to the `Platform` enum in `models.py`.
3. Register the fetcher in the PriceFetcher service.

Example skeleton:

```python
class NewPlatformFetcher(BasePriceFetcher):
    def is_configured(self) -> bool:
        return bool(settings.NEW_PLATFORM_API_KEY)

    def extract_product_id(self, url_or_id: str) -> Optional[str]:
        # parse URL or id
        pass

    async def fetch_price(self, product_id: str) -> PriceResult:
        # call API and normalize response
        pass
```

### Add a new notification channel
1. Create a notifier class in `app/services/notifier.py` implementing `is_configured()` and `send(...)`.
2. Add a `NotificationType` enum entry.
3. Register the notifier in the Notification service.

Example skeleton:

```python
class NewChannelNotifier(BaseNotifier):
    def is_configured(self) -> bool:
        return bool(settings.NEW_CHANNEL_API_KEY)

    async def send(self, recipient, subject, message, product=None) -> NotificationResult:
        # send notification
        pass
```

---

## Contributing

1. Fork the repository
2. Create a feature branch:
   ```bash
   git checkout -b feature/my-feature
   ```
3. Commit and push your changes:
   ```bash
   git commit -m "Add feature"
   git push origin feature/my-feature
   ```
4. Open a Pull Request for review

Please follow existing style and add tests for new functionality.

---

## License

MIT License — see the LICENSE file.

---

## Support

- Documentation (local): `/docs` when running the server
- Issues: https://github.com/constripacity/NovaSniper/issues
- Discussions: https://github.com/constripacity/NovaSniper/discussions

Built with ❤️ using FastAPI, SQLAlchemy, and APScheduler
```
