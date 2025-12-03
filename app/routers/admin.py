"""
NovaSniper v2.0 Admin Router
System administration and monitoring
"""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    User, TrackedProduct, PriceHistory, NotificationLog,
    SystemStats, APIRequestLog, Platform, AlertStatus
)
from app.schemas import UserResponse, SystemStatsResponse
from app.utils.auth import get_current_admin_user
from app.services.scheduler import scheduler_service
from app.services.price_fetcher import price_fetcher_service

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard")
async def admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Get admin dashboard overview
    """
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    
    # User stats
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.last_login >= week_ago).count()
    new_users_today = db.query(User).filter(User.created_at >= today).count()
    
    # Product stats
    total_products = db.query(TrackedProduct).count()
    active_products = db.query(TrackedProduct).filter(TrackedProduct.is_active == True).count()
    
    # Platform breakdown
    platform_counts = db.query(
        TrackedProduct.platform,
        func.count(TrackedProduct.id)
    ).group_by(TrackedProduct.platform).all()
    
    # Alert stats
    pending_alerts = db.query(TrackedProduct).filter(
        TrackedProduct.alert_status == AlertStatus.PENDING
    ).count()
    triggered_today = db.query(TrackedProduct).filter(
        TrackedProduct.alert_triggered_at >= today
    ).count()
    
    # Price checks today
    checks_today = db.query(PriceHistory).filter(
        PriceHistory.checked_at >= today
    ).count()
    
    # Notifications today
    notifications_today = db.query(NotificationLog).filter(
        NotificationLog.sent_at >= today
    ).count()
    
    # Scheduler status
    scheduler_stats = scheduler_service.get_stats()
    
    # Platform configuration status
    platform_status = {
        p.value: price_fetcher_service.is_platform_configured(p)
        for p in Platform
    }
    
    return {
        "timestamp": now.isoformat(),
        "users": {
            "total": total_users,
            "active_this_week": active_users,
            "new_today": new_users_today,
        },
        "products": {
            "total": total_products,
            "active": active_products,
            "by_platform": {p.value: c for p, c in platform_counts},
        },
        "alerts": {
            "pending": pending_alerts,
            "triggered_today": triggered_today,
        },
        "activity": {
            "price_checks_today": checks_today,
            "notifications_today": notifications_today,
        },
        "scheduler": scheduler_stats,
        "platforms": platform_status,
    }


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    List all users
    """
    query = db.query(User)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    if search:
        query = query.filter(
            (User.email.ilike(f"%{search}%")) |
            (User.username.ilike(f"%{search}%"))
        )
    
    users = query.order_by(desc(User.created_at)).offset(skip).limit(limit).all()
    return users


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Get detailed user information
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user stats
    products_count = db.query(TrackedProduct).filter(
        TrackedProduct.user_id == user_id
    ).count()
    
    active_alerts = db.query(TrackedProduct).filter(
        TrackedProduct.user_id == user_id,
        TrackedProduct.alert_status == AlertStatus.PENDING,
    ).count()
    
    notifications_sent = db.query(NotificationLog).filter(
        NotificationLog.user_id == user_id
    ).count()
    
    return {
        "user": UserResponse.from_orm(user),
        "stats": {
            "tracked_products": products_count,
            "active_alerts": active_alerts,
            "notifications_sent": notifications_sent,
        }
    }


@router.patch("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Toggle user active status
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    
    user.is_active = not user.is_active
    db.commit()
    
    return {"user_id": user_id, "is_active": user.is_active}


@router.patch("/users/{user_id}/toggle-admin")
async def toggle_user_admin(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Toggle user admin status
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove your own admin status")
    
    user.is_admin = not user.is_admin
    db.commit()
    
    return {"user_id": user_id, "is_admin": user.is_admin}


@router.get("/stats/history", response_model=List[SystemStatsResponse])
async def get_stats_history(
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Get historical system statistics
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    stats = db.query(SystemStats).filter(
        SystemStats.stat_date >= cutoff
    ).order_by(SystemStats.stat_date).all()
    
    return stats


@router.get("/products/errors")
async def get_products_with_errors(
    min_errors: int = Query(3, ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Get products with consecutive errors
    """
    products = db.query(TrackedProduct).filter(
        TrackedProduct.consecutive_errors >= min_errors
    ).order_by(desc(TrackedProduct.consecutive_errors)).offset(skip).limit(limit).all()
    
    return [{
        "id": p.id,
        "platform": p.platform.value,
        "product_id": p.product_id,
        "title": p.title,
        "consecutive_errors": p.consecutive_errors,
        "last_error": p.last_error,
        "last_checked": p.last_checked,
        "is_active": p.is_active,
    } for p in products]


@router.post("/products/{product_id}/reset-errors")
async def reset_product_errors(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Reset error count and reactivate product
    """
    product = db.query(TrackedProduct).filter(TrackedProduct.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product.consecutive_errors = 0
    product.last_error = None
    product.is_active = True
    db.commit()
    
    return {"product_id": product_id, "status": "reset"}


@router.get("/scheduler/status")
async def get_scheduler_status(
    current_user: User = Depends(get_current_admin_user),
):
    """
    Get scheduler status and statistics
    """
    return scheduler_service.get_stats()


@router.post("/scheduler/trigger")
async def trigger_price_check(
    current_user: User = Depends(get_current_admin_user),
):
    """
    Manually trigger a price check cycle
    """
    if not scheduler_service.is_running():
        raise HTTPException(status_code=400, detail="Scheduler is not running")
    
    # Run check in background
    import asyncio
    asyncio.create_task(scheduler_service._check_all_prices())
    
    return {"status": "triggered", "message": "Price check started"}


@router.get("/api-logs")
async def get_api_logs(
    hours: int = Query(24, ge=1, le=168),
    endpoint: Optional[str] = None,
    status_code: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Get API request logs
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    query = db.query(APIRequestLog).filter(APIRequestLog.request_at >= cutoff)
    
    if endpoint:
        query = query.filter(APIRequestLog.endpoint.ilike(f"%{endpoint}%"))
    
    if status_code:
        query = query.filter(APIRequestLog.status_code == status_code)
    
    logs = query.order_by(desc(APIRequestLog.request_at)).offset(skip).limit(limit).all()
    
    return [{
        "id": log.id,
        "user_id": log.user_id,
        "endpoint": log.endpoint,
        "method": log.method,
        "status_code": log.status_code,
        "response_time_ms": log.response_time_ms,
        "ip_address": log.ip_address,
        "request_at": log.request_at,
    } for log in logs]


@router.delete("/cleanup/old-history")
async def cleanup_old_history(
    days: int = Query(90, ge=30, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Manually clean up old price history
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    deleted = db.query(PriceHistory).filter(
        PriceHistory.checked_at < cutoff
    ).delete()
    
    db.commit()
    
    return {"deleted_records": deleted, "cutoff_days": days}
