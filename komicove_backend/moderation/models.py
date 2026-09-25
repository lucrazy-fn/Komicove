
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class ModerationStatus(str, Enum):
    pass
    APPROVED = "approved"
    PENDING_REVIEW = "pending_review"
    REJECTED = "rejected"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class PublicationSubmission:
    pass
    user_id: str
    title: str
    author: str
    description: str
    tags: list[str] = field(default_factory=list)


    authorship_declared: bool = False
    authorization_declared: bool = False
    license: Optional[str] = None


    file_name: Optional[str] = None
    file_hash: Optional[str] = None
    cover_image_bytes: Optional[bytes] = None
    embedded_metadata: dict = field(default_factory=dict)

    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AnalyzerFinding:
    pass
    analyzer_name: str
    risk_level: RiskLevel
    confidence: float
    reasons: list[str]
    matched_signals: dict = field(default_factory=dict)


@dataclass
class ModerationResult:
    pass
    submission_user_id: str
    status: ModerationStatus
    risk_level: RiskLevel
    confidence: float
    internal_justification: str
    findings: list[AnalyzerFinding]
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def public_message(self) -> str:
        pass
        if self.status == ModerationStatus.APPROVED:
            return (
                "Sua publicação passou pela triagem automática inicial e foi "
                "liberada. Isso não é uma confirmação legal de autoria: "
                "publicações podem ser removidas posteriormente se houver "
                "denúncia ou nova análise."
            )
        if self.status == ModerationStatus.PENDING_REVIEW:
            return (
                "Sua publicação está em análise antes de ficar visível na "
                "comunidade. Isso é rotina para parte dos envios e não "
                "significa que algo foi feito de errado."
            )
        return (
            "Não foi possível publicar este conteúdo no momento. Se você "
            "acredita que isso é um engano, é possível abrir um recurso."
        )
