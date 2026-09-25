from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from komicove_backend.accounts.models import Notification, User
from komicove_backend.api.deps import get_db, require_moderator
from komicove_backend.api.schemas import ModerationDecisionRequest, ModerationQueueItem
from komicove_backend.catalog.assets import UnsafeAssetError, cover_jpeg, resolve_asset
from komicove_backend.catalog.models import Comic, Publication, PublicationAsset
from komicove_backend.moderation.db_models import ModerationRecordRow

router = APIRouter(prefix="/moderation", tags=["moderation"])


@router.get("/queue", response_model=list[ModerationQueueItem])
def queue(
    include_decided: bool = False,
    _moderator: User = Depends(require_moderator),
    db: Session = Depends(get_db),
):
    query = (
        select(ModerationRecordRow, Publication, Comic, User, PublicationAsset)
        .join(Publication, Publication.moderation_record_id == ModerationRecordRow.id)
        .join(Comic, Comic.id == Publication.comic_id)
        .join(User, User.id == Publication.user_id)
        .outerjoin(PublicationAsset, PublicationAsset.publication_id == Publication.id)
        .order_by(ModerationRecordRow.created_at.asc())
    )
    if not include_decided:
        query = query.where(ModerationRecordRow.manual_override_status.is_(None))
    rows = db.execute(query).all()
    return [
        ModerationQueueItem(
            record_id=record.id,
            publication_id=publication.id,
            title=comic.title,
            author=comic.author,
            uploader_username=uploader.username,
            risk_level=publication.risk_level,
            confidence=record.confidence,
            justification=record.internal_justification,
            created_at=record.created_at,
            has_file=asset is not None,
            original_filename=asset.original_filename if asset else None,
            status=(record.manual_override_status or "pending_review"),
            decision_reason=record.manual_override_reason,
        )
        for record, publication, comic, uploader, asset in rows
    ]


def _moderation_asset(db: Session, record_id: str) -> PublicationAsset:
    asset = db.scalar(
        select(PublicationAsset)
        .join(Publication, Publication.id == PublicationAsset.publication_id)
        .where(Publication.moderation_record_id == record_id)
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Arquivo da publicação não encontrado.")
    return asset


@router.get("/{record_id}/file")
def download_file(
    record_id: str,
    _moderator: User = Depends(require_moderator),
    db: Session = Depends(get_db),
):
    asset = _moderation_asset(db, record_id)
    try:
        path = resolve_asset(asset.stored_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no armazenamento.") from exc
    return FileResponse(path, filename=asset.original_filename, media_type="application/octet-stream")


@router.get("/{record_id}/cover")
def cover(
    record_id: str,
    _moderator: User = Depends(require_moderator),
    db: Session = Depends(get_db),
):
    asset = _moderation_asset(db, record_id)
    try:
        content = cover_jpeg(resolve_asset(asset.stored_name))
    except (FileNotFoundError, UnsafeAssetError, OSError) as exc:
        raise HTTPException(status_code=422, detail=f"Não foi possível gerar a capa: {exc}") from exc
    return Response(content=content, media_type="image/jpeg")


@router.post("/{record_id}/decision", response_model=ModerationQueueItem)
def decide(
    record_id: str,
    payload: ModerationDecisionRequest,
    moderator: User = Depends(require_moderator),
    db: Session = Depends(get_db),
):
    row = db.execute(
        select(ModerationRecordRow, Publication, Comic, User, PublicationAsset)
        .join(Publication, Publication.moderation_record_id == ModerationRecordRow.id)
        .join(Comic, Comic.id == Publication.comic_id)
        .join(User, User.id == Publication.user_id)
        .outerjoin(PublicationAsset, PublicationAsset.publication_id == Publication.id)
        .where(ModerationRecordRow.id == record_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Pedido de moderação não encontrado.")

    record, publication, comic, uploader, asset = row
    if record.manual_override_status is not None:
        raise HTTPException(status_code=409, detail="Este pedido já foi decidido.")
    if payload.decision == "approved":
        if asset is None:
            raise HTTPException(409,"Envie o arquivo antes da aprovação.")
        try:
            resolve_asset(asset.stored_name)
        except (FileNotFoundError, UnsafeAssetError) as exc:
            raise HTTPException(409,"O arquivo precisa estar disponível para aprovação.") from exc

    record.manual_override_status = payload.decision
    record.manual_override_reason = payload.reason
    record.manual_reviewer_id = moderator.id
    publication.status = payload.decision
    publication.published_at = (
        datetime.now(timezone.utc).replace(tzinfo=None)
        if payload.decision == "approved" else None
    )
    db.add(Notification(
        user_id=uploader.id,
        title="Seu envio foi analisado",
        message=f'“{comic.title}” foi {"aprovado" if payload.decision == "approved" else "rejeitado"}. {payload.reason}',
        kind="publication_decision",
    ))
    db.flush()

    return ModerationQueueItem(
        record_id=record.id,
        publication_id=publication.id,
        title=comic.title,
        author=comic.author,
        uploader_username=uploader.username,
        risk_level=publication.risk_level,
        confidence=record.confidence,
        justification=record.internal_justification,
        created_at=record.created_at,
        has_file=asset is not None,
        original_filename=asset.original_filename if asset else None,
        status=record.manual_override_status or publication.status,
        decision_reason=record.manual_override_reason,
    )
