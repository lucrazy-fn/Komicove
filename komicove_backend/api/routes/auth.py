from __future__ import annotations

import hmac
import os
import threading
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from komicove_backend.accounts import service as accounts
from komicove_backend.accounts import moderator_invites
from komicove_backend.accounts import account_actions
from komicove_backend.accounts.models import SessionToken, TotpRecoveryCode, User
from komicove_backend.accounts.security import hash_password, recovery_code_hash, verify_totp
from komicove_backend.api.deps import get_current_user, get_db
from komicove_backend.api.schemas import (
    AuthResponse,
    LoginRequest,
    ModeratorClaimRequest,
    RegisterRequest,
    UserPublic,
    AccountRecoveryRequest, PasswordResetConfirm, EmailVerificationConfirm,
)

router = APIRouter(prefix="/auth", tags=["auth"])
_attempts: dict[str, list[float]] = {}
_attempt_lock = threading.Lock()

def _public(user: User) -> UserPublic:
    return UserPublic(id=user.id, username=user.username,
        display_name=user.display_name or user.username,
        is_moderator=user.is_moderator, role=user.role,
        email_verified=bool(user.email_verified), totp_enabled=bool(user.totp_enabled))

def _valid_second_factor(db: Session, user: User, code: str | None) -> bool:
    if not code:
        return False
    if user.totp_secret and len(code.strip()) == 6 and verify_totp(user.totp_secret, code.strip()):
        return True
    row = db.scalar(select(TotpRecoveryCode).where(
        TotpRecoveryCode.user_id == user.id,
        TotpRecoveryCode.code_hash == recovery_code_hash(code),
        TotpRecoveryCode.used_at.is_(None),
    ))
    if row:
        from komicove_backend.accounts.models import _now
        row.used_at = _now()
        return True
    return False

def _check_login_limit(key: str):
    now=time.time()
    with _attempt_lock:
        recent=[stamp for stamp in _attempts.get(key,[]) if now-stamp < 900]
        _attempts[key]=recent
        if len(recent)>=5: raise HTTPException(429,"Muitas tentativas. Aguarde alguns minutos.")
        recent.append(now)


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)):
    return _public(user)


@router.post("/claim-moderator", response_model=UserPublic)
def claim_moderator(
    payload: ModeratorClaimRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pass
    if user.role in {"admin", "owner"}:
        return _public(user)
    from komicove_backend.config_env import setting
    expected = setting("KOMICOVE_MODERATOR_SETUP_TOKEN")
    master_matches = bool(expected) and hmac.compare_digest(payload.setup_token, expected)
    if not master_matches and user.role != "moderator":
        raise HTTPException(status_code=403, detail="Somente moderadores podem usar um token de administrador.")
    invite = None if master_matches else moderator_invites.consume(db, payload.setup_token)
    if not master_matches and invite is None:
        raise HTTPException(status_code=403, detail="Token de administrador inválido, expirado ou esgotado.")
    user.is_moderator = True
    user.role = "owner" if master_matches else "admin"
    db.flush()
    return _public(user)


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        result = accounts.register_user(
            db, username=payload.username, password=payload.password, email=payload.email
        )
    except (accounts.UsernameTakenError, accounts.EmailTakenError) as e:
        raise HTTPException(status_code=409, detail=str(e))

    accounts.record_access(result.user)
    if result.user.email:
        try:
            account_actions.send_verification(db, result.user)
        except Exception:
            pass
    return AuthResponse(
        token=result.token,
        user=_public(result.user),
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    key=f"{request.client.host if request.client else 'local'}:{payload.username.lower()}"
    _check_login_limit(key)
    try:
        result = accounts.authenticate(db, username=payload.username, password=payload.password)
    except (accounts.InvalidCredentialsError, accounts.AccountRestrictedError) as e:
        raise HTTPException(status_code=401, detail=str(e))
    if result.user.totp_enabled:
        if not _valid_second_factor(db, result.user, payload.totp_code):
            session = db.get(SessionToken,result.token)
            if session: db.delete(session)
            raise HTTPException(401,"Código de autenticação em duas etapas inválido.")

    with _attempt_lock: _attempts.pop(key,None)
    accounts.record_access(result.user)
    return AuthResponse(
        token=result.token,
        user=_public(result.user),
    )


@router.post("/password-recovery/request")
def request_password_recovery(payload: AccountRecoveryRequest, db: Session = Depends(get_db)):
    identifier = payload.identifier.strip().lower()
    user = db.scalar(select(User).where((User.username == identifier) | (User.email == identifier)))
    if user and user.email and user.is_active and not user.deleted_at:
        try:
            account_actions.send_password_reset(db, user)
        except Exception:
            pass
    return {"message": "Se a conta existir e tiver e-mail, enviaremos as instruções. / If the account exists and has an email, instructions will be sent."}


@router.post("/password-recovery/confirm")
def confirm_password_recovery(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    user = account_actions.consume(db, payload.token, "reset_password")
    if not user:
        raise HTTPException(400, "Código inválido ou expirado. / Invalid or expired code.")
    user.password_hash, user.password_salt = hash_password(payload.new_password)
    db.query(SessionToken).filter(SessionToken.user_id == user.id).delete()
    db.flush()
    return {"message": "Senha alterada. / Password changed."}


@router.post("/email/confirm")
def confirm_email(payload: EmailVerificationConfirm, db: Session = Depends(get_db)):
    user = account_actions.consume(db, payload.token, "verify_email")
    if not user:
        raise HTTPException(400, "Código inválido ou expirado. / Invalid or expired code.")
    user.email_verified = True
    db.flush()
    return {"message": "E-mail confirmado. / Email verified."}


@router.post("/logout", status_code=204)
def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    pass
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        accounts.logout(db, token)
    return None
