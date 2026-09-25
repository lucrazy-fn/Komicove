
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from komicove_backend.api.routes import account, auth, moderation, moderator_tokens, moderators, publications, reports
from komicove_backend.db import init_db

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Komicove API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(account.router)
app.include_router(publications.router)
app.include_router(moderation.router)
app.include_router(moderator_tokens.router)
app.include_router(moderators.router)
app.include_router(reports.router)
