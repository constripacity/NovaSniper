"""
NovaSniper v2.0 Pydantic Schemas
Request/response models for all API endpoints
"""
from pydantic import BaseModel, EmailStr, Field, HttpUrl, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# Enums for API
class PlatformEnum(str, Enum):
    amazon = "amazon"
    ebay = "ebay"
    walmart = "walmart"
    bestbuy = "bestbuy"
    target = "target"
    newegg = "newegg"
    custom = "custom"


class AlertStatusEnum(str, Enum):
    pending = "pending"
    triggered = "triggered"
    expired = "expired"
    disabled = "disabled"


class NotificationTypeEnum(str, Enum):
    email = "email"
    discord = "discord"
    telegram = "telegram"
    pushover = "pushover"
    sms = "sms"
    slack = "slack"
    webhook = "webhook"


# ============ User Schemas ============

class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    timezone: str = "UTC"


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    timezone: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)


class UserResponse(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    api_key: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserWithStats(UserResponse):
    tracked_products_count: int = 0
    active_alerts_count: int = 0
    watchlists_count: int = 0


# ============ Authentication Schemas ============

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None


class APIKeyResponse(BaseModel):
    api_key: str
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ============ Tracked Product Schemas ============

class TrackedProductBase(BaseModel):
    platform: PlatformEnum
    product_id: str = Field(..., description="Product URL or ID")
    target_price: float = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=3)
    notify_email: Optional[EmailStr] = None


class TrackedProductCreate(TrackedProductBase):
    watchlist_id: Optional[int] = None


class TrackedProductUpdate(BaseModel):
    target_price: Optional[float] = Field(None, gt=0)
    currency: Optional[str] = Field(None, max_length=3)
    notify_email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class TrackedProductResponse(TrackedProductBase):
    id: int
    user_id: Optional[int]
    asin: Optional[str]
    title: Optional[str]
    description: Optional[str]
    image_url: Optional[str]
    product_url: Optional[str]
    brand: Optional[str]
    category: Optional[str]
    current_price: Optional[float]
    original_price: Optional[float]
    lowest_price: Optional[float]
    highest_price: Optional[float]
    alert_status: AlertStatusEnum
    alert_triggered_at: Optional[datetime]
    is_active: bool
    check_count: int
    last_checked: Optional[datetime]
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TrackedProductBrief(BaseModel):
    """Minimal product info for lists"""
    id: int
    platform: PlatformEnum
    title: Optional[str]
    image_url: Optional[str]
    current_price: Optional[float]
    target_price: float
    currency: str
    alert_status: AlertStatusEnum

    class Config:
        from_attributes = True


# ============ Price History Schemas ============

class PriceHistoryBase(BaseModel):
    price: float
    currency: str = "USD"
    availability: Optional[str] = None
    seller: Optional[str] = None
    condition: Optional[str] = None


class PriceHistoryResponse(PriceHistoryBase):
    id: int
    product_id: int
    checked_at: datetime

    class Config:
        from_attributes = True


class PriceHistoryBulk(BaseModel):
    """Bulk price history for charts"""
    product_id: int
    title: Optional[str]
    currency: str
    history: List[Dict[str, Any]]  # [{timestamp, price, availability}]
    stats: Dict[str, float]  # min, max, avg, current


# ============ Alert Schemas ============

class AlertBase(BaseModel):
    target_price: float = Field(..., gt=0)
    alert_type: str = "price_drop"
    expires_at: Optional[datetime] = None


class AlertCreate(AlertBase):
    product_id: int


class AlertResponse(AlertBase):
    id: int
    product_id: int
    status: AlertStatusEnum
    triggered_at: Optional[datetime]
    triggered_price: Optional[float]
    notification_sent: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Watchlist Schemas ============

class WatchlistBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    is_public: bool = False


class WatchlistCreate(WatchlistBase):
    pass


class WatchlistUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    is_public: Optional[bool] = None


