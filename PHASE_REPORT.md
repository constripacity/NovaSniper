# NovaSniper Consolidation – Phase 1 Analysis

The repository currently contains a single implementation under `app/` and **does not include** the expected `novasniper-v2/` directory or any alternative package to merge. All observations below are therefore limited to the existing `app/` codebase.

## 1. FastAPI entrypoint and routers
- FastAPI application instance is defined in `app/main.py` as `app` with a lifespan hook that initializes the scheduler and database tables.
- Routers registered: only `app.routers.tracked_products` is included; no other routers (auth, admin, watchlists, etc.) are present.
- Additional mounts: `/static` is served via `StaticFiles`; templates are loaded from `app/templates` with `Jinja2Templates`.

## 2. Database models
- Models are defined in `app/models.py` and only contain the `TrackedProduct` table with the following columns: `id`, `platform`, `product_id`, `product_url`, `target_price`, `currency`, `current_price`, `last_checked_at`, `alert_sent`, `notify_email`, `created_at`, `updated_at`.
- There are no additional tables such as `User`, `PriceHistory`, `Watchlist`, `NotificationLog`, etc.

## 3. Services
- Price fetching (`app/services/price_fetcher.py`): provides safe placeholder logic plus an optional eBay Shopping API lookup when `EBAY_APP_ID` is configured. No Amazon API integration is present.
- Scheduler (`app/services/scheduler.py`): runs periodic price checks over tracked products and triggers notifications using the notifier.
- Notifier (`app/services/notifier.py`): sends email notifications via SMTP if settings are provided.

## 4. Features comparison
- **v1 (current):** tracked-products CRUD, scheduler-driven price checks, SMTP email alerts, optional eBay live price lookup, basic dashboard templates/static assets.
- **v2 (expected):** The repository lacks the described v2 implementation (no `novasniper-v2/` directory or equivalent). Features such as user authentication, watchlists, price history, multi-channel notifications, admin routes, Docker support, and tests are not present and therefore cannot yet be merged.

## 5. Blockers for further phases
- Because the `novasniper-v2/` source tree is absent, database migration and code merge tasks from the consolidation plan cannot proceed without the missing code and schema definitions.
- If a separate v2 codebase exists elsewhere, it needs to be added to the repository before migration/merge work can continue.
