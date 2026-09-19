
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from panel_backend.accounts.models import SessionToken, User
from panel_backend.accounts.models import _now
from panel_backend.accounts.security import hash_password, verify_password


class UsernameTakenError(Exception):
    pass


class EmailTakenError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class AccountRestrictedError(Exception):
    pass


@dataclass
class AuthResult:
    user: User
    token: str


def record_access(user: User) -> None:
    now = _now()
    if user.last_seen_at is None or (now - user.last_seen_at).total_seconds() >= 60:
        user.last_seen_at = now


def register_user(
    db: Session, *, username: str, password: str, email: str | None = None,
    display_name: str | None = None,
) -> AuthResult:
    username = username.strip().lower()
    email = email.strip().lower() if email else None
    existing = db.execute(
        select(User).where(func.lower(User.username) == username)
    ).scalar_one_or_none()
    if existing is not None:
        raise UsernameTakenError(f"Nome de usuário '{username}' já está em uso.")
    if email and db.execute(
        select(User).where(func.lower(User.email) == email)
    ).scalar_one_or_none() is not None:
        raise EmailTakenError("Este e-mail já está cadastrado.")

    password_hash, password_salt = hash_password(password)
    user = User(
        username=username,
        email=email,
        display_name=display_name or username,
        password_hash=password_hash,
        password_salt=password_salt,
    )
    db.add(user)
    db.flush()

    session_token = SessionToken(user_id=user.id)
    db.add(session_token)
    db.flush()

    return AuthResult(user=user, token=session_token.token)


def authenticate(db: Session, *, username: str, password: str) -> AuthResult:
    username = username.strip().lower()
    user = db.execute(
        select(User).where(func.lower(User.username) == username)
    ).scalar_one_or_none()
    if user is None:
        raise InvalidCredentialsError("Usuário ou senha inválidos.")
    if not verify_password(password, user.password_hash, user.password_salt):
        raise InvalidCredentialsError("Usuário ou senha inválidos.")
    if not user.is_active:
        reason = f" Motivo: {user.punishment_reason}" if user.punishment_reason else ""
        raise AccountRestrictedError(f"Esta conta foi banida.{reason}")
    if user.suspended_until and user.suspended_until > _now():
        reason = f" Motivo: {user.punishment_reason}" if user.punishment_reason else ""
        raise AccountRestrictedError(
            f"Conta suspensa até {user.suspended_until.strftime('%d/%m/%Y às %H:%M')} UTC.{reason}"
        )
    if user.suspended_until:
        user.suspended_until = None
        user.punishment_reason = None

    session_token = SessionToken(user_id=user.id)
    db.add(session_token)
    db.flush()

    return AuthResult(user=user, token=session_token.token)


def get_user_by_token(db: Session, token: str) -> User | None:
    session_token = db.get(SessionToken, token)
    if session_token is None or not session_token.is_valid():
        return None
    user = session_token.user
    if not user.is_active or (user.suspended_until and user.suspended_until > _now()):
        return None
    return user


def logout(db: Session, token: str) -> None:
    session_token = db.get(SessionToken, token)
    if session_token is not None:
        db.delete(session_token)
