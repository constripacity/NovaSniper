"""
NovaSniper v2.0 Notification Service
Multi-channel notifications: Email, Discord, Telegram, Pushover, SMS, Slack, Webhooks
"""
import asyncio
import hashlib
import hmac
import json
import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod

import httpx

from app.config import settings
from app.models import TrackedProduct, User, NotificationSetting, NotificationType

logger = logging.getLogger(__name__)


class NotificationResult:
    """Result of sending a notification"""
    def __init__(self, success: bool, channel: str, error: Optional[str] = None):
        self.success = success
        self.channel = channel
        self.error = error
        self.timestamp = datetime.utcnow()


class BaseNotifier(ABC):
    """Abstract base class for notification channels"""
    
    @abstractmethod
    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        product: Optional[TrackedProduct] = None,
        **kwargs
    ) -> NotificationResult:
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        pass


class EmailNotifier(BaseNotifier):
    """Email notifications via SMTP"""
    
    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.user = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.FROM_EMAIL
        self.use_tls = settings.SMTP_TLS
    
    def is_configured(self) -> bool:
        return all([self.host, self.user, self.password, self.from_email])
    
    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        product: Optional[TrackedProduct] = None,
        **kwargs
    ) -> NotificationResult:
        if not self.is_configured():
            return NotificationResult(False, "email", "SMTP not configured")
        
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = recipient
            
            # Plain text version
            text_part = MIMEText(message, "plain")
            msg.attach(text_part)
            
            # HTML version
            html_content = self._build_html(subject, message, product)
            html_part = MIMEText(html_content, "html")
            msg.attach(html_part)
            
            # Send in thread pool to not block
            await asyncio.get_event_loop().run_in_executor(
                None, self._send_email, recipient, msg
            )
            
            return NotificationResult(True, "email")
            
        except Exception as e:
            logger.exception(f"Email send error to {recipient}")
            return NotificationResult(False, "email", str(e))
    
    def _send_email(self, recipient: str, msg: MIMEMultipart):
        """Synchronous email send"""
        with smtplib.SMTP(self.host, self.port) as server:
            if self.use_tls:
                server.starttls()
            server.login(self.user, self.password)
            server.sendmail(self.from_email, recipient, msg.as_string())
    
    def _build_html(self, subject: str, message: str, product: Optional[TrackedProduct]) -> str:
        """Build HTML email template"""
        product_section = ""
        if product:
            product_section = f"""
            <div style="background: #f9f9f9; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <h3 style="margin: 0 0 10px 0;">{product.title or 'Product'}</h3>
                <p style="margin: 5px 0;"><strong>Current Price:</strong> ${product.current_price:.2f} {product.currency}</p>
                <p style="margin: 5px 0;"><strong>Target Price:</strong> ${product.target_price:.2f} {product.currency}</p>
                {f'<p style="margin: 5px 0;"><strong>Savings:</strong> ${(product.target_price - product.current_price):.2f}</p>' if product.current_price and product.current_price < product.target_price else ''}
                {f'<a href="{product.product_url}" style="display: inline-block; background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 10px;">View Product</a>' if product.product_url else ''}
            </div>
            """
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0; font-size: 24px;">🎯 NovaSniper</h1>
                <p style="margin: 5px 0 0 0; opacity: 0.9;">Price Alert</p>
            </div>
            <div style="border: 1px solid #e0e0e0; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">
                <h2 style="margin-top: 0;">{subject}</h2>
                <p>{message}</p>
                {product_section}
            </div>
            <div style="text-align: center; color: #666; font-size: 12px; margin-top: 20px;">
                <p>Sent by NovaSniper • <a href="#">Manage Alerts</a></p>
            </div>
        </body>
        </html>
        """


class DiscordNotifier(BaseNotifier):
    """Discord webhook notifications"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.DISCORD_WEBHOOK_URL
    
    def is_configured(self) -> bool:
        return bool(self.webhook_url)
    
    async def send(
        self,
        recipient: str,  # Can be webhook URL or ignored if using default
        subject: str,
        message: str,
        product: Optional[TrackedProduct] = None,
        **kwargs
    ) -> NotificationResult:
        webhook_url = recipient if recipient.startswith("https://discord.com") else self.webhook_url
        
        if not webhook_url:
            return NotificationResult(False, "discord", "Webhook URL not configured")
        
        try:
            embed = {
                "title": f"🎯 {subject}",
                "description": message,
                "color": 0x667eea,  # Purple
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {"text": "NovaSniper Price Tracker"},
            }
            
            if product:
                embed["fields"] = [
                    {"name": "Product", "value": product.title or "N/A", "inline": False},
                    {"name": "Current Price", "value": f"${product.current_price:.2f}" if product.current_price else "N/A", "inline": True},
                    {"name": "Target Price", "value": f"${product.target_price:.2f}", "inline": True},
                ]
                
                if product.current_price and product.current_price < product.target_price:
                    savings = product.target_price - product.current_price
                    embed["fields"].append({"name": "Savings", "value": f"${savings:.2f} 🎉", "inline": True})
                
                if product.image_url:
                    embed["thumbnail"] = {"url": product.image_url}
                
                if product.product_url:
                    embed["url"] = product.product_url
            
            payload = {"embeds": [embed]}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=payload)
                
                if response.status_code not in (200, 204):
                    return NotificationResult(False, "discord", f"HTTP {response.status_code}")
            
            return NotificationResult(True, "discord")
            
        except Exception as e:
            logger.exception("Discord notification error")
            return NotificationResult(False, "discord", str(e))


