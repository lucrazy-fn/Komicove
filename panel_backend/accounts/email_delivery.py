from __future__ import annotations

import os
import smtplib
import logging
import json
from email.message import EmailMessage
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


def send_account_email(to_address: str, subject: str, text: str) -> bool:
    """Send account mail through optional SMTP; fail closed without leaking tokens."""
    sender = (os.environ.get("PANEL_EMAIL_FROM", "").strip()
              or os.environ.get("PANEL_SMTP_FROM", "").strip())
    brevo_key = os.environ.get("PANEL_BREVO_API_KEY", "").strip()
    if not sender:
        return False

    # Free Render services block outbound SMTP ports. Brevo's transactional
    # HTTPS API works over port 443 and is therefore the preferred provider
    # when PANEL_BREVO_API_KEY is configured.
    if brevo_key:
        payload = json.dumps({
            "sender": {
                "name": os.environ.get("PANEL_EMAIL_FROM_NAME", "PANEL").strip() or "PANEL",
                "email": sender,
            },
            "to": [{"email": to_address}],
            "subject": subject,
            "textContent": text,
        }).encode("utf-8")
        request = Request(
            "https://api.brevo.com/v3/smtp/email",
            data=payload,
            method="POST",
            headers={
                "accept": "application/json",
                "api-key": brevo_key,
                "content-type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=15) as response:
                if response.status < 200 or response.status >= 300:
                    raise OSError(f"Brevo returned HTTP {response.status}")
        except Exception as exc:
            logger.error("Account email delivery failed via Brevo HTTPS API (%s)",
                         type(exc).__name__)
            raise
        return True

    host = os.environ.get("PANEL_SMTP_HOST", "").strip()
    if not host:
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
