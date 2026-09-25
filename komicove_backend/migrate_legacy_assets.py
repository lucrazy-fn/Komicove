
from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from pathlib import Path

from sqlalchemy import select

from komicove_backend.catalog.assets import MAX_UPLOAD_BYTES, _validate_file, storage_dir
from komicove_backend.catalog.models import Comic, Publication, PublicationAsset
from komicove_backend.db import get_session, init_db


def main() -> None:
    init_db()
    imported = 0
    skipped = 0
    known_files: dict[str, Path] = {}
    with get_session() as db:
        rows = db.execute(
            select(Publication, Comic)
            .join(Comic, Comic.id == Publication.comic_id)
            .outerjoin(PublicationAsset, PublicationAsset.publication_id == Publication.id)
            .where(PublicationAsset.id.is_(None))
        ).all()
        for publication, comic in rows:
            source = Path(comic.file_reference)
            try:
                if not source.is_file() or source.stat().st_size > MAX_UPLOAD_BYTES:
                    skipped += 1
                    continue
                extension = source.suffix.lower()
                _validate_file(source, extension)
                digest = hashlib.sha256()
                with source.open("rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        digest.update(chunk)
                sha256 = digest.hexdigest()
                stored_name = f"{uuid.uuid4().hex}{extension}"
                destination = storage_dir() / stored_name
                previous = known_files.get(sha256)
                if previous:
                    try:
                        os.link(previous, destination)
                    except OSError:
                        shutil.copy2(source, destination)
                else:
                    shutil.copy2(source, destination)
                    known_files[sha256] = destination
                db.add(PublicationAsset(
                    publication_id=publication.id,
                    stored_name=stored_name,
                    original_filename=source.name,
                    sha256=sha256,
                    size_bytes=source.stat().st_size,
                ))
                imported += 1
            except (OSError, ValueError):
                skipped += 1
    print(f"Arquivos importados: {imported}; ignorados: {skipped}")


if __name__ == "__main__":
    main()
