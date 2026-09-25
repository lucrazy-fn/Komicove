
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from komicove_backend.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Comic(Base):
    __tablename__ = "comics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    uploader_id: Mapped[str] = mapped_column(ForeignKey("users.id"))

    title: Mapped[str] = mapped_column(String(255))
    author: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(String(255), default="")

    file_reference: Mapped[str] = mapped_column(String(512))
    license: Mapped[str | None] = mapped_column(String(64), nullable=True)
    series_title: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    chapter_number: Mapped[int | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now)

    publication: Mapped["Publication | None"] = relationship(
        back_populates="comic", uselist=False, cascade="all, delete-orphan"
    )

    def tag_list(self) -> list[str]:
        return [t.strip() for t in self.tags.split(",") if t.strip()]


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    comic_id: Mapped[str] = mapped_column(ForeignKey("comics.id"), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))




    status: Mapped[str] = mapped_column(String(32), default="pending_review")
    risk_level: Mapped[str] = mapped_column(String(16), default="medium")
    moderation_record_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    comic: Mapped["Comic"] = relationship(back_populates="publication")

    def is_visible_to_community(self) -> bool:
        pass
        return self.status == "approved"


class PublicationAsset(Base):
    __tablename__ = "publication_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    publication_id: Mapped[str] = mapped_column(
        ForeignKey("publications.id", ondelete="CASCADE"), unique=True, index=True
    )
    stored_name: Mapped[str] = mapped_column(String(128), unique=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=_now)
