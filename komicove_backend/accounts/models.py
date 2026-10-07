
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from komicove_backend.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:


    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(160), nullable=True)
    avatar_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    avatar_content_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    avatar_updated_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    password_hash: Mapped[str] = mapped_column(String(255))
    password_salt: Mapped[str] = mapped_column(String(64))

    is_active: Mapped[bool] = mapped_column(default=True)
    is_moderator: Mapped[bool] = mapped_column(default=False, index=True)
    role: Mapped[str] = mapped_column(String(16), default="user", index=True)
    suspended_until: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True, index=True)
    punishment_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_pending_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_pending_session: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_pending_expires_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    sessions: Mapped[list["SessionToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class SessionToken(Base):
    pass
    __tablename__ = "session_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uuid.uuid4().hex + uuid.uuid4().hex)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(), default=lambda: _now() + timedelta(days=30)
    )
    device_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")

    def is_valid(self) -> bool:
        return _now() < self.expires_at


class AccountActionToken(Base):
    __tablename__ = "account_action_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(32), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class TotpRecoveryCode(Base):
    __tablename__ = "totp_recovery_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class ModeratorInvite(Base):
    pass

    __tablename__ = "moderator_invites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    max_uses: Mapped[int] = mapped_column(Integer)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now)

    def is_usable(self) -> bool:
        return not self.revoked and self.use_count < self.max_uses and _now() < self.expires_at


class AdminAuditLog(Base):
    pass

    __tablename__ = "admin_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    actor_username: Mapped[str] = mapped_column(String(32))
    target_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    target_username: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(48), index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now, index=True)


class ContributorInvite(Base):
    __tablename__ = "contributor_invites"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_by_username: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    used_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    used_by_username: Mapped[str | None] = mapped_column(String(32), nullable=True)


class AppUpdate(Base):
    __tablename__ = "app_updates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(150))
    version: Mapped[str] = mapped_column(String(64), index=True)
    notes: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16))
    source_repository: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_release_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_release_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    download_destination: Mapped[str | None] = mapped_column(String(16), nullable=True)
    download_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_by_username: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now, index=True)


class AppUpdateSelection(Base):
    __tablename__ = "app_update_selection"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    update_id: Mapped[str] = mapped_column(ForeignKey("app_updates.id"), unique=True)
    selected_at: Mapped[datetime] = mapped_column(DateTime(), default=_now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(32), default="info")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now, index=True)

class LibraryState(Base):
    __tablename__ = "library_states"
    __table_args__ = (UniqueConstraint("user_id", "item_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    item_key: Mapped[str] = mapped_column(String(512))
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    client_updated_at: Mapped[float] = mapped_column(Float, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=_now)

class LibraryStateAlias(Base):
    __tablename__ = "library_state_aliases"
    __table_args__ = (UniqueConstraint("user_id", "legacy_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    legacy_key: Mapped[str] = mapped_column(String(512))
    item_key: Mapped[str] = mapped_column(String(512))

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    reporter_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(16), index=True)
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    reason: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now, index=True)
