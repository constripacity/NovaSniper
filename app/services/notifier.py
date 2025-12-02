from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from app.config import Settings

logger = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send_price_alert(
        self,
        to_email: str,
        product_title: str,
        platform: str,
        current_price: float,
        currency: str,
        product_url: str,
    ) -> None:
        if not (self.settings.smtp_host and self.settings.smtp_port and self.settings.from_email):
            logger.warning("SMTP settings are incomplete; skipping email notification")
            return

        message = EmailMessage()
        message["Subject"] = f"Price alert for {product_title}"
        message["From"] = self.settings.from_email
        message["To"] = to_email
        body = (
            f"Good news! The {platform} product '{product_title}' is now priced at {current_price} {currency}.\n\n"
            f"Visit the product page: {product_url}\n\n"
            "This alert is sent so you can review and purchase manually."
        )
        message.set_content(body)

        logger.info("Sending email notification to %s", to_email)

        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as server:
            if self.settings.smtp_user and self.settings.smtp_password:
                server.starttls()
                server.login(self.settings.smtp_user, self.settings.smtp_password)
            server.send_message(message)
