from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from panel_backend.accounts.models import ModeratorInvite, User, _now


def token_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate(db: Session, creator: User, *, max_uses: int, valid_hours: int) -> tuple[ModeratorInvite, str]:
    raw_secret = "pnl_admin_" + secrets.token_urlsafe(32)
    invite = ModeratorInvite(
        token_hash=token_hash(raw_secret),
        created_by_user_id=creator.id,
        max_uses=max_uses,
        expires_at=_now() + timedelta(hours=valid_hours),
    )
    db.add(invite)
    db.flush()
    return invite, raw_secret


def consume(db: Session, raw_secret: str) -> ModeratorInvite | None:
    digest = token_hash(raw_secret)
    result = db.execute(update(ModeratorInvite).where(
        ModeratorInvite.token_hash == digest,
        ModeratorInvite.revoked.is_(False),
        ModeratorInvite.expires_at > _now(),
        ModeratorInvite.use_count < ModeratorInvite.max_uses,
    ).values(use_count=ModeratorInvite.use_count + 1)
      .execution_options(synchronize_session=False))
    if result.rowcount != 1:
        return None
    return db.scalar(select(ModeratorInvite).where(ModeratorInvite.token_hash == digest)
                     .execution_options(populate_existing=True))