class TelegramNotifier(BaseNotifier):
    """Telegram Bot API notifications"""
    
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
    
    def is_configured(self) -> bool:
        return bool(self.bot_token)
    
    async def send(
        self,
        recipient: str,  # Telegram chat_id
        subject: str,
        message: str,
        product: Optional[TrackedProduct] = None,
        **kwargs
    ) -> NotificationResult:
        if not self.is_configured():
            return NotificationResult(False, "telegram", "Bot token not configured")
        
        try:
            text = f"🎯 *{self._escape_markdown(subject)}*\n\n{self._escape_markdown(message)}"
            
            if product:
                text += f"\n\n📦 *{self._escape_markdown(product.title or 'Product')}*"
                if product.current_price:
                    text += f"\n💰 Current: ${product.current_price:.2f}"
                text += f"\n🎯 Target: ${product.target_price:.2f}"
                
                if product.current_price and product.current_price < product.target_price:
                    savings = product.target_price - product.current_price
                    text += f"\n✨ Savings: ${savings:.2f}"
                
                if product.product_url:
                    text += f"\n\n[View Product]({product.product_url})"
            
            payload = {
                "chat_id": recipient,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{self.api_url}/sendMessage", json=payload)
                data = response.json()
                
                if not data.get("ok"):
                    return NotificationResult(False, "telegram", data.get("description", "Unknown error"))
            
            return NotificationResult(True, "telegram")
            
        except Exception as e:
            logger.exception("Telegram notification error")
            return NotificationResult(False, "telegram", str(e))
    
    def _escape_markdown(self, text: str) -> str:
        """Escape special Markdown characters"""
        chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in chars:
            text = text.replace(char, f"\\{char}")
        return text


class PushoverNotifier(BaseNotifier):
    """Pushover notifications"""
    
    def __init__(self):
        self.app_token = settings.PUSHOVER_APP_TOKEN
        self.api_url = "https://api.pushover.net/1/messages.json"
    
    def is_configured(self) -> bool:
        return bool(self.app_token)
    
    async def send(
        self,
        recipient: str,  # Pushover user key
        subject: str,
        message: str,
        product: Optional[TrackedProduct] = None,
        **kwargs
    ) -> NotificationResult:
        if not self.is_configured():
            return NotificationResult(False, "pushover", "App token not configured")
        
        try:
            payload = {
                "token": self.app_token,
                "user": recipient,
                "title": subject,
                "message": message,
                "priority": kwargs.get("priority", 0),
            }
            
            if product and product.product_url:
                payload["url"] = product.product_url
                payload["url_title"] = "View Product"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.api_url, data=payload)
                data = response.json()
                
                if data.get("status") != 1:
                    errors = data.get("errors", ["Unknown error"])
                    return NotificationResult(False, "pushover", ", ".join(errors))
            
            return NotificationResult(True, "pushover")
            
        except Exception as e:
            logger.exception("Pushover notification error")
            return NotificationResult(False, "pushover", str(e))


