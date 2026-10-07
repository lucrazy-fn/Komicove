import re
import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from komicove_backend import updates
from komicove_backend.accounts import audit
from komicove_backend.accounts.models import AppUpdate, AppUpdateSelection, User, _now
from komicove_backend.api.deps import get_db, require_moderator
from komicove_backend.api.schemas import AppUpdateCreate, AppUpdatePreview, AppUpdatePublic
from komicove_client import releases

router = APIRouter(tags=["app-updates"])


def _selection(db):
    selection = db.get(AppUpdateSelection, 1)
    if selection:
        item = db.get(AppUpdate, selection.update_id)
        if item:
            return item, f"{item.id}:{selection.selected_at.isoformat()}Z"
    item = db.scalars(select(AppUpdate).order_by(AppUpdate.created_at.desc(), AppUpdate.id).limit(1)).first()
    return (item, f"legacy:{item.id}") if item else (None, None)


def _select(db, item):
    selection = db.get(AppUpdateSelection, 1)
    if selection is None:
        selection = AppUpdateSelection(id=1, update_id=item.id)
        db.add(selection)
    else:
        selection.update_id = item.id
        selection.selected_at = _now()
    db.flush()
    return selection


def public(item, selected_id=None, selection_token=None):
    return AppUpdatePublic(id=item.id, title=item.title, version=item.version, notes=item.notes,
        notes_html=updates.markdown(item.notes), source=item.source, source_repository=item.source_repository,
        source_release_id=item.source_release_id, source_release_url=item.source_release_url,
        download_destination=item.download_destination, download_url=item.download_url,
        created_by_username=item.created_by_username, created_at=item.created_at.isoformat() + "Z",
        selected=item.id == selected_id,
        selection_token=selection_token if item.id == selected_id else None)


def _automatic_release(update_id, actor, db):
    match = re.fullmatch(r"auto-(\d+)-(\d+)", update_id)
    if match is None:
        return None
    repository_index, release_id = (int(value) for value in match.groups())
    if repository_index >= len(releases.REPOSITORIES) or release_id <= 0 or release_id > 2**63 - 1:
        raise HTTPException(404, "Atualização não encontrada.")
    repository = releases.REPOSITORIES[repository_index]
    existing = db.scalars(select(AppUpdate).where(
        AppUpdate.source_repository == repository,
        AppUpdate.source_release_id == release_id,
    )).first()
    if existing:
        return existing
    try:
        content = updates.imported(repository, release_id)
    except ValueError as error:
        raise HTTPException(422, str(error))
    except requests.RequestException:
        raise HTTPException(502, "Não foi possível consultar as releases do GitHub.")
    item = AppUpdate(title=content["title"].strip(), version=content["version"].strip(), notes=content["notes"],
        source="github", source_repository=repository, source_release_id=release_id,
        source_release_url=content["url"], download_destination="github",
        download_url=releases.release_url(content["version"]),
        created_by_user_id=actor.id, created_by_username=actor.username)
    db.add(item)
    db.flush()
    return item


@router.get("/updates", response_model=list[AppUpdatePublic])
def feed(db: Session = Depends(get_db), offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    if offset:
        return []
    item, token = _selection(db)
    return [public(item, item.id, token)] if item else []


@router.get("/api/moderators/updates", response_model=list[AppUpdatePublic])
def history(actor: User = Depends(require_moderator), db: Session = Depends(get_db), offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    selected, token = _selection(db)
    selected_id = selected.id if selected else None
    return [public(item, selected_id, token) for item in db.scalars(
        select(AppUpdate).order_by(AppUpdate.created_at.desc(), AppUpdate.id).offset(offset).limit(limit))]


@router.get("/api/moderators/releases")
def releases_list(repository: str, actor: User = Depends(require_moderator), page: int = Query(1, ge=1, le=10000)):
    if repository not in releases.REPOSITORIES:
        raise HTTPException(422, "Repositório não permitido.")
    try:
        rows = releases.github_get(repository, "?per_page=30" + (f"&page={page}" if page > 1 else "")) or []
        return [{"id": r["id"], "title": r.get("name") or r.get("tag_name"), "version": r.get("tag_name"),
            "notes": r.get("body") or "", "notes_html": updates.markdown(r.get("body") or ""),
            "url": r.get("html_url"), "created_at": r.get("published_at") or r.get("created_at")}
            for r in rows if not r.get("draft") and not r.get("prerelease")
            and releases.version_key(r.get("tag_name")) is not None and releases.github_url(r.get("html_url"))]
    except (requests.RequestException, ValueError, TypeError, KeyError):
        raise HTTPException(502, "Não foi possível consultar as releases do GitHub.")


@router.post("/api/moderators/updates/preview")
def preview(payload: AppUpdatePreview, actor: User = Depends(require_moderator)):
    return {"html": updates.markdown(payload.notes)}


@router.post("/api/moderators/updates", response_model=AppUpdatePublic, status_code=201)
def publish(payload: AppUpdateCreate, actor: User = Depends(require_moderator), db: Session = Depends(get_db)):
    content = {"title": payload.title, "version": payload.version, "notes": payload.notes, "url": None}
    if payload.source == "github":
        try:
            content = updates.imported(payload.repository, payload.release_id)
        except ValueError as error:
            raise HTTPException(422, str(error))
        except requests.RequestException:
            raise HTTPException(502, "Não foi possível consultar as releases do GitHub.")
    url = None
    if payload.download_destination == "site":
        url = releases.SITE_DOWNLOAD_URL
    elif payload.download_destination == "github":
        url = releases.release_url(content["version"])
    item = AppUpdate(title=content["title"].strip(), version=content["version"].strip(), notes=content["notes"],
        source=payload.source, source_repository=payload.repository, source_release_id=payload.release_id,
        source_release_url=content["url"], download_destination=payload.download_destination, download_url=url,
        created_by_user_id=actor.id, created_by_username=actor.username)
    db.add(item)
    db.flush()
    _select(db, item)
    audit.record(db, actor, "app_update_published", details=f"atualização {item.id}, {item.version}, {item.source}, {item.download_destination or 'none'}")
    _, token = _selection(db)
    return public(item, item.id, token)


@router.put("/api/moderators/updates/{update_id}/selection", response_model=AppUpdatePublic)
def select_for_apps(update_id: str, actor: User = Depends(require_moderator), db: Session = Depends(get_db)):
    item = _automatic_release(update_id, actor, db) or db.get(AppUpdate, update_id)
    if item is None:
        raise HTTPException(404, "Atualização não encontrada.")
    selection = _select(db, item)
    audit.record(db, actor, "app_update_selected", details=f"atualização {item.id}, {item.version}")
    token = f"{item.id}:{selection.selected_at.isoformat()}Z"
    return public(item, item.id, token)
