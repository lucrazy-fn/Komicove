from __future__ import annotations

import hmac
import os
import threading
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from panel_backend.accounts import service as accounts
from panel_backend.accounts import moderator_invites
from panel_backend.accounts.models import SessionToken, User
from panel_backend.accounts.security import verify_totp
from panel_backend.api.deps import get_current_user, get_db
from panel_backend.api.schemas import (
    AuthResponse,
    LoginRequest,
    ModeratorClaimRequest,
    RegisterRequest,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["auth"])
_attempts: dict[str, list[float]] = {}
_attempt_lock = threading.Lock()

def _check_login_limit(key: str):
    now=time.time()
    with _attempt_lock:
        recent=[stamp for stamp in _attempts.get(key,[]) if now-stamp < 900]
        _attempts[key]=recent
        if len(recent)>=5: raise HTTPException(429,"Muitas tentativas. Aguarde alguns minutos.")
        recent.append(now)


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)):
    pass
    return UserPublic(
        id=user.id,
        username=user.username,
        display_name=user.display_name or user.username,
        is_moderator=user.is_moderator,
        role=user.role,
    )


@router.post("/claim-moderator", response_model=UserPublic)
def claim_moderator(
    payload: ModeratorClaimRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pass
    if user.role in {"admin", "owner"}:
        return UserPublic(
            id=user.id, username=user.username,
            display_name=user.display_name or user.username,
            is_moderator=True, role=user.role,
        )
    expected = os.environ.get("PANEL_MODERATOR_SETUP_TOKEN", "")
    master_matches = bool(expected) and hmac.compare_digest(payload.setup_token, expected)
    if not master_matches and user.role != "moderator":
        raise HTTPException(status_code=403, detail="Somente moderadores podem usar um token de administrador.")
    invite = None if master_matches else moderator_invites.consume(db, payload.setup_token)
    if not master_matches and invite is None:
        raise HTTPException(status_code=403, detail="Token de administrador inválido, expirado ou esgotado.")
    user.is_moderator = True
    user.role = "owner" if master_matches else "admin"
    db.flush()
    return UserPublic(
        id=user.id, username=user.username,
        display_name=user.display_name or user.username,
        is_moderator=True, role=user.role,
    )


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        result = accounts.register_user(
            db, username=payload.username, password=payload.password, email=payload.email
        )
    except (accounts.UsernameTakenError, accounts.EmailTakenError) as e:
        raise HTTPException(status_code=409, detail=str(e))

    accounts.record_access(result.user)
    return AuthResponse(
        token=result.token,
        user=UserPublic(
            id=result.user.id, username=result.user.username,
            display_name=result.user.display_name or result.user.username,
            is_moderator=result.user.is_moderator,
            role=result.user.role,
        ),
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    key=f"{request.client.host if request.client else 'local'}:{payload.username.lower()}"
    _check_login_limit(key)
    try:
        result = accounts.authenticate(db, username=payload.username, password=payload.password)
    except (accounts.InvalidCredentialsError, accounts.AccountRestrictedError) as e:
        raise HTTPException(status_code=401, detail=str(e))
    if result.user.role in {"admin","owner"} and result.user.totp_enabled:
        if not payload.totp_code or not verify_totp(result.user.totp_secret,payload.totp_code):
            session = db.get(SessionToken,result.token)
            if session: db.delete(session)
            raise HTTPException(401,"Código de autenticação em duas etapas inválido.")

    with _attempt_lock: _attempts.pop(key,None)
    accounts.record_access(result.user)
    return AuthResponse(
        token=result.token,
        user=UserPublic(
            id=result.user.id, username=result.user.username,
            display_name=result.user.display_name or result.user.username,
            is_moderator=result.user.is_moderator,
            role=result.user.role,
        ),
    )


@router.post("/logout", status_code=204)
def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    pass
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        accounts.logout(db, token)
    return None
