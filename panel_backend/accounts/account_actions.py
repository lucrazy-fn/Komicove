from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from panel_backend.accounts.email_delivery import send_account_email
from panel_backend.accounts.models import AccountActionToken, User, _now


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue(db: Session, user: User, purpose: str, minutes: int) -> str:
    db.execute(delete(AccountActionToken).where(
        AccountActionToken.user_id == user.id,
        AccountActionToken.purpose == purpose,
        AccountActionToken.used_at.is_(None),
    ))
    token = secrets.token_urlsafe(32)
    db.add(AccountActionToken(user_id=user.id, purpose=purpose, token_hash=_hash(token),
                              expires_at=_now() + timedelta(minutes=minutes)))
    db.flush()
    return token


def consume(db: Session, raw_token: str, purpose: str) -> User | None:
    row = db.scalar(select(AccountActionToken).where(
        AccountActionToken.token_hash == _hash(raw_token),
        AccountActionToken.purpose == purpose,
        AccountActionToken.used_at.is_(None),
        AccountActionToken.expires_at > _now(),
    ))
    if not row:
        return None
    row.used_at = _now()
    return db.get(User, row.user_id)


def send_verification(db: Session, user: User) -> bool:
    if not user.email:
        return False
    token = issue(db, user, "verify_email", 24 * 60)
    return send_account_email(user.email, "PANEL - confirme seu e-mail / verify your email",
        "PT: Cole este código no PANEL para confirmar seu e-mail:\n\n"
        f"{token}\n\nEN: Paste this code into PANEL to verify your email.\n"
        "O código expira em 24 horas / The code expires in 24 hours.")


def send_password_reset(db: Session, user: User) -> bool:
    if not user.email:
        return False
    token = issue(db, user, "reset_password", 30)
    return send_account_email(user.email, "PANEL - recuperação de senha / password recovery",
        "PT: Cole este código no PANEL para criar uma nova senha:\n\n"
        f"{token}\n\nEN: Paste this code into PANEL to create a new password.\n"
        "O código expira em 30 minutos / The code expires in 30 minutes.")