class TwilioSMSNotifier(BaseNotifier):
    """Twilio SMS notifications"""
    
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_FROM_NUMBER
        self.api_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json" if self.account_sid else None
    
    def is_configured(self) -> bool:
        return all([self.account_sid, self.auth_token, self.from_number])
    
    async def send(
        self,
        recipient: str,  # Phone number
        subject: str,
        message: str,
        product: Optional[TrackedProduct] = None,
        **kwargs
    ) -> NotificationResult:
        if not self.is_configured():
            return NotificationResult(False, "sms", "Twilio not configured")
        
        try:
            # Combine subject and message for SMS
            sms_text = f"🎯 {subject}\n{message}"
            
            if product:
                if product.current_price:
                    sms_text += f"\n${product.current_price:.2f}"
                if product.product_url:
                    sms_text += f"\n{product.product_url}"
            
            # Truncate if too long
            if len(sms_text) > 1600:
                sms_text = sms_text[:1597] + "..."
            
            payload = {
                "To": recipient,
                "From": self.from_number,
                "Body": sms_text,
            }
            
            auth = (self.account_sid, self.auth_token)
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.api_url, data=payload, auth=auth)
                
                if response.status_code not in (200, 201):
                    data = response.json()
                    return NotificationResult(False, "sms", data.get("message", f"HTTP {response.status_code}"))
            
            return NotificationResult(True, "sms")
            
        except Exception as e:
            logger.exception("Twilio SMS notification error")
            return NotificationResult(False, "sms", str(e))


