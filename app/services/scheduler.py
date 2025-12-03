"""
NovaSniper v2.0 Scheduler Service
Background price checking with APScheduler
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db_context
from app.models import (
    TrackedProduct, PriceHistory, Alert, AlertStatus, 
    NotificationSetting, NotificationLog, NotificationType, SystemStats
)
from app.services.price_fetcher import price_fetcher_service, PriceResult
from app.services.notifier import notification_service

logger = logging.getLogger(__name__)


class SchedulerService:
    """Background job scheduler for price checking"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._is_running = False
        self._current_job_count = 0
        self._stats = {
            "checks_today": 0,
            "alerts_triggered_today": 0,
            "errors_today": 0,
            "last_check": None,
        }
    
    def start(self):
        """Start the scheduler"""
        if self._is_running:
            return
        
        # Main price check job
        self.scheduler.add_job(
            self._check_all_prices,
            IntervalTrigger(seconds=settings.CHECK_INTERVAL_SECONDS),
            id="price_check",
            name="Price Check",
            replace_existing=True,
            max_instances=1,
        )
        
        # Daily stats aggregation
        self.scheduler.add_job(
            self._aggregate_daily_stats,
            CronTrigger(hour=0, minute=5),
            id="daily_stats",
            name="Daily Stats Aggregation",
            replace_existing=True,
        )
        
        # Cleanup old price history (keep 90 days)
        self.scheduler.add_job(
            self._cleanup_old_history,
            CronTrigger(hour=3, minute=0),
            id="cleanup_history",
            name="Cleanup Old History",
            replace_existing=True,
        )
        
        self.scheduler.start()
        self._is_running = True
        logger.info(f"Scheduler started with {settings.CHECK_INTERVAL_SECONDS}s interval")
    
    def stop(self):
        """Stop the scheduler"""
        if not self._is_running:
            return
        
        self.scheduler.shutdown(wait=True)
        self._is_running = False
        logger.info("Scheduler stopped")
    
    def is_running(self) -> bool:
        return self._is_running
    
    def get_stats(self) -> dict:
        return {
            **self._stats,
            "is_running": self._is_running,
            "scheduled_jobs": len(self.scheduler.get_jobs()) if self._is_running else 0,
        }
    
    async def check_single_product(self, product_id: int) -> Optional[PriceResult]:
        """Manually trigger price check for a single product"""
        with get_db_context() as db:
            product = db.query(TrackedProduct).filter(TrackedProduct.id == product_id).first()
            if not product:
                return None
            
            return await self._check_product(db, product)
    
    async def _check_all_prices(self):
        """Check prices for all active tracked products"""
        logger.info("Starting scheduled price check")
        start_time = datetime.utcnow()
        
        with get_db_context() as db:
            # Get all active products
            products = db.query(TrackedProduct).filter(
                TrackedProduct.is_active == True,
                TrackedProduct.alert_status != AlertStatus.TRIGGERED,
            ).all()
            
            logger.info(f"Checking {len(products)} products")
            
            # Process in batches to respect rate limits
            batch_size = settings.MAX_CONCURRENT_CHECKS
            for i in range(0, len(products), batch_size):
                batch = products[i:i + batch_size]
                tasks = [self._check_product(db, product) for product in batch]
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # Small delay between batches
                if i + batch_size < len(products):
                    await asyncio.sleep(1)
            
            db.commit()
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        self._stats["last_check"] = datetime.utcnow()
        logger.info(f"Price check completed in {duration:.2f}s")
    
    async def _check_product(self, db: Session, product: TrackedProduct) -> Optional[PriceResult]:
        """Check price for a single product and update database"""
        try:
            result = await price_fetcher_service.fetch_price(product.platform, product.product_id)
            
            if result.success and result.price is not None:
                # Update product
                product.current_price = result.price
                product.last_checked = datetime.utcnow()
                product.check_count += 1
                product.last_error = None
                product.consecutive_errors = 0
                
                # Update metadata if available
                if result.title and not product.title:
                    product.title = result.title
                if result.image_url and not product.image_url:
                    product.image_url = result.image_url
                if result.product_url and not product.product_url:
                    product.product_url = result.product_url
                if result.brand and not product.brand:
                    product.brand = result.brand
                if result.category and not product.category:
                    product.category = result.category
                if result.original_price:
                    product.original_price = result.original_price
                
                # Track lowest/highest
                if product.lowest_price is None or result.price < product.lowest_price:
                    product.lowest_price = result.price
                if product.highest_price is None or result.price > product.highest_price:
                    product.highest_price = result.price
                
                # Add to price history
                history = PriceHistory(
                    product_id=product.id,
                    price=result.price,
                    currency=result.currency,
                    availability=result.availability,
                    seller=result.seller,
                )
                db.add(history)
                
                # Check if alert should trigger
                await self._check_alert_conditions(db, product, result)
                
                self._stats["checks_today"] += 1
                
            else:
                # Handle error
                product.last_error = result.error or "Unknown error"
                product.consecutive_errors += 1
                product.last_checked = datetime.utcnow()
                
                # Disable after too many consecutive errors
                if product.consecutive_errors >= 10:
                    product.is_active = False
                    logger.warning(f"Disabled product {product.id} after {product.consecutive_errors} errors")
                
                self._stats["errors_today"] += 1
            
            return result
            
        except Exception as e:
            logger.exception(f"Error checking product {product.id}")
            product.last_error = str(e)
            product.consecutive_errors += 1
            self._stats["errors_today"] += 1
            return None
    
    async def _check_alert_conditions(self, db: Session, product: TrackedProduct, result: PriceResult):
        """Check if price meets alert conditions and send notifications"""
        if result.price is None:
            return
        
        # Check main target price
        if result.price <= product.target_price and product.alert_status == AlertStatus.PENDING:
            product.alert_status = AlertStatus.TRIGGERED
            product.alert_triggered_at = datetime.utcnow()
            
            # Send notifications
            await self._send_price_alert(db, product)
            
            self._stats["alerts_triggered_today"] += 1
            logger.info(f"Alert triggered for product {product.id}: ${result.price} <= ${product.target_price}")
        
        # Check additional alerts
        alerts = db.query(Alert).filter(
            Alert.product_id == product.id,
            Alert.status == AlertStatus.PENDING,
        ).all()
        
        for alert in alerts:
            should_trigger = False
            
            if alert.alert_type == "price_drop" and result.price <= alert.target_price:
                should_trigger = True
            elif alert.alert_type == "back_in_stock" and result.availability == "in_stock":
                should_trigger = True
            
            if should_trigger:
                alert.status = AlertStatus.TRIGGERED
                alert.triggered_at = datetime.utcnow()
                alert.triggered_price = result.price
                
                await self._send_price_alert(db, product)
    
    async def _send_price_alert(self, db: Session, product: TrackedProduct):
        """Send price alert notifications"""
        try:
            # Get user's notification settings if product has user
            notification_settings = None
            if product.user_id:
                notification_settings = db.query(NotificationSetting).filter(
                    NotificationSetting.user_id == product.user_id,
                    NotificationSetting.is_enabled == True,
                ).all()
            
            # Send notifications
            results = await notification_service.send_price_alert(
                product,
                notification_settings=notification_settings,
            )
            
            # Log results
            for result in results:
                log = NotificationLog(
                    user_id=product.user_id,
                    product_id=product.id,
                    notification_type=NotificationType(result.channel),
                    recipient=product.notify_email or "configured",
                    subject=f"Price Alert: {product.title}",
                    status="sent" if result.success else "failed",
                    error_message=result.error,
                )
                db.add(log)
            
        except Exception as e:
            logger.exception(f"Error sending notifications for product {product.id}")
    
    async def _aggregate_daily_stats(self):
        """Aggregate daily statistics"""
        with get_db_context() as db:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            stats = SystemStats(
                stat_date=today,
                total_products=db.query(TrackedProduct).count(),
                total_users=0,  # Will be updated with actual user count
                price_checks_today=self._stats["checks_today"],
                alerts_triggered_today=self._stats["alerts_triggered_today"],
                notifications_sent_today=db.query(NotificationLog).filter(
                    NotificationLog.sent_at >= today
                ).count(),
                api_errors_today=self._stats["errors_today"],
            )
            
            db.add(stats)
            db.commit()
            
            # Reset daily stats
            self._stats["checks_today"] = 0
            self._stats["alerts_triggered_today"] = 0
            self._stats["errors_today"] = 0
            
            logger.info("Daily stats aggregated")
    
    async def _cleanup_old_history(self):
        """Clean up price history older than 90 days"""
        with get_db_context() as db:
            cutoff = datetime.utcnow() - timedelta(days=90)
            
            deleted = db.query(PriceHistory).filter(
                PriceHistory.checked_at < cutoff
            ).delete()
            
            db.commit()
            logger.info(f"Cleaned up {deleted} old price history records")


# Global instance
scheduler_service = SchedulerService()
