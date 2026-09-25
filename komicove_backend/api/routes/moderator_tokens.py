from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from komicove_backend.accounts import audit, moderator_invites
from komicove_backend.accounts.models import ModeratorInvite, User
from komicove_backend.api.deps import get_db, require_admin
from komicove_backend.api.schemas import (
    ModeratorInviteCreateRequest,
    ModeratorInviteCreated,
    ModeratorInviteSummary,
)

router = APIRouter(tags=["moderator-tokens"])
@router.get("/moderator-tokens", include_in_schema=False)
def page():
    return RedirectResponse("/moderators", status_code=307)


@router.post("/api/moderator-tokens", response_model=ModeratorInviteCreated)
def create_invite(
    payload: ModeratorInviteCreateRequest,
    moderator: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    invite, secret = moderator_invites.generate(
        db, moderator, max_uses=payload.max_uses, valid_hours=payload.valid_hours
    )
    audit.record(db, moderator, "invite_created", details=f"{invite.max_uses} uso(s), {payload.valid_hours} hora(s)")
    return ModeratorInviteCreated(
        id=invite.id, secret=secret, max_uses=invite.max_uses,
        use_count=invite.use_count, expires_at=invite.expires_at,
    )


@router.get("/api/moderator-tokens", response_model=list[ModeratorInviteSummary])
def list_invites(
    _moderator: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(ModeratorInvite).order_by(ModeratorInvite.created_at.desc())
    ).all()


@router.delete("/api/moderator-tokens/{invite_id}", status_code=204)
def revoke_invite(
    invite_id: str,
    moderator: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    invite = db.get(ModeratorInvite, invite_id)
    if invite is None:
        raise HTTPException(status_code=404, detail="Convite não encontrado.")
    invite.revoked = True
    audit.record(db, moderator, "invite_revoked", details=f"convite {invite.id}")
    db.flush()
    return None
