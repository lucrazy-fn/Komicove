from datetime import timedelta
import hashlib
import re
import time
from io import BytesIO
from fastapi import APIRouter, Depends, File, Header, HTTPException, Response, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session
from komicove_backend.accounts import account_actions
from komicove_backend.accounts.models import AccountActionToken, LibraryState, LibraryStateAlias, Notification, SessionToken, TotpRecoveryCode, User, _now
from komicove_backend.accounts.security import hash_password, verify_password
from komicove_backend.accounts.security import (new_recovery_codes, new_totp_secret,
    recovery_code_hash, verify_totp)
from komicove_backend.api.deps import get_current_user, get_db
from komicove_backend.api.schemas import (LibraryStateItem, LibrarySyncRequest,
    NotificationPublic, PasswordChange, ProfileUpdate, TotpConfirm, TotpDisable, TotpSetup, UserPublic)

router = APIRouter(prefix="/account", tags=["account"])

@router.get("/profile")
def get_profile(user: User=Depends(get_current_user)):
    return {"username":user.username,"display_name":user.display_name or user.username,
        "email":user.email,"role":user.role,"email_verified":bool(user.email_verified),
        "totp_enabled":bool(user.totp_enabled),"bio":user.bio,
        "avatar_version":user.avatar_updated_at.isoformat() if user.avatar_updated_at else None}

