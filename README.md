```markdown
# 🎯 NovaSniper v2.0

A production-ready, multi-platform price tracking service with real-time alerts and notifications built with FastAPI, SQLAlchemy, and APScheduler.

## Features

- Multi-platform support
  - Amazon — Product Advertising API (PA-API)
  - eBay — Shopping API
  - Walmart — Affiliate API
  - Best Buy — Products API
  - Target — Redsky API
  - Extensible architecture for adding more platforms

- Multi-channel notifications
  - Email (SMTP with HTML templates)
  - Discord (webhook embeds)
  - Telegram (Bot API)
  - Pushover
  - SMS (Twilio)
  - Slack (webhooks)
  - Custom webhooks (HMAC signing)

- Advanced capabilities
  - Price history tracking with analytics
  - Multiple alert thresholds per product
  - Watchlists and dashboards
  - User auth (JWT + API keys)
  - Rate limiting, background scheduler, and admin dashboard
  - RESTful API with OpenAPI docs

---

## Quick Start

### Prerequisites

- Python 3.11+
- pip
- (optional) Docker & docker-compose

### Local Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/constripacity/NovaSniper.git
   cd NovaSniper
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. Upgrade pip and install dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Copy environment template and edit `.env`:
   ```bash
   cp .env.example .env
   # Edit .env and fill in API keys and notification credentials
   ```

5. Start the app (development):
   ```bash
   uvicorn app.main:app --reload
   ```

6. Open in browser:
   - Dashboard: http://localhost:8000/dashboard
   - API docs: http://localhost:8000/docs
   - Health check: http://localhost:8000/health

### Docker

Build and run with docker-compose:
```bash
docker-compose up -d --build
docker-compose logs -f
```

---

## Configuration

Edit `.env` with your settings. At minimum provide one platform API key and at least one notification channel.

Example environment variables:

```env
# General
DEBUG=true
SECRET_KEY=change-me

# Database (example)
DATABASE_URL=sqlite:///./db.sqlite3

# Amazon (Product Advertising API)
AMAZON_ACCESS_KEY=your-access-key
AMAZON_SECRET_KEY=your-secret-key
AMAZON_PARTNER_TAG=your-tag-20

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

# Twilio
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=+10000000000
TWILIO_ENABLED=true
```

---

## Scheduler & Price Fetching

- Price fetchers live in `app/services/price_fetcher.py`. Each fetcher extracts product identifiers, calls the upstream API, and normalizes the response into a common `PriceResult`.
- Scheduler (e.g., APScheduler) in `app/services/scheduler.py` enqueues recurring fetch jobs, persists price history, and triggers notification tasks asynchronously so the API remains responsive.

---

## API Usage

### Authentication

Two methods are supported:
1. API Key (header): `X-API-Key: your-api-key`
2. JWT (header): `Authorization: Bearer your-jwt-token`

### Selected endpoints

```bash
# Register user
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

# Create watchlist
POST /api/v1/watchlists
{
  "name": "Holiday Wishlist",
  "is_public": true
}
```

See full API documentation at `/docs` when running the server.

---

## Architecture (overview)

Project layout (simplified):

```
novasniper/
├── app/
│   ├── main.py            # FastAPI app
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

## Platform API Setup (high level)

- Amazon PA-API: join Amazon Associates and request API access via Amazon's PA-API docs.
- eBay: create an app on eBay Developers to get an App ID.
- Walmart: register for Walmart Affiliate Program and request API keys.
- Best Buy: get API key from Best Buy Developer portal.
- Target: consult Redsky endpoints and follow their key provisioning.

Refer to provider docs for exact steps and quotas.

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

## Deployment

Production checklist:
- [ ] Set a strong SECRET_KEY
- [ ] Use PostgreSQL (or managed DB) instead of SQLite
- [ ] Configure proper CORS origins
- [ ] Set up SSL/TLS
- [ ] Configure rate limiting
- [ ] Set up monitoring/logging
- [ ] Enable Redis caching (optional)
- [ ] Run with a process manager (gunicorn/uvicorn workers) behind a reverse proxy

Example production env snippet:
```env
DEBUG=false
SECRET_KEY=<generated-secret>
DATABASE_URL=postgresql://user:pass@host:5432/novasniper
```

---

## Extending

### Add a new platform
1. Implement a fetcher (e.g., in `app/services/price_fetcher.py`) that inherits from the base fetcher and implements:
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
1. Create a notifier implementing a `send(...)` interface in `app/services/notifier.py`.
2. Add new entry to `NotificationType` enum.
3. Register notifier in the Notification service.

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
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -m "Add my feature"`
4. Push and open a pull request

Please follow existing code style and add tests for new functionality.

---

## License

MIT License — see the LICENSE file.

---

## Support

- Documentation: `/docs` when running the app
- Issue tracker: https://github.com/constripacity/NovaSniper/issues
- Discussions: https://github.com/constripacity/NovaSniper/discussions

---

Built with ❤️ using FastAPI, SQLAlchemy, and APScheduler
```
