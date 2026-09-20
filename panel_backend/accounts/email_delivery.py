from __future__ import annotations

import os
import smtplib
import logging
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def send_account_email(to_address: str, subject: str, text: str) -> bool:
    """Send account mail through optional SMTP; fail closed without leaking tokens."""
    host = os.environ.get("PANEL_SMTP_HOST", "").strip()
    sender = os.environ.get("PANEL_SMTP_FROM", "").strip()
    if not host or not sender:
        return False
    port = int(os.environ.get("PANEL_SMTP_PORT", "587"))
    username = os.environ.get("PANEL_SMTP_USERNAME", "").strip()
    password = os.environ.get("PANEL_SMTP_PASSWORD", "").strip()
    # Google displays app passwords grouped with spaces. Those spaces are not
    # part of the credential and commonly get copied into environment values.
    if host.lower() in {"smtp.gmail.com", "smtp.googlemail.com"}:
        password = password.replace(" ", "")
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = sender, to_address, subject
    message.set_content(text)
    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.ehlo()
            if os.environ.get("PANEL_SMTP_STARTTLS", "1") != "0":
                smtp.starttls()
                smtp.ehlo()
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
    except Exception as exc:
        # Never log the recipient, message, token, password or SMTP response
        # body. The exception type is enough to diagnose configuration,
        # authentication and connectivity failures safely.
        logger.error("Account email delivery failed via %s:%s (%s)",
                     host, port, type(exc).__name__)
        raise
    return True
