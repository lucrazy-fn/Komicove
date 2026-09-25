
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from komicove_backend.db import Base


class ModerationRecordRow(Base):
    __tablename__ = "moderation_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    publication_title: Mapped[str] = mapped_column(String(255))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(32))
    risk_level: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    internal_justification: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime())

    manual_override_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    manual_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_reviewer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