@router.patch("/profile", response_model=UserPublic)
def profile(body: ProfileUpdate, user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    email=body.email.strip().lower() if body.email else None
    if email and db.scalar(select(User).where(User.email==email, User.id!=user.id)):
        raise HTTPException(409,"Este e-mail já está cadastrado.")
    email_changed = email != user.email
    user.display_name=body.display_name.strip(); user.email=email; user.bio=body.bio
    if email_changed:
        user.email_verified=False
        db.execute(delete(AccountActionToken).where(AccountActionToken.user_id==user.id,
            AccountActionToken.purpose=="verify_email",AccountActionToken.used_at.is_(None)))
    db.flush()
    if email_changed and email:
        try: account_actions.send_verification(db,user)
        except Exception: pass
    return UserPublic(id=user.id,username=user.username,display_name=user.display_name,
        email=user.email,is_moderator=user.is_moderator,role=user.role,email_verified=user.email_verified,
        totp_enabled=user.totp_enabled,bio=user.bio,
        avatar_version=user.avatar_updated_at.isoformat() if user.avatar_updated_at else None)

@router.get("/avatar")
def avatar(user: User=Depends(get_current_user)):
    if not user.avatar_data:
        raise HTTPException(404,"Avatar não configurado.")
    return Response(content=user.avatar_data,media_type=user.avatar_content_type or "image/jpeg",
                    headers={"Cache-Control":"private, no-cache"})

@router.put("/avatar")
async def update_avatar(avatar: UploadFile=File(...), user: User=Depends(get_current_user),
                        db: Session=Depends(get_db)):
    raw=await avatar.read(5*1024*1024+1)
    await avatar.close()
    if not raw or len(raw)>5*1024*1024:
        raise HTTPException(413,"A imagem deve ter no máximo 5 MB.")
    try:
        source=Image.open(BytesIO(raw))
        if source.width*source.height>25_000_000:
            raise HTTPException(413,"A imagem possui resolução grande demais.")
        source=ImageOps.exif_transpose(source).convert("RGB")
        source.thumbnail((512,512),Image.Resampling.LANCZOS)
        output=BytesIO()
        source.save(output,"JPEG",quality=88,optimize=True,progressive=True)
    except HTTPException:
        raise
    except (UnidentifiedImageError,OSError,ValueError):
        raise HTTPException(400,"Arquivo de imagem inválido.")
    user.avatar_data=output.getvalue()
    user.avatar_content_type="image/jpeg"
    user.avatar_updated_at=_now()
    db.flush()
    return {"avatar_version":user.avatar_updated_at.isoformat()}

@router.post("/email/resend")
def resend_email_verification(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if not user.email: raise HTTPException(400,"Adicione um e-mail à conta. / Add an email to your account.")
    if user.email_verified: return {"message":"E-mail já confirmado. / Email already verified."}
    try:
        delivered = account_actions.send_verification(db,user)
    except Exception:
        raise HTTPException(503,
            "O servidor de e-mail recusou o envio. Verifique o log do Render. / "
            "The mail server rejected delivery. Check the Render log.")
    if not delivered:
        raise HTTPException(503,
            "O envio de e-mail não está configurado no servidor. / "
            "Email delivery is not configured on the server.")
    return {"message":"Se o serviço de e-mail estiver disponível, enviamos um novo código. / A new code was sent if email delivery is available."}

@router.post("/password", status_code=204)
def change_password(body:PasswordChange,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if not verify_password(body.current_password,user.password_hash,user.password_salt):
        raise HTTPException(400,"A senha atual está incorreta.")
    user.password_hash,user.password_salt=hash_password(body.new_password)
    for session in db.scalars(select(SessionToken).where(SessionToken.user_id==user.id)).all(): db.delete(session)
    db.flush()

@router.post("/2fa/setup")
def setup_2fa(body:TotpSetup, user:User=Depends(get_current_user),db:Session=Depends(get_db),
              authorization:str=Header(...)):
    if not verify_password(body.current_password,user.password_hash,user.password_salt):
        raise HTTPException(403,"A senha atual está incorreta. / Current password is incorrect.")
    if user.totp_enabled and (not user.totp_secret or not body.current_code or
                             not verify_totp(user.totp_secret,body.current_code)):
        raise HTTPException(403,"Informe o código do autenticador atual. / Enter the current authenticator code.")
    secret=new_totp_secret()
    result=db.execute(update(User).where(User.id==user.id,
        User.totp_secret==user.totp_secret, User.totp_enabled==user.totp_enabled,
        User.password_hash==user.password_hash).values(
            totp_pending_secret=secret,
            totp_pending_session=hashlib.sha256(authorization.encode()).hexdigest(),
            totp_pending_expires_at=_now()+timedelta(minutes=10)))
    if result.rowcount != 1: raise HTTPException(409,"A segurança da conta mudou. Tente novamente. / Account security changed. Try again.")
    return {"secret":secret,"otpauth_url":f"otpauth://totp/Komicove:{user.username}?secret={secret}&issuer=Komicove"}

@router.post("/2fa/confirm")
def confirm_2fa(body:TotpConfirm,user:User=Depends(get_current_user),db:Session=Depends(get_db),
                authorization:str=Header(...)):
    pending=user.totp_pending_secret
    session_hash=hashlib.sha256(authorization.encode()).hexdigest()
    if (not pending or user.totp_pending_session!=session_hash or
        not user.totp_pending_expires_at or user.totp_pending_expires_at<=_now() or
        not verify_totp(pending,body.code)):
        raise HTTPException(400,"Configuração expirada ou código inválido. / Setup expired or code is invalid.")
    result=db.execute(update(User).where(User.id==user.id,User.totp_pending_secret==pending,
        User.totp_pending_session==session_hash,User.totp_pending_expires_at>_now()).values(
            totp_secret=pending,totp_enabled=True,totp_pending_secret=None,
            totp_pending_session=None,totp_pending_expires_at=None))
    if result.rowcount!=1: raise HTTPException(409,"A configuração mudou. Tente novamente. / Setup changed. Try again.")
    db.execute(delete(TotpRecoveryCode).where(TotpRecoveryCode.user_id==user.id))
    codes=new_recovery_codes()
    for code in codes:
        db.add(TotpRecoveryCode(user_id=user.id,code_hash=recovery_code_hash(code)))
    token=authorization.removeprefix("Bearer ").strip()
    db.execute(delete(SessionToken).where(SessionToken.user_id==user.id,SessionToken.token!=token))
    db.flush()
    return {"recovery_codes":codes}

@router.post("/2fa/disable")
def disable_2fa(body:TotpDisable,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if not verify_password(body.current_password,user.password_hash,user.password_salt):
        raise HTTPException(403,"A senha atual está incorreta. / Current password is incorrect.")
    valid=bool(user.totp_secret and len(body.code.strip())==6 and verify_totp(user.totp_secret,body.code))
    if not valid:
        recovery=db.scalar(select(TotpRecoveryCode).where(TotpRecoveryCode.user_id==user.id,
            TotpRecoveryCode.code_hash==recovery_code_hash(body.code),TotpRecoveryCode.used_at.is_(None)))
        valid=recovery is not None
    if not valid: raise HTTPException(403,"Código inválido. / Invalid code.")
    user.totp_enabled=False; user.totp_secret=None; user.totp_pending_secret=None
    user.totp_pending_session=None; user.totp_pending_expires_at=None
    db.execute(delete(TotpRecoveryCode).where(TotpRecoveryCode.user_id==user.id))
    db.execute(delete(SessionToken).where(SessionToken.user_id==user.id))
    db.flush()
    return {"message":"2FA desativado. Entre novamente. / 2FA disabled. Sign in again."}

@router.get("/notifications", response_model=list[NotificationPublic])
def notifications(user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    return db.scalars(select(Notification).where(Notification.user_id==user.id)
        .order_by(Notification.created_at.desc()).limit(100)).all()

@router.post("/notifications/{notification_id}/read", status_code=204)
def read_notification(notification_id: str,user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    item=db.get(Notification,notification_id)
    if not item or item.user_id!=user.id: raise HTTPException(404,"Notificação não encontrada.")
    item.read_at=_now(); db.flush()


def _session_id(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


@router.get("/sessions")
def active_sessions(authorization: str = Header(...), user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    current = authorization.removeprefix("Bearer ").strip()
    rows = db.scalars(select(SessionToken).where(SessionToken.user_id == user.id)
                      .order_by(SessionToken.created_at.desc())).all()
    for row in rows:
        if row.token == current:
            row.last_seen_at = _now()
    return [{
        "id": _session_id(row.token),
        "device_name": row.device_name or "Komicove",
        "created_at": row.created_at,
        "last_seen_at": row.last_seen_at,
        "expires_at": row.expires_at,
        "current": row.token == current,
    } for row in rows]


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(session_id: str, authorization: str = Header(...),
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current = authorization.removeprefix("Bearer ").strip()
    for row in db.scalars(select(SessionToken).where(SessionToken.user_id == user.id)).all():
        if _session_id(row.token) == session_id:
            if row.token == current:
                raise HTTPException(400, "Não é possível encerrar a sessão atual aqui. / "
                                         "The current session cannot be ended here.")
            db.delete(row)
            db.flush()
            return None
    raise HTTPException(404, "Sessão não encontrada. / Session not found.")

def _library_rows(db, user_id):
    rows = {x.item_key: x for x in db.scalars(select(LibraryState).where(LibraryState.user_id == user_id)).all()}
    aliases = {x.legacy_key: x for x in db.scalars(select(LibraryStateAlias).where(LibraryStateAlias.user_id == user_id)).all()}
    return rows, aliases


def _library_response(rows, aliases):
    result = []
    for key, row in [(key, row) for key, row in rows.items()] + [
            (key, rows[alias.item_key]) for key, alias in aliases.items() if alias.item_key in rows]:
        result.append(LibraryStateItem(item_key=key, page=row.page, favorite=row.favorite,
                                      client_updated_at=float(row.client_updated_at or 0)))
    return result


@router.get("/library-state", response_model=list[LibraryStateItem])
def get_state(user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    return _library_response(*_library_rows(db, user.id))


@router.put("/library-state", response_model=list[LibraryStateItem])
def sync_state(body: LibrarySyncRequest, user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    """Merge portable v2 state while retaining v1 file and URI aliases."""
    # Serialize this account's read/merge/write transaction on SQLite and PostgreSQL.
    db.execute(update(User).where(User.id == user.id).values(id=User.id))
    existing, aliases = _library_rows(db, user.id)
    for incoming in body.items:
        if incoming.legacy_keys and (not re.fullmatch(r"[0-9a-f]{64}", incoming.item_key) or
                any(not re.fullmatch(r"(?:uri-)?[0-9a-f]{64}", key) for key in incoming.legacy_keys)):
            raise HTTPException(422, "Alias de identidade inválido.")
        key = aliases[incoming.item_key].item_key if incoming.item_key in aliases else incoming.item_key
        row = existing.get(key)
        migration_keys = set(incoming.legacy_keys) - {key}
        # A URI may already point at the v1 file hash. Only redirect that root
        # when the client also supplies it as part of the same content migration.
        for legacy in migration_keys:
            known = aliases.get(legacy)
            if known is not None and known.item_key != key and known.item_key not in migration_keys:
                raise HTTPException(409, "A identidade antiga já pertence a outra HQ.")
        for known in aliases.values():
            if known.item_key in migration_keys:
                known.item_key = key
        for legacy in sorted(migration_keys):
            known = aliases.get(legacy)
            if known is None:
                known = LibraryStateAlias(user_id=user.id, legacy_key=legacy, item_key=key)
                db.add(known)
                aliases[legacy] = known
            old = existing.pop(legacy, None)
            if old is not None:
                if row is None:
                    old.item_key = key
                    existing[key] = row = old
                else:
                    if (old.client_updated_at or 0) > (row.client_updated_at or 0):
                        row.page, row.favorite, row.client_updated_at = old.page, old.favorite, old.client_updated_at
                    elif (old.client_updated_at or 0) == (row.client_updated_at or 0) == 0:
                        pages = [x for x in (row.page, old.page) if x is not None]
                        row.page = max(pages) if pages else None
                        row.favorite = row.favorite or old.favorite
                    db.delete(old)
        stamp = float(incoming.client_updated_at) if incoming.client_updated_at is not None else time.time()
        if row is None:
            row = LibraryState(user_id=user.id, item_key=key, page=incoming.page,
                               favorite=incoming.favorite, client_updated_at=stamp)
            db.add(row)
            existing[key] = row
        elif stamp > (row.client_updated_at or 0):
            # Null represents a device with no reading progress, never an erase.
            if incoming.page is not None:
                row.page = incoming.page
            row.favorite = incoming.favorite
            row.client_updated_at = stamp
            row.updated_at = _now()
        elif stamp == (row.client_updated_at or 0) == 0:
            # Bootstrap legacy untimestamped state without losing saved values.
            pages = [x for x in (row.page, incoming.page) if x is not None]
            row.page = max(pages) if pages else None
            row.favorite = row.favorite or incoming.favorite
    db.flush()
    return _library_response(existing, aliases)
