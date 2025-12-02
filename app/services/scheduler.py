from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from app import models
from app.config import Settings
from app.database import SessionLocal
from app.services import price_fetcher
from app.services.notifier import EmailNotifier

logger = logging.getLogger(__name__)


class PriceCheckScheduler:
    def __init__(self, settings: Settings, notifier: EmailNotifier) -> None:
        self.settings = settings
        self.notifier = notifier
        self.scheduler = AsyncIOScheduler()

    def start(self) -> None:
        logger.info("Starting price check scheduler with interval %s seconds", self.settings.check_interval_seconds)
        self.scheduler.add_job(self.run_checks, "interval", seconds=self.settings.check_interval_seconds)
        self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler.running:
            logger.info("Shutting down scheduler")
            self.scheduler.shutdown(wait=False)

    def run_checks(self) -> None:
        logger.info("Running scheduled price checks")
        db: Session = SessionLocal()
        try:
            products = db.query(models.TrackedProduct).all()
            for product in products:
                price, currency = price_fetcher.get_current_price(product.platform, product.product_id)
                product.current_price = price
                product.last_checked_at = datetime.utcnow()

                if price is not None and product.target_price >= price and not product.alert_sent:
                    product_title = f"{product.platform.title()} item {product.product_id}"
                    self.notifier.send_price_alert(
                        to_email=product.notify_email,
                        product_title=product_title,
                        platform=product.platform,
                        current_price=price,
                        currency=currency or product.currency,
                        product_url=product.product_url,
                    )
                    product.alert_sent = True

            db.commit()
        except Exception:  # pragma: no cover - logging unexpected errors
            logger.exception("Error while running price checks")
            db.rollback()
        finally:
            db.close()
