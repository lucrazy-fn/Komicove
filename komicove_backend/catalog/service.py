
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from komicove_backend.catalog.models import Comic, Publication
from komicove_backend.moderation.models import ModerationResult, PublicationSubmission
from komicove_backend.moderation.service import ModerationService


@dataclass
class SubmissionInput:
    pass
    title: str
    author: str
    description: str
    tags: list[str]
    file_reference: str
    authorship_declared: bool = False
    authorization_declared: bool = False
    license: str | None = None
    series_title: str | None = None
    chapter_number: int | None = None
    embedded_metadata: dict | None = None


@dataclass
class SubmissionOutcome:
    comic: Comic
    publication: Publication
    moderation_result: ModerationResult
    public_message: str


def submit_publication(
    db: Session,
    *,
    moderation_service: ModerationService,
    user_id: str,
    data: SubmissionInput,
) -> SubmissionOutcome:
    comic = Comic(
        uploader_id=user_id,
        title=data.title,
        author=data.author,
        description=data.description,
        tags=", ".join(data.tags),
        file_reference=data.file_reference,
        license=data.license,
        series_title=data.series_title,
        chapter_number=data.chapter_number,
    )
    db.add(comic)
    db.flush()

    submission = PublicationSubmission(
        user_id=user_id,
        title=data.title,
        author=data.author,
        description=data.description,
        tags=data.tags,
        authorship_declared=data.authorship_declared,
        authorization_declared=data.authorization_declared,
        license=data.license,
        file_name=data.file_reference,
        embedded_metadata=data.embedded_metadata or {},
    )
    result, record = moderation_service.review(submission)

    publication = Publication(
        comic_id=comic.id,
        user_id=user_id,

        status="pending_review",
        risk_level=result.risk_level.value,
        moderation_record_id=record.record_id,
    )

    db.add(publication)
    db.flush()

    return SubmissionOutcome(
        comic=comic,
        publication=publication,
        moderation_result=result,
        public_message=(
            "Seu pedido foi enviado para revisão e ficará visível na comunidade "
            "somente depois da decisão de um moderador."
        ),
    )
