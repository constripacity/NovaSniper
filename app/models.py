"""
NovaSniper v2.0 Database Models
Complete ORM models for price tracking, users, notifications, and analytics
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, 
    ForeignKey, Enum, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from datetime import datetime
import enum

Base = declarative_base()


class Platform(enum.Enum):
    AMAZON = "amazon"
    EBAY = "ebay"
    WALMART = "walmart"
    BESTBUY = "bestbuy"
    TARGET = "target"
    NEWEGG = "newegg"
    CUSTOM = "custom"


class AlertStatus(enum.Enum):
    PENDING = "pending"
    TRIGGERED = "triggered"
    EXPIRED = "expired"
    DISABLED = "disabled"


class NotificationType(enum.Enum):
    EMAIL = "email"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    PUSHOVER = "pushover"
    SMS = "sms"
    SLACK = "slack"
    WEBHOOK = "webhook"


class User(Base):
    """User accounts for multi-tenant support"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255))
    api_key = Column(String(64), unique=True, index=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    timezone = Column(String(50), default="UTC")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Relationships
    tracked_products = relationship("TrackedProduct", back_populates="user", cascade="all, delete-orphan")
    watchlists = relationship("Watchlist", back_populates="user", cascade="all, delete-orphan")
    notification_settings = relationship("NotificationSetting", back_populates="user", cascade="all, delete-orphan")
    webhooks = relationship("OutboundWebhook", back_populates="user", cascade="all, delete-orphan")


class TrackedProduct(Base):
    """Products being tracked for price changes"""
    __tablename__ = "tracked_products"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Null for anonymous/legacy
    platform = Column(Enum(Platform), nullable=False, index=True)
    product_id = Column(String(500), nullable=False)  # URL or product ID
    asin = Column(String(20), index=True)  # Amazon ASIN if applicable
    
    # Product metadata (cached from API)
    title = Column(String(500))
    description = Column(Text)
    image_url = Column(String(1000))
    product_url = Column(String(1000))
    brand = Column(String(200))
    category = Column(String(200))
    
    # Price tracking
    current_price = Column(Float)
    original_price = Column(Float)  # MSRP / list price
    lowest_price = Column(Float)
    highest_price = Column(Float)
    currency = Column(String(3), default="USD")
    
    # Alert configuration
    target_price = Column(Float, nullable=False)
    alert_status = Column(Enum(AlertStatus), default=AlertStatus.PENDING)
    alert_triggered_at = Column(DateTime)
    notify_email = Column(String(255))  # Legacy field
    
    # Tracking state
    is_active = Column(Boolean, default=True)
    check_count = Column(Integer, default=0)
    last_checked = Column(DateTime)
    last_error = Column(Text)
    consecutive_errors = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="tracked_products")
    price_history = relationship("PriceHistory", back_populates="product", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="product", cascade="all, delete-orphan")
    watchlist_items = relationship("WatchlistItem", back_populates="product", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_tracked_products_platform_product", "platform", "product_id"),
        Index("ix_tracked_products_user_active", "user_id", "is_active"),
    )


class PriceHistory(Base):
    """Historical price records for trend analysis"""
    __tablename__ = "price_history"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("tracked_products.id", ondelete="CASCADE"), nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")
    availability = Column(String(50))  # in_stock, out_of_stock, limited
    seller = Column(String(200))  # For marketplace items
    condition = Column(String(50))  # new, used, refurbished
    checked_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationship
    product = relationship("TrackedProduct", back_populates="price_history")
    
    __table_args__ = (
        Index("ix_price_history_product_date", "product_id", "checked_at"),
    )


class Alert(Base):
    """Individual price alerts with multiple thresholds"""
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("tracked_products.id", ondelete="CASCADE"), nullable=False)
    target_price = Column(Float, nullable=False)
    alert_type = Column(String(50), default="price_drop")  # price_drop, price_increase, back_in_stock
    status = Column(Enum(AlertStatus), default=AlertStatus.PENDING)
    triggered_at = Column(DateTime)
    triggered_price = Column(Float)
    notification_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # Optional expiration
    
    # Relationship
    product = relationship("TrackedProduct", back_populates="alerts")


