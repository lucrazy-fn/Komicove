from datetime import timedelta
import hashlib
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session
from komicove_backend.accounts import account_actions
from komicove_backend.accounts.models import AccountActionToken, LibraryState, Notification, SessionToken, TotpRecoveryCode, User, _now
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
        "totp_enabled":bool(user.totp_enabled)}

@router.patch("/profile", response_model=UserPublic)
def profile(body: ProfileUpdate, user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    email=body.email.strip().lower() if body.email else None
    if email and db.scalar(select(User).where(User.email==email, User.id!=user.id)):
        raise HTTPException(409,"Este e-mail já está cadastrado.")
    email_changed = email != user.email
    user.display_name=body.display_name.strip(); user.email=email
    if email_changed:
        user.email_verified=False
        db.execute(delete(AccountActionToken).where(AccountActionToken.user_id==user.id,
            AccountActionToken.purpose=="verify_email",AccountActionToken.used_at.is_(None)))
    db.flush()
    if email_changed and email:
        try: account_actions.send_verification(db,user)
        except Exception: pass
    return UserPublic(id=user.id,username=user.username,display_name=user.display_name,
        is_moderator=user.is_moderator,role=user.role,email_verified=user.email_verified,
        totp_enabled=user.totp_enabled)

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

@router.get("/library-state", response_model=list[LibraryStateItem])
def get_state(user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    return [LibraryStateItem(item_key=x.item_key,page=x.page,favorite=x.favorite,
            client_updated_at=float(x.client_updated_at or 0))
        for x in db.scalars(select(LibraryState).where(LibraryState.user_id==user.id)).all()]

@router.put("/library-state", response_model=list[LibraryStateItem])
def sync_state(body: LibrarySyncRequest,user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    existing={x.item_key:x for x in db.scalars(select(LibraryState).where(LibraryState.user_id==user.id)).all()}
    for incoming in body.items:
        row=existing.get(incoming.item_key)
        if row is None:
            row=LibraryState(user_id=user.id,item_key=incoming.item_key); db.add(row); existing[incoming.item_key]=row
        incoming_stamp = float(incoming.client_updated_at or 0)
        if (row.client_updated_at or 0) <= incoming_stamp:
            row.page=incoming.page; row.favorite=incoming.favorite
            row.client_updated_at=incoming_stamp; row.updated_at=_now()
    db.flush()
    return [LibraryStateItem(item_key=x.item_key,page=x.page,favorite=x.favorite,
            client_updated_at=float(x.client_updated_at or 0)) for x in existing.values()]
