
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator




class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    email: str | None = Field(default=None, max_length=255)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().lower()
        local, separator, domain = normalized.partition("@")
        if not separator or not local or "." not in domain or domain.startswith("."):
            raise ValueError("e-mail inválido")
        return normalized


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: str | None = Field(default=None,min_length=6,max_length=6)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class UserPublic(BaseModel):
    id: str
    username: str
    display_name: str
    is_moderator: bool = False
    role: str = "user"


class AuthResponse(BaseModel):
    token: str
    user: UserPublic

class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=64)
    email: str | None = Field(default=None, max_length=255)

class NotificationPublic(BaseModel):
    id: str
    title: str
    message: str
    kind: str
    read_at: datetime | None
    created_at: datetime

class LibraryStateItem(BaseModel):
    item_key: str = Field(min_length=1, max_length=512)
    page: int | None = Field(default=None, ge=0)
    favorite: bool = False
    client_updated_at: float | None = None

class LibrarySyncRequest(BaseModel):
    items: list[LibraryStateItem] = Field(default_factory=list, max_length=5000)

class ReportCreate(BaseModel):
    target_type: Literal["publication", "user"]
    target_id: str = Field(min_length=1, max_length=36)
    reason: Literal["copyright", "illegal", "harassment", "spam", "other"]
    description: str = Field(default="", max_length=1000)

class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

class TotpSetup(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    current_code: str | None = Field(default=None, max_length=6)

class TotpConfirm(BaseModel):
    code: str = Field(min_length=6,max_length=6)


class ModeratorClaimRequest(BaseModel):
    setup_token: str = Field(min_length=16, max_length=512)


class ModeratorInviteCreateRequest(BaseModel):
    max_uses: int = Field(ge=1, le=5)
    valid_hours: int = Field(ge=1, le=120)


class ModeratorInviteCreated(BaseModel):
    id: str
    secret: str
    max_uses: int
    use_count: int
    expires_at: datetime


class ModeratorInviteSummary(BaseModel):
    id: str
    max_uses: int
    use_count: int
    expires_at: datetime
    revoked: bool
    created_at: datetime


class ManagedUserPublic(BaseModel):
    last_seen_at: datetime | None = None
    id: str
    username: str
    display_name: str
    email: str | None
    is_active: bool
    is_moderator: bool
    role: str
    suspended_until: datetime | None
    punishment_reason: str | None
    deleted_at: datetime | None
    created_at: datetime


class ManagedUserUpdate(BaseModel):
    action: Literal["set_role", "suspend", "ban", "clear_punishment", "revoke_sessions"]
    role: Literal["user", "moderator"] | None = None
    duration_hours: int | None = Field(default=None, ge=1, le=24 * 365)
    reason: str | None = Field(default=None, max_length=255)


class AuditLogPublic(BaseModel):
    id: str
    actor_username: str
    target_username: str | None
    action: str
    reason: str | None
    details: str | None
    created_at: datetime


class ModeratorDashboard(BaseModel):
    total_users: int
    active_users: int
    suspended_users: int
    banned_users: int
    moderators: int
    pending_publications: int
    active_invites: int


class ManagedPublicationPublic(BaseModel):
    publication_id: str
    title: str
    status: str
    created_at: datetime


class ManagedUserDetail(BaseModel):
    user: ManagedUserPublic
    total_publications: int
    approved_publications: int
    rejected_publications: int
    pending_publications: int
    publications: list[ManagedPublicationPublic]
    recent_actions: list[AuditLogPublic]




class PublicationSubmitRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    author: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    file_reference: str = Field(min_length=1, max_length=512)
    authorship_declared: bool = False
    authorization_declared: bool = False
    license: str | None = Field(default=None, max_length=64)
    series_title: str | None = Field(default=None, max_length=255)
    chapter_number: int | None = Field(default=None, ge=1)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str]) -> list[str]:
        cleaned: list[str] = []
        for tag in tags:
            normalized = tag.strip()
            if not normalized:
                continue
            if len(normalized) > 40:
                raise ValueError("cada tag deve ter no máximo 40 caracteres")
            if normalized.casefold() not in {item.casefold() for item in cleaned}:
                cleaned.append(normalized)
        return cleaned


class PublicationResponse(BaseModel):
    publication_id: str
    comic_id: str
    status: str
    risk_level: str
    public_message: str


class PublicationAssetResponse(BaseModel):
    publication_id: str
    original_filename: str
    size_bytes: int
    sha256: str


class DiscoveryItem(BaseModel):
    publication_id: str
    comic_id: str
    title: str
    author: str
    description: str
    tags: list[str]
    published_at: datetime | None
    has_file: bool = False
    original_filename: str | None = None
    series_title: str | None = None
    chapter_number: int | None = None


class MyPublicationItem(BaseModel):
    publication_id: str
    title: str
    author: str
    description: str
    tags: list[str]
    status: str
    risk_level: str
    created_at: datetime
    published_at: datetime | None
    decision_reason: str | None = None
    has_file: bool = False
    original_filename: str | None = None
    series_title: str | None = None
    chapter_number: int | None = None




class ModerationQueueItem(BaseModel):
    record_id: str
    publication_id: str
    title: str
    author: str
    uploader_username: str
    risk_level: str
    confidence: float
    justification: str
    created_at: datetime
    has_file: bool = False
    original_filename: str | None = None
    status: str = "pending_review"
    decision_reason: str | None = None


class ModerationDecisionRequest(BaseModel):
    decision: str = Field(pattern=r"^(approved|rejected)$")
    reason: str = Field(min_length=3, max_length=2000)
