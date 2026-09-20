from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def send_account_email(to_address: str, subject: str, text: str) -> bool:
    """Send account mail through optional SMTP; fail closed without leaking tokens."""
    host = os.environ.get("PANEL_SMTP_HOST", "").strip()
    sender = os.environ.get("PANEL_SMTP_FROM", "").strip()
    if not host or not sender:
        return False
    port = int(os.environ.get("PANEL_SMTP_PORT", "587"))
    username = os.environ.get("PANEL_SMTP_USERNAME", "")
    password = os.environ.get("PANEL_SMTP_PASSWORD", "")
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = sender, to_address, subject
    message.set_content(text)
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        if os.environ.get("PANEL_SMTP_STARTTLS", "1") != "0":
            smtp.starttls()
        if username:
            smtp.login(username, password)
        smtp.send_message(message)
    return True
