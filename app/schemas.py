from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class TrackedProductCreate(BaseModel):
    platform: Literal["amazon", "ebay"]
    product_id: str = Field(..., description="ASIN for Amazon or Item ID for eBay; URLs are accepted")
    target_price: float
    currency: str
    notify_email: EmailStr
    product_url: Optional[HttpUrl] = None


class TrackedProductResponse(BaseModel):
    id: int
    platform: str
    product_id: str
    product_url: str
    target_price: float
    currency: str
    current_price: float | None = None
    last_checked_at: datetime | None = None
    alert_sent: bool
    notify_email: EmailStr
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
