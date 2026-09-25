from __future__ import annotations

import secrets
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from komicove_backend.accounts import service as accounts
from komicove_backend.catalog import service as catalog
from komicove_backend.db import Base
from komicove_backend.moderation.service import ModerationService
from komicove_backend.moderation.storage import JsonModerationStore


def main():
    # A demo must never initialize or write the API's configured database.
    with TemporaryDirectory(prefix="panel-demo-") as directory:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        moderation_service = ModerationService(
            store=JsonModerationStore(str(Path(directory) / "records.json")))
        with Session(engine) as db, db.begin():
            auth = accounts.register_user(
                db, username="maria_autora", password=secrets.token_urlsafe(32))
            print("Demonstração isolada: banco temporário e senha aleatória.")
            for title, author, declared in (
                ("As Aventuras de Zeca Lagarta", "Maria Autora", True),
                ("Naruto", "?", False),
            ):
                outcome = catalog.submit_publication(
                    db, moderation_service=moderation_service, user_id=auth.user.id,
                    data=catalog.SubmissionInput(
                        title=title, author=author, description="Demonstração local",
                        tags=[], file_reference="demo.cbz", authorship_declared=declared,
                    ),
                )
                print(f"Comic: {outcome.comic.title}")
                print(f"Publication status: {outcome.publication.status}")
                print(f"Mensagem pública: {outcome.public_message}")
        engine.dispose()


if __name__ == "__main__":
    main()
