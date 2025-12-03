"""
NovaSniper v2.0 Configuration
Expanded settings for multi-platform price tracking with notifications
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "NovaSniper"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    
    # Database
    DATABASE_URL: str = "sqlite:///./novasniper.db"
    
    # Scheduler
    CHECK_INTERVAL_SECONDS: int = 3600  # 1 hour default
    MAX_CONCURRENT_CHECKS: int = 10
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Authentication
    API_KEY_HEADER: str = "X-API-Key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Email (SMTP)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_TLS: bool = True
    FROM_EMAIL: Optional[str] = None
    
    # Amazon Product Advertising API
    AMAZON_ACCESS_KEY: Optional[str] = None
    AMAZON_SECRET_KEY: Optional[str] = None
    AMAZON_PARTNER_TAG: Optional[str] = None
    AMAZON_REGION: str = "us-east-1"
    AMAZON_MARKETPLACE: str = "www.amazon.com"
    
    # eBay API
    EBAY_APP_ID: Optional[str] = None
    EBAY_CERT_ID: Optional[str] = None
    EBAY_DEV_ID: Optional[str] = None
    EBAY_SANDBOX: bool = False
    
    # Walmart API
    WALMART_CLIENT_ID: Optional[str] = None
    WALMART_CLIENT_SECRET: Optional[str] = None
    
    # Best Buy API
    BESTBUY_API_KEY: Optional[str] = None
    
    # Target API (Redsky)
    TARGET_API_KEY: Optional[str] = None
    
    # Discord Notifications
    DISCORD_WEBHOOK_URL: Optional[str] = None
    DISCORD_ENABLED: bool = False
    
    # Telegram Notifications
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_ENABLED: bool = False
    
    # Pushover Notifications
    PUSHOVER_APP_TOKEN: Optional[str] = None
    PUSHOVER_ENABLED: bool = False
    
    # Twilio SMS
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_FROM_NUMBER: Optional[str] = None
    TWILIO_ENABLED: bool = False
    
    # Slack Notifications
    SLACK_WEBHOOK_URL: Optional[str] = None
    SLACK_ENABLED: bool = False
    
    # Outbound Webhooks
    WEBHOOK_TIMEOUT: int = 10
    WEBHOOK_RETRY_ATTEMPTS: int = 3
    
    # Proxy (for API requests)
    HTTP_PROXY: Optional[str] = None
    HTTPS_PROXY: Optional[str] = None
    
    # Caching
    CACHE_TTL_SECONDS: int = 300  # 5 minutes
    REDIS_URL: Optional[str] = None  # Optional Redis for distributed caching

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
