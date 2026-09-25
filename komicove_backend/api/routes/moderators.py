from __future__ import annotations

import secrets
from datetime import timedelta
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from komicove_backend.accounts import audit
from komicove_backend.accounts.models import AdminAuditLog, ModeratorInvite, Notification, User, _now
from komicove_backend.accounts.security import hash_password
from komicove_backend.api.deps import get_db, require_admin
from komicove_backend.api.schemas import (AuditLogPublic, ManagedPublicationPublic,
    ManagedUserDetail, ManagedUserPublic, ManagedUserUpdate, ModeratorDashboard)
from komicove_backend.catalog.models import Comic, Publication

router = APIRouter(tags=["moderators"])
_PAGE = Path(__file__).resolve().parents[2] / "web" / "moderators.html"

def _public(u: User) -> ManagedUserPublic:
    return ManagedUserPublic(id=u.id, username=u.username, display_name=u.display_name or u.username,
        email=u.email, is_active=u.is_active, is_moderator=u.is_moderator, role=u.role,
        suspended_until=u.suspended_until, punishment_reason=u.punishment_reason,
        deleted_at=u.deleted_at, created_at=u.created_at, last_seen_at=u.last_seen_at)

def _audit_public(item: AdminAuditLog) -> AuditLogPublic:
    return AuditLogPublic(id=item.id, actor_username=item.actor_username,
        target_username=item.target_username, action=item.action, reason=item.reason,
        details=item.details, created_at=item.created_at)

def _revoke(db: Session, user: User):
    for item in list(user.sessions): db.delete(item)

def _can_manage(actor: User, target: User):
    if actor.id == target.id: raise HTTPException(409, "Você não pode executar esta ação na própria conta.")
    if target.role == "owner": raise HTTPException(403, "A conta do dono não pode ser alterada.")
    if actor.role == "admin" and target.role == "admin":
        raise HTTPException(403, "Administradores não podem alterar outros administradores.")

@router.get("/moderators", response_class=HTMLResponse, include_in_schema=False)
def page(): return HTMLResponse(_PAGE.read_text(encoding="utf-8"))

@router.get("/api/moderators/dashboard", response_model=ModeratorDashboard)
def dashboard(_actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    now = _now()
    def count(*filters):
        return db.scalar(select(func.count()).select_from(User).where(User.deleted_at.is_(None), *filters)) or 0
    return ModeratorDashboard(total_users=count(),
        active_users=count(User.is_active.is_(True), (User.suspended_until.is_(None) | (User.suspended_until <= now))),
        suspended_users=count(User.is_active.is_(True), User.suspended_until > now),
        banned_users=count(User.is_active.is_(False)),
        moderators=count(User.role.in_(["moderator", "admin", "owner"])),
        pending_publications=db.scalar(select(func.count()).select_from(Publication).where(Publication.status == "pending_review")) or 0,
        active_invites=db.scalar(select(func.count()).select_from(ModeratorInvite).where(
            ModeratorInvite.revoked.is_(False), ModeratorInvite.use_count < ModeratorInvite.max_uses,
            ModeratorInvite.expires_at > now)) or 0)

@router.get("/api/moderators/users", response_model=list[ManagedUserPublic])
def users(_actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [_public(u) for u in db.scalars(select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc())).all()]

@router.get("/api/moderators/users/{user_id}/detail", response_model=ManagedUserDetail)
def detail(user_id: str, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target or target.deleted_at: raise HTTPException(404, "Conta não encontrada.")
    if actor.role == "admin" and target.role in {"admin", "owner"} and actor.id != target.id:
        raise HTTPException(403, "Administradores não podem consultar outros administradores.")
    rows = db.execute(select(Publication, Comic).join(Comic, Comic.id == Publication.comic_id)
        .where(Publication.user_id == target.id).order_by(Publication.created_at.desc()).limit(100)).all()
    pubs = [ManagedPublicationPublic(publication_id=p.id, title=c.title, status=p.status, created_at=p.created_at) for p,c in rows]
    actions = db.scalars(select(AdminAuditLog).where(AdminAuditLog.target_user_id == target.id)
        .order_by(AdminAuditLog.created_at.desc()).limit(30)).all()
    return ManagedUserDetail(user=_public(target), total_publications=len(pubs),
        approved_publications=sum(x.status == "approved" for x in pubs),
        rejected_publications=sum(x.status == "rejected" for x in pubs),
        pending_publications=sum(x.status == "pending_review" for x in pubs),
        publications=pubs, recent_actions=[_audit_public(item) for item in actions])

@router.patch("/api/moderators/users/{user_id}", response_model=ManagedUserPublic)
def update(user_id: str, body: ManagedUserUpdate, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target or target.deleted_at: raise HTTPException(404, "Conta não encontrada.")
    _can_manage(actor, target)
    if body.action == "set_role":
        if actor.role != "owner": raise HTTPException(403, "Somente o dono pode alterar cargos.")
        if not body.role: raise HTTPException(422, "Informe o novo cargo.")
        old = target.role; target.role = body.role; target.is_moderator = body.role != "user"
        if not target.is_moderator: _revoke(db, target)
        audit.record(db, actor, "role_changed", target=target, details=f"{old} -> {target.role}")
    elif body.action == "suspend":
        if not body.duration_hours: raise HTTPException(422, "Informe a duração da suspensão.")
        target.suspended_until = _now() + timedelta(hours=body.duration_hours)
        target.punishment_reason = (body.reason or "Suspensão aplicada pela administração.").strip(); _revoke(db,target)
        db.add(Notification(user_id=target.id,title="Conta suspensa",
            message=f"Suspensa por {body.duration_hours} hora(s). Motivo: {target.punishment_reason}",kind="punishment"))
        audit.record(db,actor,"user_suspended",target=target,reason=target.punishment_reason,details=f"{body.duration_hours} hora(s)")
    elif body.action == "ban":
        target.is_active=False; target.suspended_until=None
        target.punishment_reason=(body.reason or "Banimento aplicado pela administração.").strip(); _revoke(db,target)
        db.add(Notification(user_id=target.id,title="Conta banida",
            message=f"Motivo: {target.punishment_reason}",kind="punishment"))
        audit.record(db,actor,"user_banned",target=target,reason=target.punishment_reason)
    elif body.action == "clear_punishment":
        target.is_active=True; target.suspended_until=None; target.punishment_reason=None
        audit.record(db,actor,"punishment_cleared",target=target)
    else:
        _revoke(db,target); audit.record(db,actor,"sessions_revoked",target=target,reason=body.reason)
    db.flush(); return _public(target)

@router.delete("/api/moderators/users/{user_id}", status_code=204)
def delete(user_id: str, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    target=db.get(User,user_id)
    if not target or target.deleted_at: raise HTTPException(404,"Conta não encontrada.")
    _can_manage(actor,target); audit.record(db,actor,"user_deleted",target=target)
    suffix=target.id.replace("-","")[:12]; target.password_hash,target.password_salt=hash_password(secrets.token_urlsafe(32))
    target.username=f"deleted_{suffix}"; target.email=None; target.display_name="Conta excluída"
    target.is_active=False; target.is_moderator=False; target.role="user"; target.suspended_until=None
    target.punishment_reason=None; target.deleted_at=_now(); _revoke(db,target); db.flush()

@router.get("/api/moderators/audit", response_model=list[AuditLogPublic])
def audit_rows(_actor: User=Depends(require_admin), db: Session=Depends(get_db)):
    rows = db.scalars(select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(250)).all()
    return [_audit_public(item) for item in rows]
