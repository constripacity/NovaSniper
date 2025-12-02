"""
NovaSniper v2.0 Webhooks Router
Outbound webhook management for custom integrations
"""
import secrets
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OutboundWebhook, User
from app.schemas import (
    OutboundWebhookCreate, OutboundWebhookUpdate, OutboundWebhookResponse
)
from app.utils.auth import get_current_user_required
from app.services.notifier import notification_service, NotificationType

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def generate_webhook_secret() -> str:
    """Generate a secret for webhook signing"""
    return secrets.token_hex(32)


@router.get("", response_model=List[OutboundWebhookResponse])
async def list_webhooks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    List user's outbound webhooks
    """
    webhooks = db.query(OutboundWebhook).filter(
        OutboundWebhook.user_id == current_user.id
    ).all()
    
    return webhooks


@router.post("", response_model=OutboundWebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    webhook_in: OutboundWebhookCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Create a new outbound webhook
    """
    webhook = OutboundWebhook(
        user_id=current_user.id,
        name=webhook_in.name,
        url=str(webhook_in.url),
        secret=generate_webhook_secret(),
        events=webhook_in.events,
    )
    
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    
    return webhook


@router.get("/{webhook_id}", response_model=OutboundWebhookResponse)
async def get_webhook(
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Get webhook details
    """
    webhook = db.query(OutboundWebhook).filter(
        OutboundWebhook.id == webhook_id,
        OutboundWebhook.user_id == current_user.id,
    ).first()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    return webhook


@router.patch("/{webhook_id}", response_model=OutboundWebhookResponse)
async def update_webhook(
    webhook_id: int,
    webhook_in: OutboundWebhookUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Update webhook
    """
    webhook = db.query(OutboundWebhook).filter(
        OutboundWebhook.id == webhook_id,
        OutboundWebhook.user_id == current_user.id,
    ).first()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    update_data = webhook_in.dict(exclude_unset=True)
    
    if "url" in update_data:
        update_data["url"] = str(update_data["url"])
    
    for field, value in update_data.items():
        setattr(webhook, field, value)
    
    db.commit()
    db.refresh(webhook)
    
    return webhook


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Delete webhook
    """
    webhook = db.query(OutboundWebhook).filter(
        OutboundWebhook.id == webhook_id,
        OutboundWebhook.user_id == current_user.id,
    ).first()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    db.delete(webhook)
    db.commit()


@router.post("/{webhook_id}/regenerate-secret", response_model=OutboundWebhookResponse)
async def regenerate_webhook_secret(
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Regenerate webhook signing secret
    """
    webhook = db.query(OutboundWebhook).filter(
        OutboundWebhook.id == webhook_id,
        OutboundWebhook.user_id == current_user.id,
    ).first()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    webhook.secret = generate_webhook_secret()
    db.commit()
    db.refresh(webhook)
    
    return webhook


@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Send test payload to webhook
    """
    webhook = db.query(OutboundWebhook).filter(
        OutboundWebhook.id == webhook_id,
        OutboundWebhook.user_id == current_user.id,
    ).first()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    # Send test webhook
    result = await notification_service.send_notification(
        NotificationType.WEBHOOK,
        webhook.url,
        "NovaSniper Test Webhook",
        "This is a test webhook payload from NovaSniper.",
        secret=webhook.secret,
        event="test",
    )
    
    if result.success:
        webhook.last_triggered = datetime.utcnow()
        webhook.success_count += 1
        db.commit()
        return {"status": "success", "message": "Test webhook delivered"}
    else:
        webhook.failure_count += 1
        db.commit()
        raise HTTPException(status_code=500, detail=f"Webhook failed: {result.error}")


@router.get("/{webhook_id}/stats")
async def get_webhook_stats(
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Get webhook delivery statistics
    """
    webhook = db.query(OutboundWebhook).filter(
        OutboundWebhook.id == webhook_id,
        OutboundWebhook.user_id == current_user.id,
    ).first()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    total = webhook.success_count + webhook.failure_count
    success_rate = (webhook.success_count / total * 100) if total > 0 else 0
    
    return {
        "webhook_id": webhook.id,
        "name": webhook.name,
        "total_deliveries": total,
        "successful": webhook.success_count,
        "failed": webhook.failure_count,
        "success_rate": round(success_rate, 2),
        "last_triggered": webhook.last_triggered,
    }
