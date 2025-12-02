from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.database import SessionLocal
from app.schemas import TrackedProductCreate, TrackedProductResponse
from app.services import price_fetcher
from app.services.notifier import EmailNotifier

router = APIRouter(prefix="/tracked-products", tags=["tracked-products"])
logger = logging.getLogger(__name__)
settings = get_settings()
notifier = EmailNotifier(settings)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def parse_product_identifier(platform: str, product_id: str):
    if platform == "amazon":
        asin = price_fetcher.extract_amazon_asin(product_id)
        if not asin:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Amazon ASIN or URL")
        return asin, price_fetcher.build_product_url("amazon", asin)

    if platform == "ebay":
        item_id = price_fetcher.extract_ebay_item_id(product_id)
        if not item_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid eBay item ID or URL")
        return item_id, price_fetcher.build_product_url("ebay", item_id)

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported platform")


@router.post("", response_model=TrackedProductResponse, status_code=status.HTTP_201_CREATED)
def create_tracked_product(payload: TrackedProductCreate, db: Session = Depends(get_db)):
    product_id_value = payload.product_id
    if payload.product_url:
        product_id_value = payload.product_url

    parsed_id, canonical_url = parse_product_identifier(payload.platform, product_id_value)

    tracked = models.TrackedProduct(
        platform=payload.platform,
        product_id=parsed_id,
        product_url=canonical_url,
        target_price=payload.target_price,
        currency=payload.currency,
        notify_email=payload.notify_email,
    )
    db.add(tracked)
    db.commit()
    db.refresh(tracked)
    return tracked


@router.get("", response_model=List[TrackedProductResponse])
def list_tracked_products(db: Session = Depends(get_db)):
    products = db.query(models.TrackedProduct).order_by(models.TrackedProduct.created_at.desc()).all()
    return products


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tracked_product(product_id: int, db: Session = Depends(get_db)):
    tracked = db.query(models.TrackedProduct).filter(models.TrackedProduct.id == product_id).first()
    if not tracked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked product not found")
    db.delete(tracked)
    db.commit()
    return None


@router.post("/{product_id}/check-now", response_model=TrackedProductResponse)
def check_now(product_id: int, db: Session = Depends(get_db)):
    tracked = db.query(models.TrackedProduct).filter(models.TrackedProduct.id == product_id).first()
    if not tracked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked product not found")

    price, currency = price_fetcher.get_current_price(tracked.platform, tracked.product_id)
    tracked.current_price = price
    tracked.last_checked_at = datetime.utcnow()

    if price is not None and tracked.target_price >= price and not tracked.alert_sent:
        product_title = f"{tracked.platform.title()} item {tracked.product_id}"
        notifier.send_price_alert(
            to_email=tracked.notify_email,
            product_title=product_title,
            platform=tracked.platform,
            current_price=price,
            currency=currency or tracked.currency,
            product_url=tracked.product_url,
        )
        tracked.alert_sent = True

    db.commit()
    db.refresh(tracked)
    return tracked
