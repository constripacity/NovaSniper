from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String

from app.database import Base


class TrackedProduct(Base):
    __tablename__ = "tracked_products"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String, nullable=False)
    product_id = Column(String, nullable=False, index=True)
    product_url = Column(String, nullable=False)
    target_price = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    current_price = Column(Float, nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    alert_sent = Column(Boolean, default=False)
    notify_email = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
