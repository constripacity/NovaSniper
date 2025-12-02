from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models
from app.database import SessionLocal
from app.schemas import TrackedProductCreate, TrackedProductResponse
from app.services import price_fetcher

router = APIRouter(prefix="/tracked-products", tags=["tracked-products"])
logger = logging.getLogger(__name__)


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
