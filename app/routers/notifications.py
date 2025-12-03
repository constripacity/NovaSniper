"""
NovaSniper v2.0 Notifications Router
Notification settings and logs management
"""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import NotificationSetting, NotificationLog, NotificationType, User
from app.schemas import (
    NotificationSettingCreate, NotificationSettingUpdate, NotificationSettingResponse,
    NotificationLogResponse
)
from app.utils.auth import get_current_user_required
from app.services.notifier import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/channels")
async def get_available_channels():
    """
    Get list of available notification channels and their configuration status
    """
    channels = []
    
    for ntype in NotificationType:
        notifier = notification_service.get_notifier(ntype)
        channels.append({
            "type": ntype.value,
            "configured": notifier.is_configured() if notifier else False,
            "description": _get_channel_description(ntype),
        })
    
    return {"channels": channels}


@router.get("/settings", response_model=List[NotificationSettingResponse])
async def get_notification_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Get user's notification settings
    """
    settings = db.query(NotificationSetting).filter(
        NotificationSetting.user_id == current_user.id
    ).all()
    
    return settings


@router.post("/settings", response_model=NotificationSettingResponse, status_code=status.HTTP_201_CREATED)
async def create_notification_setting(
    setting_in: NotificationSettingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Create notification setting for a channel
    """
    # Check if setting already exists for this type
    existing = db.query(NotificationSetting).filter(
        NotificationSetting.user_id == current_user.id,
        NotificationSetting.notification_type == setting_in.notification_type,
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Setting for {setting_in.notification_type.value} already exists. Use PATCH to update."
        )
    
    setting = NotificationSetting(
        user_id=current_user.id,
        notification_type=setting_in.notification_type,
        is_enabled=setting_in.is_enabled,
        config=setting_in.config,
        notify_price_drop=setting_in.notify_price_drop,
        notify_price_increase=setting_in.notify_price_increase,
        notify_back_in_stock=setting_in.notify_back_in_stock,
        notify_daily_digest=setting_in.notify_daily_digest,
        quiet_hours_start=setting_in.quiet_hours_start,
        quiet_hours_end=setting_in.quiet_hours_end,
    )
    
    db.add(setting)
    db.commit()
    db.refresh(setting)
    
    return setting


@router.get("/settings/{notification_type}", response_model=NotificationSettingResponse)
async def get_notification_setting(
    notification_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Get specific notification setting
    """
    try:
        ntype = NotificationType(notification_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid notification type")
    
    setting = db.query(NotificationSetting).filter(
        NotificationSetting.user_id == current_user.id,
        NotificationSetting.notification_type == ntype,
    ).first()
    
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    
    return setting


@router.patch("/settings/{notification_type}", response_model=NotificationSettingResponse)
async def update_notification_setting(
    notification_type: str,
    setting_in: NotificationSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Update notification setting
    """
    try:
        ntype = NotificationType(notification_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid notification type")
    
    setting = db.query(NotificationSetting).filter(
        NotificationSetting.user_id == current_user.id,
        NotificationSetting.notification_type == ntype,
    ).first()
    
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    
    update_data = setting_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(setting, field, value)
    
    setting.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(setting)
    
    return setting


@router.delete("/settings/{notification_type}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification_setting(
    notification_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Delete notification setting
    """
    try:
        ntype = NotificationType(notification_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid notification type")
    
    setting = db.query(NotificationSetting).filter(
        NotificationSetting.user_id == current_user.id,
        NotificationSetting.notification_type == ntype,
    ).first()
    
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    
    db.delete(setting)
    db.commit()


@router.post("/settings/{notification_type}/test")
async def test_notification(
    notification_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Send a test notification
    """
    try:
        ntype = NotificationType(notification_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid notification type")
    
    setting = db.query(NotificationSetting).filter(
        NotificationSetting.user_id == current_user.id,
        NotificationSetting.notification_type == ntype,
    ).first()
    
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found. Create it first.")
    
    # Get recipient from config
    recipient = _get_recipient_from_config(ntype, setting.config)
    if not recipient:
        raise HTTPException(status_code=400, detail="No recipient configured")
    
    # Send test notification
    result = await notification_service.send_notification(
        ntype,
        recipient,
        "NovaSniper Test Notification",
        "This is a test notification from NovaSniper. If you received this, your notifications are configured correctly!",
    )
    
    # Log the test
    log = NotificationLog(
        user_id=current_user.id,
        notification_type=ntype,
        recipient=recipient,
        subject="Test Notification",
        status="sent" if result.success else "failed",
        error_message=result.error,
    )
    db.add(log)
    db.commit()
    
    if result.success:
        return {"status": "success", "message": "Test notification sent"}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to send: {result.error}")


# ============ Notification Logs ============

@router.get("/logs", response_model=List[NotificationLogResponse])
async def get_notification_logs(
    days: int = Query(7, ge=1, le=90),
    notification_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Get notification logs
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(NotificationLog).filter(
        NotificationLog.user_id == current_user.id,
        NotificationLog.sent_at >= cutoff,
    )
    
    if notification_type:
        try:
            ntype = NotificationType(notification_type)
            query = query.filter(NotificationLog.notification_type == ntype)
        except ValueError:
            pass
    
    if status:
        query = query.filter(NotificationLog.status == status)
    
    logs = query.order_by(NotificationLog.sent_at.desc()).offset(skip).limit(limit).all()
    
    return logs


@router.get("/logs/stats")
async def get_notification_stats(
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Get notification statistics
    """
    from sqlalchemy import func
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Total counts by status
    status_counts = db.query(
        NotificationLog.status,
        func.count(NotificationLog.id)
    ).filter(
        NotificationLog.user_id == current_user.id,
        NotificationLog.sent_at >= cutoff,
    ).group_by(NotificationLog.status).all()
    
    # Counts by type
    type_counts = db.query(
        NotificationLog.notification_type,
        func.count(NotificationLog.id)
    ).filter(
        NotificationLog.user_id == current_user.id,
        NotificationLog.sent_at >= cutoff,
    ).group_by(NotificationLog.notification_type).all()
    
    return {
        "period_days": days,
        "by_status": {s: c for s, c in status_counts},
        "by_type": {t.value: c for t, c in type_counts},
        "total": sum(c for _, c in status_counts),
    }


# ============ Helpers ============

def _get_channel_description(ntype: NotificationType) -> str:
    """Get description for notification channel"""
    descriptions = {
        NotificationType.EMAIL: "Email notifications via SMTP",
        NotificationType.DISCORD: "Discord webhook notifications",
        NotificationType.TELEGRAM: "Telegram bot notifications",
        NotificationType.PUSHOVER: "Pushover push notifications",
        NotificationType.SMS: "SMS via Twilio",
        NotificationType.SLACK: "Slack webhook notifications",
        NotificationType.WEBHOOK: "Custom webhook integrations",
    }
    return descriptions.get(ntype, "")


def _get_recipient_from_config(ntype: NotificationType, config: dict) -> Optional[str]:
    """Extract recipient from notification config"""
    if not config:
        return None
    
    key_map = {
        NotificationType.EMAIL: "email",
        NotificationType.DISCORD: "webhook_url",
        NotificationType.TELEGRAM: "chat_id",
        NotificationType.PUSHOVER: "user_key",
        NotificationType.SMS: "phone_number",
        NotificationType.SLACK: "webhook_url",
        NotificationType.WEBHOOK: "url",
    }
    
    key = key_map.get(ntype)
    return config.get(key) if key else None
