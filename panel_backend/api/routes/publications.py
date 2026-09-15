from __future__ import annotations

from fastapi import APIRouter, Depends, File, Header, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from panel_backend.accounts import service as accounts
from panel_backend.accounts.models import User
from panel_backend.api.deps import get_current_user, get_db, get_moderation_service
from panel_backend.api.schemas import (
    DiscoveryItem,
    MyPublicationItem,
    PublicationResponse,
    PublicationAssetResponse,
    PublicationSubmitRequest,
)
from panel_backend.catalog import service as catalog
from panel_backend.catalog.assets import UnsafeAssetError, cover_jpeg, resolve_asset, save_upload
from panel_backend.catalog.models import Comic, Publication, PublicationAsset
from panel_backend.moderation.service import ModerationService
from panel_backend.moderation.db_models import ModerationRecordRow

router = APIRouter(prefix="/publications", tags=["publications"])


@router.delete("/{publication_id}", status_code=204)
def remove_publication(publication_id: str, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    publication = db.get(Publication, publication_id)
    if publication is None or publication.user_id != user.id:
        raise HTTPException(404, "Publicação não encontrada.")
    asset = db.scalar(select(PublicationAsset).where(PublicationAsset.publication_id == publication_id))
    if asset is not None:
        db.delete(asset)
        db.flush()

    db.delete(publication)
    db.flush()

def _asset_available(asset: PublicationAsset | None) -> bool:
    if asset is None:return False
    try: resolve_asset(asset.stored_name);return True
    except FileNotFoundError:return False


def _authorized_asset(
    publication_id: str, authorization: str | None, db: Session,
) -> PublicationAsset:
    row = db.execute(
        select(Publication, PublicationAsset, ModerationRecordRow)
        .join(PublicationAsset, PublicationAsset.publication_id == Publication.id)
        .join(ModerationRecordRow, ModerationRecordRow.id == Publication.moderation_record_id)
        .where(Publication.id == publication_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    publication, asset, record = row
    publicly_approved = (
        publication.status == "approved"
        and record.manual_override_status == "approved"
    )
    if publicly_approved:
        return asset

    user = None
    if authorization and authorization.startswith("Bearer "):
        user = accounts.get_user_by_token(
            db, authorization.removeprefix("Bearer ").strip()
        )
    if user is None or (publication.user_id != user.id and not user.is_moderator):
        raise HTTPException(status_code=403, detail="Você não pode acessar este arquivo.")
    return asset


@router.get("/{publication_id}/content")
def content(
    publication_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    asset = _authorized_asset(publication_id, authorization, db)
    try:
        path = resolve_asset(asset.stored_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no armazenamento.") from exc
    return FileResponse(path, filename=asset.original_filename, media_type="application/octet-stream")


@router.get("/{publication_id}/cover")
def publication_cover(
    publication_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    asset = _authorized_asset(publication_id, authorization, db)
    try:
        data = cover_jpeg(resolve_asset(asset.stored_name))
    except (FileNotFoundError, UnsafeAssetError, OSError) as exc:
        raise HTTPException(status_code=422, detail=f"Não foi possível gerar a capa: {exc}") from exc
    return Response(content=data, media_type="image/jpeg")


@router.put("/{publication_id}/file", response_model=PublicationAssetResponse)
async def upload_file(
    publication_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    publication = db.get(Publication, publication_id)
    if publication is None or publication.user_id != user.id:
        raise HTTPException(status_code=404, detail="Publicação não encontrada.")
    if db.scalar(select(PublicationAsset).where(
        PublicationAsset.publication_id == publication_id
    )) is not None:
        raise HTTPException(status_code=409, detail="Esta publicação já possui um arquivo.")
    record = db.get(ModerationRecordRow, publication.moderation_record_id)
    if record is None or record.manual_override_status is not None:
        raise HTTPException(409,"Não é possível anexar arquivo após a decisão. Faça um novo envio.")
    try:
        stored_name, original, size, sha256 = await save_upload(file)
    except UnsafeAssetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    gate = db.execute(update(ModerationRecordRow).where(
        ModerationRecordRow.id == publication.moderation_record_id,
        ModerationRecordRow.manual_override_status.is_(None),
    ).values(manual_override_status=None))
    if gate.rowcount != 1:
        resolve_asset(stored_name).unlink(missing_ok=True)
        raise HTTPException(409,"A publicação foi decidida durante o upload. Faça um novo envio.")

    asset = PublicationAsset(
        publication_id=publication_id, stored_name=stored_name,
        original_filename=original, size_bytes=size, sha256=sha256,
    )
    db.add(asset)
    db.flush()
    return PublicationAssetResponse(
        publication_id=publication_id, original_filename=original,
        size_bytes=size, sha256=sha256,
    )


@router.get("/mine", response_model=list[MyPublicationItem])
def mine(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Publication, Comic, ModerationRecordRow, PublicationAsset)
        .join(Comic, Comic.id == Publication.comic_id)
        .outerjoin(
            ModerationRecordRow,
            ModerationRecordRow.id == Publication.moderation_record_id,
        )
        .outerjoin(PublicationAsset, PublicationAsset.publication_id == Publication.id)
        .where(Publication.user_id == user.id)
        .order_by(Publication.created_at.desc())
    ).all()
    return [
        MyPublicationItem(
            publication_id=publication.id,
            title=comic.title,
            author=comic.author,
            description=comic.description,
            tags=comic.tag_list(),
            status=(
                publication.status
                if record is None or record.manual_override_status is not None
                else "pending_review"
            ),
            risk_level=publication.risk_level,
            created_at=publication.created_at,
            published_at=publication.published_at,
            decision_reason=record.manual_override_reason if record else None,
            has_file=_asset_available(asset),
            original_filename=asset.original_filename if asset else None,
            series_title=comic.series_title, chapter_number=comic.chapter_number,
        )
        for publication, comic, record, asset in rows
    ]


@router.post("", response_model=PublicationResponse, status_code=201)
def submit(
    payload: PublicationSubmitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    moderation_service: ModerationService = Depends(get_moderation_service),
):
    pass
    outcome = catalog.submit_publication(
        db,
        moderation_service=moderation_service,
        user_id=user.id,
        data=catalog.SubmissionInput(
            title=payload.title,
            author=payload.author,
            description=payload.description,
            tags=payload.tags,
            file_reference=payload.file_reference,
            authorship_declared=payload.authorship_declared,
            authorization_declared=payload.authorization_declared,
            license=payload.license,
            series_title=payload.series_title,
            chapter_number=payload.chapter_number,
        ),
    )
    return PublicationResponse(
        publication_id=outcome.publication.id,
        comic_id=outcome.comic.id,
        status=outcome.publication.status,
        risk_level=outcome.publication.risk_level,
        public_message=outcome.public_message,
    )


@router.get("/discovery", response_model=list[DiscoveryItem])
def discovery(db: Session = Depends(get_db)):
    pass
    rows = db.execute(
        select(Publication, Comic, PublicationAsset)
        .join(Comic, Comic.id == Publication.comic_id)
        .join(
            ModerationRecordRow,
            ModerationRecordRow.id == Publication.moderation_record_id,
        )
        .where(Publication.status == "approved")
        .where(ModerationRecordRow.manual_override_status == "approved")
        .outerjoin(PublicationAsset, PublicationAsset.publication_id == Publication.id)
        .order_by(Publication.published_at.desc())
    ).all()

    return [
        DiscoveryItem(
            publication_id=pub.id,
            comic_id=comic.id,
            title=comic.title,
            author=comic.author,
            description=comic.description,
            tags=comic.tag_list(),
            published_at=pub.published_at,
            has_file=asset is not None,
            original_filename=asset.original_filename if asset else None,
            series_title=comic.series_title, chapter_number=comic.chapter_number,
        )
        for pub, comic, asset in rows if _asset_available(asset)
    ]