class SlackNotifier(BaseNotifier):
    """Slack webhook notifications"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.SLACK_WEBHOOK_URL
    
    def is_configured(self) -> bool:
        return bool(self.webhook_url)
    
    async def send(
        self,
        recipient: str,  # Can be webhook URL or ignored
        subject: str,
        message: str,
        product: Optional[TrackedProduct] = None,
        **kwargs
    ) -> NotificationResult:
        webhook_url = recipient if recipient.startswith("https://hooks.slack.com") else self.webhook_url
        
        if not webhook_url:
            return NotificationResult(False, "slack", "Webhook URL not configured")
        
        try:
            blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"🎯 {subject}", "emoji": True}
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": message}
                }
            ]
            
            if product:
                fields = []
                if product.title:
                    fields.append({"type": "mrkdwn", "text": f"*Product:*\n{product.title}"})
                if product.current_price:
                    fields.append({"type": "mrkdwn", "text": f"*Current Price:*\n${product.current_price:.2f}"})
                fields.append({"type": "mrkdwn", "text": f"*Target Price:*\n${product.target_price:.2f}"})
                
                if product.current_price and product.current_price < product.target_price:
                    savings = product.target_price - product.current_price
                    fields.append({"type": "mrkdwn", "text": f"*Savings:*\n${savings:.2f} 🎉"})
                
                blocks.append({"type": "section", "fields": fields[:10]})  # Slack limit
                
                if product.product_url:
                    blocks.append({
                        "type": "actions",
                        "elements": [{
                            "type": "button",
                            "text": {"type": "plain_text", "text": "View Product"},
                            "url": product.product_url,
                            "style": "primary"
                        }]
                    })
            
            payload = {"blocks": blocks}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=payload)
                
                if response.status_code != 200:
                    return NotificationResult(False, "slack", f"HTTP {response.status_code}")
            
            return NotificationResult(True, "slack")
            
        except Exception as e:
            logger.exception("Slack notification error")
            return NotificationResult(False, "slack", str(e))


class WebhookNotifier(BaseNotifier):
    """Custom outbound webhook notifications"""
    
    def __init__(self):
        self.timeout = settings.WEBHOOK_TIMEOUT
        self.retry_attempts = settings.WEBHOOK_RETRY_ATTEMPTS
    
    def is_configured(self) -> bool:
        return True  # Always available
    
    async def send(
        self,
        recipient: str,  # Webhook URL
        subject: str,
        message: str,
        product: Optional[TrackedProduct] = None,
        secret: Optional[str] = None,
        **kwargs
    ) -> NotificationResult:
        if not recipient:
            return NotificationResult(False, "webhook", "Webhook URL required")
        
        try:
            payload = {
                "event": kwargs.get("event", "price_alert"),
                "timestamp": datetime.utcnow().isoformat(),
                "subject": subject,
                "message": message,
            }
            
            if product:
                payload["product"] = {
                    "id": product.id,
                    "platform": product.platform.value if product.platform else None,
                    "product_id": product.product_id,
                    "title": product.title,
                    "current_price": product.current_price,
                    "target_price": product.target_price,
                    "currency": product.currency,
                    "url": product.product_url,
                }
            
            headers = {"Content-Type": "application/json"}
            
            # Add HMAC signature if secret provided
            if secret:
                payload_str = json.dumps(payload, sort_keys=True)
                signature = hmac.new(
                    secret.encode(),
                    payload_str.encode(),
                    hashlib.sha256
                ).hexdigest()
                headers["X-NovaSniper-Signature"] = f"sha256={signature}"
            
            # Retry logic
            last_error = None
            for attempt in range(self.retry_attempts):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(recipient, json=payload, headers=headers)
                        
                        if response.status_code in (200, 201, 202, 204):
                            return NotificationResult(True, "webhook")
                        
                        last_error = f"HTTP {response.status_code}"
                        
                except httpx.TimeoutException:
                    last_error = "Timeout"
                except Exception as e:
                    last_error = str(e)
                
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
            return NotificationResult(False, "webhook", last_error)
            
        except Exception as e:
            logger.exception("Webhook notification error")
            return NotificationResult(False, "webhook", str(e))


class NotificationService:
    """Main notification service coordinating all channels"""
    
    def __init__(self):
        self.notifiers: Dict[NotificationType, BaseNotifier] = {
            NotificationType.EMAIL: EmailNotifier(),
            NotificationType.DISCORD: DiscordNotifier(),
            NotificationType.TELEGRAM: TelegramNotifier(),
            NotificationType.PUSHOVER: PushoverNotifier(),
            NotificationType.SMS: TwilioSMSNotifier(),
            NotificationType.SLACK: SlackNotifier(),
            NotificationType.WEBHOOK: WebhookNotifier(),
        }
    
    def get_notifier(self, notification_type: NotificationType) -> Optional[BaseNotifier]:
        return self.notifiers.get(notification_type)
    
    async def send_notification(
        self,
        notification_type: NotificationType,
        recipient: str,
        subject: str,
        message: str,
        product: Optional[TrackedProduct] = None,
        **kwargs
    ) -> NotificationResult:
        """Send notification via specified channel"""
        notifier = self.get_notifier(notification_type)
        if not notifier:
            return NotificationResult(False, notification_type.value, "Unknown notification type")
        
        return await notifier.send(recipient, subject, message, product, **kwargs)
    
    async def send_price_alert(
        self,
        product: TrackedProduct,
        user: Optional[User] = None,
        notification_settings: Optional[List[NotificationSetting]] = None,
    ) -> List[NotificationResult]:
        """Send price alert via all configured channels for a user"""
        results = []
        
        subject = f"Price Alert: {product.title or 'Product'} is now ${product.current_price:.2f}!"
        message = f"Your tracked product has dropped below your target price of ${product.target_price:.2f}."
        
        # If user has notification settings, use those
        if notification_settings:
            for setting in notification_settings:
                if not setting.is_enabled or not setting.notify_price_drop:
                    continue
                
                # Get recipient from config
                recipient = self._get_recipient(setting)
                if not recipient:
                    continue
                
                result = await self.send_notification(
                    setting.notification_type,
                    recipient,
                    subject,
                    message,
                    product
                )
                results.append(result)
        
        # Fallback to legacy email field
        elif product.notify_email:
            result = await self.send_notification(
                NotificationType.EMAIL,
                product.notify_email,
                subject,
                message,
                product
            )
            results.append(result)
        
        return results
    
    def _get_recipient(self, setting: NotificationSetting) -> Optional[str]:
        """Extract recipient from notification setting config"""
        config = setting.config or {}
        
        type_to_key = {
            NotificationType.EMAIL: "email",
            NotificationType.DISCORD: "webhook_url",
            NotificationType.TELEGRAM: "chat_id",
            NotificationType.PUSHOVER: "user_key",
            NotificationType.SMS: "phone_number",
            NotificationType.SLACK: "webhook_url",
            NotificationType.WEBHOOK: "url",
        }
        
        key = type_to_key.get(setting.notification_type)
        return config.get(key) if key else None
    
    def get_configured_channels(self) -> List[NotificationType]:
        """Get list of configured notification channels"""
        return [
            ntype for ntype, notifier in self.notifiers.items()
            if notifier.is_configured()
        ]


# Global instance
notification_service = NotificationService()
