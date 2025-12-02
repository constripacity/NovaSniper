"""
NovaSniper v2.0 Tracked Products Router
Full CRUD for price tracking with history and analytics
"""
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TrackedProduct, PriceHistory, Alert, AlertStatus, Platform
from app.schemas import (
    TrackedProductCreate, TrackedProductUpdate, TrackedProductResponse,
    TrackedProductBrief, PriceHistoryResponse, PriceHistoryBulk,
    AlertCreate, AlertResponse, ProductAnalytics, PriceStats,
    PaginatedResponse, BulkOperationResult
)
from app.utils.auth import get_current_user, get_current_user_required
from app.models import User
from app.services.price_fetcher import price_fetcher_service
from app.services.scheduler import scheduler_service

router = APIRouter(prefix="/tracked-products", tags=["Tracked Products"])


@router.get("", response_model=List[TrackedProductBrief])
async def list_tracked_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    platform: Optional[str] = None,
    is_active: Optional[bool] = None,
    alert_status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    List tracked products with optional filters
    """
    query = db.query(TrackedProduct)
    
    # Filter by user if authenticated
    if current_user:
        query = query.filter(TrackedProduct.user_id == current_user.id)
    else:
        query = query.filter(TrackedProduct.user_id == None)
    
    # Apply filters
    if platform:
        query = query.filter(TrackedProduct.platform == Platform(platform))
    if is_active is not None:
        query = query.filter(TrackedProduct.is_active == is_active)
    if alert_status:
        query = query.filter(TrackedProduct.alert_status == AlertStatus(alert_status))
    
    products = query.order_by(desc(TrackedProduct.created_at)).offset(skip).limit(limit).all()
    return products


@router.post("", response_model=TrackedProductResponse, status_code=status.HTTP_201_CREATED)
async def create_tracked_product(
    product_in: TrackedProductCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Create a new tracked product
    """
    # Validate platform
    try:
        platform = Platform(product_in.platform.value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid platform: {product_in.platform}")
    
    # Extract product ID if URL provided
    extracted_id = price_fetcher_service.extract_product_id(platform, product_in.product_id)
    
    # Create product
    product = TrackedProduct(
        user_id=current_user.id if current_user else None,
        platform=platform,
        product_id=product_in.product_id,
        asin=extracted_id if platform == Platform.AMAZON else None,
        target_price=product_in.target_price,
        currency=product_in.currency,
        notify_email=product_in.notify_email,
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    # Immediately fetch initial price data
    result = await price_fetcher_service.fetch_price(platform, product_in.product_id)
    if result.success:
        product.current_price = result.price
        product.title = result.title
        product.image_url = result.image_url
        product.product_url = result.product_url
        product.brand = result.brand
        product.category = result.category
        product.original_price = result.original_price
        product.lowest_price = result.price
        product.highest_price = result.price
        product.last_checked = datetime.utcnow()
        
        # Add initial price history
        history = PriceHistory(
            product_id=product.id,
            price=result.price,
            currency=result.currency,
            availability=result.availability,
        )
        db.add(history)
        db.commit()
        db.refresh(product)
    
    return product


@router.get("/{product_id}", response_model=TrackedProductResponse)
async def get_tracked_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Get a tracked product by ID
    """
    product = db.query(TrackedProduct).filter(TrackedProduct.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Check ownership
    if current_user and product.user_id and product.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return product


@router.patch("/{product_id}", response_model=TrackedProductResponse)
async def update_tracked_product(
    product_id: int,
    product_in: TrackedProductUpdate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Update a tracked product
    """
    product = db.query(TrackedProduct).filter(TrackedProduct.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if current_user and product.user_id and product.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Update fields
    update_data = product_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)
    
    product.updated_at = datetime.utcnow()
    
    # Reset alert status if target price changed
    if "target_price" in update_data and product.alert_status == AlertStatus.TRIGGERED:
        product.alert_status = AlertStatus.PENDING
        product.alert_triggered_at = None
    
    db.commit()
    db.refresh(product)
    
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tracked_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Delete a tracked product
    """
    product = db.query(TrackedProduct).filter(TrackedProduct.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if current_user and product.user_id and product.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    db.delete(product)
    db.commit()


@router.post("/{product_id}/check", response_model=TrackedProductResponse)
async def check_product_price(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Manually trigger price check for a product
    """
    product = db.query(TrackedProduct).filter(TrackedProduct.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if current_user and product.user_id and product.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Trigger price check
    await scheduler_service.check_single_product(product_id)
    
    db.refresh(product)
    return product


@router.post("/{product_id}/reset-alert", response_model=TrackedProductResponse)
async def reset_product_alert(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Reset alert status to pending
    """
    product = db.query(TrackedProduct).filter(TrackedProduct.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if current_user and product.user_id and product.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    product.alert_status = AlertStatus.PENDING
    product.alert_triggered_at = None
    db.commit()
    db.refresh(product)
    
    return product


# ============ Price History ============

@router.get("/{product_id}/history", response_model=List[PriceHistoryResponse])
async def get_price_history(
    product_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Get price history for a product
    """
    product = db.query(TrackedProduct).filter(TrackedProduct.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if current_user and product.user_id and product.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    history = db.query(PriceHistory).filter(
        PriceHistory.product_id == product_id,
        PriceHistory.checked_at >= cutoff,
    ).order_by(PriceHistory.checked_at).all()
    
    return history


@router.get("/{product_id}/history/chart")
async def get_price_history_chart(
    product_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Get price history formatted for charts
    """
    product = db.query(TrackedProduct).filter(TrackedProduct.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if current_user and product.user_id and product.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    history = db.query(PriceHistory).filter(
        PriceHistory.product_id == product_id,
        PriceHistory.checked_at >= cutoff,
    ).order_by(PriceHistory.checked_at).all()
    
    # Calculate stats
    prices = [h.price for h in history if h.price]
    stats = {
        "min": min(prices) if prices else None,
        "max": max(prices) if prices else None,
        "avg": sum(prices) / len(prices) if prices else None,
        "current": product.current_price,
    }
    
    return PriceHistoryBulk(
        product_id=product_id,
        title=product.title,
        currency=product.currency,
        history=[{
            "timestamp": h.checked_at.isoformat(),
            "price": h.price,
            "availability": h.availability,
        } for h in history],
        stats=stats,
    )


# ============ Alerts ============

@router.get("/{product_id}/alerts", response_model=List[AlertResponse])
async def get_product_alerts(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Get all alerts for a product
    """
    product = db.query(TrackedProduct).filter(TrackedProduct.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if current_user and product.user_id and product.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    alerts = db.query(Alert).filter(Alert.product_id == product_id).all()
    return alerts


@router.post("/{product_id}/alerts", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_product_alert(
    product_id: int,
    alert_in: AlertCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Create additional alert for a product
    """
    product = db.query(TrackedProduct).filter(TrackedProduct.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if current_user and product.user_id and product.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    alert = Alert(
        product_id=product_id,
        target_price=alert_in.target_price,
        alert_type=alert_in.alert_type,
        expires_at=alert_in.expires_at,
    )
    
    db.add(alert)
    db.commit()
    db.refresh(alert)
    
    return alert


@router.delete("/{product_id}/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_alert(
    product_id: int,
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Delete an alert
    """
    product = db.query(TrackedProduct).filter(TrackedProduct.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if current_user and product.user_id and product.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.product_id == product_id).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    db.delete(alert)
    db.commit()


# ============ Analytics ============

@router.get("/{product_id}/analytics", response_model=ProductAnalytics)
async def get_product_analytics(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Get analytics for a product
    """
    product = db.query(TrackedProduct).filter(TrackedProduct.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if current_user and product.user_id and product.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Calculate price changes
    now = datetime.utcnow()
    
    def get_price_at(days_ago: int):
        cutoff = now - timedelta(days=days_ago)
        history = db.query(PriceHistory).filter(
            PriceHistory.product_id == product_id,
            PriceHistory.checked_at >= cutoff,
        ).order_by(PriceHistory.checked_at).first()
        return history.price if history else None
    
    price_24h_ago = get_price_at(1)
    price_7d_ago = get_price_at(7)
    price_30d_ago = get_price_at(30)
    
    # Calculate average
    avg_price = db.query(func.avg(PriceHistory.price)).filter(
        PriceHistory.product_id == product_id
    ).scalar()
    
    # Days tracked
    days_tracked = (now - product.created_at).days if product.created_at else 0
    
    stats = PriceStats(
        current_price=product.current_price,
        lowest_price=product.lowest_price,
        highest_price=product.highest_price,
        average_price=float(avg_price) if avg_price else None,
        price_change_24h=(product.current_price - price_24h_ago) if product.current_price and price_24h_ago else None,
        price_change_7d=(product.current_price - price_7d_ago) if product.current_price and price_7d_ago else None,
        price_change_30d=(product.current_price - price_30d_ago) if product.current_price and price_30d_ago else None,
    )
    
    return ProductAnalytics(
        product_id=product_id,
        title=product.title,
        stats=stats,
        check_count=product.check_count,
        days_tracked=days_tracked,
        best_time_to_buy=None,  # TODO: Implement based on historical patterns
    )


# ============ Bulk Operations ============

@router.post("/bulk/check", response_model=BulkOperationResult)
async def bulk_check_prices(
    product_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Trigger price check for multiple products
    """
    success = 0
    failed = 0
    errors = []
    
    for product_id in product_ids[:50]:  # Limit to 50
        try:
            product = db.query(TrackedProduct).filter(
                TrackedProduct.id == product_id,
                TrackedProduct.user_id == current_user.id,
            ).first()
            
            if product:
                await scheduler_service.check_single_product(product_id)
                success += 1
            else:
                failed += 1
                errors.append({"product_id": product_id, "error": "Not found or not authorized"})
                
        except Exception as e:
            failed += 1
            errors.append({"product_id": product_id, "error": str(e)})
    
    return BulkOperationResult(success=success, failed=failed, errors=errors)


@router.delete("/bulk", response_model=BulkOperationResult)
async def bulk_delete_products(
    product_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Delete multiple products
    """
    deleted = db.query(TrackedProduct).filter(
        TrackedProduct.id.in_(product_ids),
        TrackedProduct.user_id == current_user.id,
    ).delete(synchronize_session=False)
    
    db.commit()
    
    return BulkOperationResult(
        success=deleted,
        failed=len(product_ids) - deleted,
        errors=[],
    )
