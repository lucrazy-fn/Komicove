"""Disposable desktop/backend fixture for the isolated Android Phase 5 runner."""
import argparse
import hashlib
import io
import os
from pathlib import Path
import sys
import time
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--data-dir", type=Path, required=True)
parser.add_argument("--port", type=int, default=18565)
args = parser.parse_args()
data = args.data_dir.resolve()
data.mkdir(parents=True, exist_ok=False)
os.environ["KOMICOVE_APPDATA_DIR"] = str(data / "desktop")
os.environ["KOMICOVE_DATABASE_URL"] = "sqlite:///" + (data / "server.db").as_posix()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import Depends, FastAPI, Request, Response
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session
import uvicorn
from komicove_app import storage, sync
from komicove_backend.accounts.models import User, LibraryState, LibraryStateAlias
from komicove_backend.api.deps import get_current_user, get_db
from komicove_backend.api.routes.account import router, sync_state
from komicove_backend.api.schemas import LibrarySyncRequest
from komicove_backend.db import get_session, init_db

image = io.BytesIO()
Image.new("RGB", (240, 360), "gray").save(image, "PNG")
comic = data / "PC-fixture.cbz"
with zipfile.ZipFile(comic, "w", zipfile.ZIP_DEFLATED) as archive:
    for index in range(16):
        archive.writestr(f"{index:02}.png", image.getvalue())
raw_digest = hashlib.sha256(comic.read_bytes()).hexdigest()
digest = sync.portable_id(str(comic))[0]
uri = "content://com.lucrazy.komicove.phase5fixtures/comic"
legacy = "uri-" + hashlib.sha256(uri.encode()).hexdigest()
init_db()
with get_session() as db:
    user = User(username="phase5-device-fixture", password_hash="fixture", password_salt="fixture")
    db.add(user)
    db.flush()
    user_id = user.id
    db.add(LibraryState(user_id=user_id, item_key=legacy, page=4, favorite=True, client_updated_at=90))
storage.save_progress(str(comic), {"page": 7, "ts": 100, "fixture_extra": 42})
storage.json_save(storage.FAVORITES_FILE, [str(comic)])
storage.flush_progress()

def fixture_user(db: Session = Depends(get_db)):
    return db.get(User, user_id)

def desktop_exchange():
    progress, favorites, state = storage.sync_snapshot()
    payload, mapping = sync.build_sync_payload(progress, favorites, state=state)
    with get_session() as db:
        rows = sync_state(LibrarySyncRequest(items=payload), db.get(User, user_id), db)
        response = [row.model_dump() for row in rows]
    sync.apply_sync_response(response, mapping)
    return response

desktop_exchange()
app = FastAPI(title="Disposable Phase 5 device test")
app.dependency_overrides[get_current_user] = fixture_user
app.include_router(router)

@app.get("/phase5/info")
def info():
    return {"item_key": digest, "raw_key": raw_digest, "legacy_key": legacy, "pages": 16, "fixture": True}

@app.get("/phase5/fixture")
def fixture():
    return Response(comic.read_bytes(), media_type="application/vnd.comicbook+zip")

@app.get("/phase5/pc-state")
def pc_state():
    desktop_exchange()
    with get_session() as db:
        alias = db.scalar(select(LibraryStateAlias).where(LibraryStateAlias.user_id == user_id, LibraryStateAlias.legacy_key == legacy))
    return {"page": storage.get_progress_page(str(comic)), "favorite": storage.is_favorite(str(comic)),
            "extra": storage.load_progress()[str(comic)]["fixture_extra"], "legacy_alias": alias is not None}

@app.post("/phase5/pc-edit")
async def pc_edit(request: Request):
    body = await request.json()
    stamp = max(time.time(), float(body.get("minimum_stamp", 0)) + .01)
    storage.save_progress(str(comic), {"page": int(body["page"]), "ts": stamp, "fixture_extra": 42})
    if storage.is_favorite(str(comic)) != bool(body["favorite"]):
        storage.toggle_favorite(str(comic))
    storage.flush_progress()
    desktop_exchange()
    return {"edited": True}

print(f"Phase 5 fixture ready: http://127.0.0.1:{args.port}, disposable data: {data}", flush=True)
uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning", access_log=False)