class WatchlistItemAdd(BaseModel):
    product_id: int
    notes: Optional[str] = None
    priority: int = 0


class WatchlistItemResponse(BaseModel):
    id: int
    product_id: int
    notes: Optional[str]
    priority: int
    added_at: datetime
    product: TrackedProductBrief

    class Config:
        from_attributes = True


class WatchlistResponse(WatchlistBase):
    id: int
    user_id: int
    share_code: Optional[str]
    created_at: datetime
    updated_at: datetime
    items_count: int = 0

    class Config:
        from_attributes = True


class WatchlistWithItems(WatchlistResponse):
    items: List[WatchlistItemResponse] = []


# ============ Notification Schemas ============

class NotificationSettingBase(BaseModel):
    notification_type: NotificationTypeEnum
    is_enabled: bool = True
    config: Optional[Dict[str, Any]] = None
    notify_price_drop: bool = True
    notify_price_increase: bool = False
    notify_back_in_stock: bool = True
    notify_daily_digest: bool = False
    quiet_hours_start: Optional[int] = Field(None, ge=0, le=23)
    quiet_hours_end: Optional[int] = Field(None, ge=0, le=23)


class NotificationSettingCreate(NotificationSettingBase):
    pass


class NotificationSettingUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    notify_price_drop: Optional[bool] = None
    notify_price_increase: Optional[bool] = None
    notify_back_in_stock: Optional[bool] = None
    notify_daily_digest: Optional[bool] = None
    quiet_hours_start: Optional[int] = Field(None, ge=0, le=23)
    quiet_hours_end: Optional[int] = Field(None, ge=0, le=23)


class NotificationSettingResponse(NotificationSettingBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationLogResponse(BaseModel):
    id: int
    notification_type: NotificationTypeEnum
    recipient: str
    subject: Optional[str]
    status: str
    error_message: Optional[str]
    sent_at: datetime

    class Config:
        from_attributes = True


# ============ Webhook Schemas ============

class OutboundWebhookBase(BaseModel):
    name: str = Field(..., max_length=100)
    url: HttpUrl
    events: List[str] = ["price_drop", "back_in_stock"]


class OutboundWebhookCreate(OutboundWebhookBase):
    pass


class OutboundWebhookUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    url: Optional[HttpUrl] = None
    events: Optional[List[str]] = None
    is_active: Optional[bool] = None


class OutboundWebhookResponse(OutboundWebhookBase):
    id: int
    user_id: int
    secret: Optional[str]
    is_active: bool
    last_triggered: Optional[datetime]
    success_count: int
    failure_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Analytics Schemas ============

class PriceStats(BaseModel):
    current_price: Optional[float]
    lowest_price: Optional[float]
    highest_price: Optional[float]
    average_price: Optional[float]
    price_change_24h: Optional[float]
    price_change_7d: Optional[float]
    price_change_30d: Optional[float]


class ProductAnalytics(BaseModel):
    product_id: int
    title: Optional[str]
    stats: PriceStats
    check_count: int
    days_tracked: int
    best_time_to_buy: Optional[str]


class UserAnalytics(BaseModel):
    total_products: int
    active_alerts: int
    triggered_alerts: int
    total_savings: float
    watchlists_count: int
    notifications_sent: int


class SystemStatsResponse(BaseModel):
    stat_date: datetime
    total_products: int
    total_users: int
    price_checks_today: int
    alerts_triggered_today: int
    notifications_sent_today: int
    api_errors_today: int
    average_check_time_ms: Optional[float]


# ============ Utility Schemas ============

class HealthCheck(BaseModel):
    status: str = "healthy"
    version: str
    database: str = "connected"
    scheduler: str = "running"
    timestamp: datetime


class BulkOperationResult(BaseModel):
    success: int
    failed: int
    errors: List[Dict[str, Any]] = []


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    per_page: int
    pages: int


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
