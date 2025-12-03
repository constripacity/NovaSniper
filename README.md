# 🎯 NovaSniper v2.0

A production-ready, multi-platform price tracking service with real-time alerts and notifications.

## Features

### 🛒 Multi-Platform Support
- **Amazon** — Product Advertising API v5.0
- **eBay** — Shopping API
- **Walmart** — Affiliate API
- **Best Buy** — Products API
- **Target** — Redsky API
- Extensible architecture for adding more platforms

### 🔔 Multi-Channel Notifications
- **Email** — SMTP with HTML templates
- **Discord** — Webhook embeds
- **Telegram** — Bot API
- **Pushover** — Push notifications
- **SMS** — Twilio integration
- **Slack** — Webhook blocks
- **Webhooks** — Custom integrations with HMAC signing

### 📊 Advanced Features
- Price history tracking with analytics
- Multiple alert thresholds per product
- Watchlists for organizing products
- User authentication (JWT + API keys)
- Rate limiting
- Admin dashboard
- RESTful API with OpenAPI docs
- Background scheduler for recurring price checks

## Quick Start

### Prerequisites
- Python 3.11+
- pip

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/novasniper.git
   cd novasniper
   ```
2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```
3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
4. **Copy the environment template**
   ```bash
   cp .env.example .env
   ```
5. **Run the application**
   ```bash
   uvicorn app.main:app --reload
   ```

Visit:
- **Dashboard**: http://localhost:8000/dashboard
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### Docker

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f
```

## Configuration

Edit `.env` with your settings.

### Required for Live Prices
Provide at least one platform API key:

```env
# Amazon (most common)
AMAZON_ACCESS_KEY=your-access-key
AMAZON_SECRET_KEY=your-secret-key
AMAZON_PARTNER_TAG=your-tag-20

# eBay
EBAY_APP_ID=your-app-id
```

### For Notifications

```env
# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=app-password
FROM_EMAIL=your@gmail.com

# Discord (easiest)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_ENABLED=true
```

## Scheduler & Price Fetching

- **Price fetching**: Each platform-specific fetcher in `app/services/price_fetcher.py` extracts product IDs, calls the upstream API, and normalizes prices into a unified `PriceResult`.
- **Scheduler**: APScheduler jobs in `app/services/scheduler.py` periodically trigger fetchers, persist price history, and enqueue notification tasks so alerts are delivered without blocking API requests.

## API Usage

### Authentication

Two methods available:
1. **API Key** (header): `X-API-Key: your-api-key`
2. **JWT Token** (header): `Authorization: Bearer your-token`

### Endpoints

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

# List products
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

See full API documentation at `/docs` when running.

## Architecture

```
novasniper/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration settings
│   ├── database.py          # Database setup
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── routers/
│   │   ├── auth.py          # Authentication endpoints
│   │   ├── tracked_products.py
│   │   ├── watchlists.py
│   │   ├── notifications.py
│   │   ├── webhooks.py
│   │   └── admin.py
│   ├── services/
│   │   ├── price_fetcher.py # Multi-platform fetchers
│   │   ├── notifier.py      # Notification channels
│   │   └── scheduler.py     # Background jobs
│   ├── static/              # Static assets (dashboard)
│   ├── templates/           # HTML templates
│   └── utils/
│       └── auth.py          # Auth utilities
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Database Models

```
User
├── TrackedProduct (many)
│   ├── PriceHistory (many)
│   └── Alert (many)
├── Watchlist (many)
│   └── WatchlistItem (many)
├── NotificationSetting (many)
└── OutboundWebhook (many)
```

## Platform API Setup

### Amazon Product Advertising API
1. Join [Amazon Associates](https://affiliate-program.amazon.com/)
2. Request [Product Advertising API](https://webservices.amazon.com/paapi5/documentation/) access
3. Generate access keys in your Associates account

### eBay Shopping API
1. Create account at [eBay Developers](https://developer.ebay.com/)
2. Create an application to get App ID

### Walmart Affiliate API
1. Join [Walmart Affiliate Program](https://affiliates.walmart.com/)
2. Request API access at [Walmart Developer](https://developer.walmart.com/)

### Best Buy Products API
1. Register at [Best Buy Developer](https://developer.bestbuy.com/)
2. Get API key (free tier available)

## Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_tracked_products.py -v
```

## Deployment

### Production Checklist
- [ ] Set strong `SECRET_KEY`
- [ ] Use PostgreSQL instead of SQLite
- [ ] Configure proper CORS origins
- [ ] Set up SSL/TLS
- [ ] Configure rate limits
- [ ] Set up monitoring/logging
- [ ] Enable Redis caching (optional)

### Environment Variables
```env
DEBUG=false
SECRET_KEY=<generated-with-openssl-rand-hex-32>
DATABASE_URL=postgresql://user:pass@host:5432/novasniper
```

## Extending

### Adding a New Platform

1. Create fetcher class in `app/services/price_fetcher.py`:

```python
class NewPlatformFetcher(BasePriceFetcher):
    def is_configured(self) -> bool:
        return bool(settings.NEW_PLATFORM_API_KEY)

    def extract_product_id(self, url_or_id: str) -> Optional[str]:
        # Extract ID from URL
        pass

    async def fetch_price(self, product_id: str) -> PriceResult:
        # Fetch from API
        pass
```

2. Add to `Platform` enum in `models.py`
3. Register in `PriceFetcherService`

### Adding a New Notification Channel

1. Create notifier class in `app/services/notifier.py`:

```python
class NewChannelNotifier(BaseNotifier):
    def is_configured(self) -> bool:
        pass

    async def send(self, recipient, subject, message, product=None) -> NotificationResult:
        pass
```

2. Add to `NotificationType` enum
3. Register in `NotificationService`

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

MIT License - see LICENSE file

## Support

- 📖 [Documentation](/docs)
- 🐛 [Issue Tracker](https://github.com/your-username/novasniper/issues)
- 💬 [Discussions](https://github.com/your-username/novasniper/discussions)

---

Built with ❤️ using FastAPI, SQLAlchemy, and APScheduler
