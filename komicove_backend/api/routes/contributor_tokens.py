from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from komicove_backend.accounts import audit, contributor_invites
from komicove_backend.accounts.models import ContributorInvite, User, _now
from komicove_backend.api.deps import get_db, get_current_user, require_moderator
from komicove_backend.api.routes.auth import _public
from komicove_backend.api.schemas import ContributorClaim, ContributorInviteCreate, ContributorInviteCreated, ContributorInvitePublic, UserPublic

router = APIRouter(tags=["contributor-tokens"])


def public(invite):
    status = "used" if invite.used_at else "revoked" if invite.revoked_at else "expired" if invite.expires_at <= _now() else "available"
    return ContributorInvitePublic(id=invite.id, status=status, created_by_username=invite.created_by_username,
        created_at=invite.created_at, expires_at=invite.expires_at, revoked_at=invite.revoked_at,
        used_at=invite.used_at, used_by_user_id=invite.used_by_user_id, used_by_username=invite.used_by_username)


@router.post("/api/contributor-tokens", response_model=ContributorInviteCreated, status_code=201)
def create(payload: ContributorInviteCreate, response: Response, actor: User = Depends(require_moderator), db: Session = Depends(get_db)):
    invite, secret = contributor_invites.generate(db, actor, payload.valid_hours)
    audit.record(db, actor, "contributor_token_created", details=f"convite {invite.id}")
    response.headers["Cache-Control"] = "no-store"
    return ContributorInviteCreated(**public(invite).model_dump(), secret=secret)


@router.get("/api/contributor-tokens", response_model=list[ContributorInvitePublic])
def history(actor: User = Depends(require_moderator), db: Session = Depends(get_db), offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    return [public(i) for i in db.scalars(select(ContributorInvite).order_by(ContributorInvite.created_at.desc(), ContributorInvite.id).offset(offset).limit(limit))]


@router.delete("/api/contributor-tokens/{invite_id}", status_code=204)
def revoke(invite_id: str, actor: User = Depends(require_moderator), db: Session = Depends(get_db)):
    result = db.execute(update(ContributorInvite).where(ContributorInvite.id == invite_id,
        ContributorInvite.used_at.is_(None), ContributorInvite.revoked_at.is_(None)).values(revoked_at=_now()))
    if result.rowcount == 1:
        audit.record(db, actor, "contributor_token_revoked", details=f"convite {invite_id}")
    else:
        invite = db.get(ContributorInvite, invite_id)
        if not invite:
            raise HTTPException(404, "Token não encontrado.")
        if invite.used_at:
            raise HTTPException(409, "O token já foi utilizado.")


@router.post("/account/contributor-token", response_model=UserPublic)
def redeem(payload: ContributorClaim, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "user":
        raise HTTPException(409, "Esta conta já possui um cargo. O token não foi consumido.")
    invite = contributor_invites.consume(db, user, payload.token.strip())
    if invite is None:
        raise HTTPException(400, "Token de Contribuidor inválido, expirado, revogado ou utilizado.")
    audit.record(db, user, "contributor_token_used", target=user, details=f"convite {invite.id}")
    return _public(user)