class Watchlist(Base):
    """Named groups of tracked products"""
    __tablename__ = "watchlists"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    is_public = Column(Boolean, default=False)
    share_code = Column(String(20), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="watchlists")
    items = relationship("WatchlistItem", back_populates="watchlist", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_watchlist_name"),
    )


class WatchlistItem(Base):
    """Products within a watchlist"""
    __tablename__ = "watchlist_items"
    
    id = Column(Integer, primary_key=True, index=True)
    watchlist_id = Column(Integer, ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("tracked_products.id", ondelete="CASCADE"), nullable=False)
    notes = Column(Text)
    priority = Column(Integer, default=0)
    added_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    watchlist = relationship("Watchlist", back_populates="items")
    product = relationship("TrackedProduct", back_populates="watchlist_items")
    
    __table_args__ = (
        UniqueConstraint("watchlist_id", "product_id", name="uq_watchlist_product"),
    )


class NotificationSetting(Base):
    """User notification preferences per channel"""
    __tablename__ = "notification_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    notification_type = Column(Enum(NotificationType), nullable=False)
    is_enabled = Column(Boolean, default=True)
    
    # Channel-specific config stored as JSON
    config = Column(JSON)  # e.g., {"chat_id": "123"} for Telegram
    
    # Notification preferences
    notify_price_drop = Column(Boolean, default=True)
    notify_price_increase = Column(Boolean, default=False)
    notify_back_in_stock = Column(Boolean, default=True)
    notify_daily_digest = Column(Boolean, default=False)
    quiet_hours_start = Column(Integer)  # Hour 0-23
    quiet_hours_end = Column(Integer)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="notification_settings")
    
    __table_args__ = (
        UniqueConstraint("user_id", "notification_type", name="uq_user_notification_type"),
    )


class NotificationLog(Base):
    """Log of all sent notifications"""
    __tablename__ = "notification_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    product_id = Column(Integer, ForeignKey("tracked_products.id", ondelete="SET NULL"))
    notification_type = Column(Enum(NotificationType), nullable=False)
    recipient = Column(String(255))  # email, phone, chat_id, etc.
    subject = Column(String(500))
    message = Column(Text)
    status = Column(String(50))  # sent, failed, pending
    error_message = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_notification_logs_user_date", "user_id", "sent_at"),
    )


class OutboundWebhook(Base):
    """Custom webhooks for integrations"""
    __tablename__ = "outbound_webhooks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    url = Column(String(1000), nullable=False)
    secret = Column(String(100))  # For HMAC signing
    is_active = Column(Boolean, default=True)
    
    # Event filters
    events = Column(JSON)  # ["price_drop", "back_in_stock"]
    
    # Stats
    last_triggered = Column(DateTime)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="webhooks")


class SystemStats(Base):
    """Aggregate statistics for admin dashboard"""
    __tablename__ = "system_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    stat_date = Column(DateTime, nullable=False, unique=True, index=True)
    total_products = Column(Integer, default=0)
    total_users = Column(Integer, default=0)
    price_checks_today = Column(Integer, default=0)
    alerts_triggered_today = Column(Integer, default=0)
    notifications_sent_today = Column(Integer, default=0)
    api_errors_today = Column(Integer, default=0)
    average_check_time_ms = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class APIRequestLog(Base):
    """API request logging for debugging and rate limiting"""
    __tablename__ = "api_request_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    api_key = Column(String(64))
    endpoint = Column(String(200))
    method = Column(String(10))
    status_code = Column(Integer)
    response_time_ms = Column(Float)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    request_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index("ix_api_logs_user_date", "user_id", "request_at"),
    )
