
from __future__ import annotations

import hashlib
import io
import os
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath
import requests

from fastapi import UploadFile
from PIL import Image
from komicove_backend.config_env import setting

ALLOWED_EXTENSIONS = {".cbz", ".zip", ".cbr", ".rar", ".pdf"}

MAX_UPLOAD_BYTES = int(setting("KOMICOVE_MAX_UPLOAD_MB", "250")) * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = int(setting("KOMICOVE_MAX_UNCOMPRESSED_MB", "1500")) * 1024 * 1024


class UnsafeAssetError(ValueError):
    pass


def storage_dir() -> Path:
    legacy = Path("./panel_storage")
    path = Path(setting("KOMICOVE_STORAGE_DIR", str(legacy if legacy.exists() else Path("./komicove_storage")))).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _remote_config() -> tuple[str, str, str] | None:
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SECRET_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))
    bucket = os.environ.get("SUPABASE_BUCKET", "panel-assets")
    return (base, key, bucket) if base and key else None


def _remote_upload(path: Path, name: str) -> None:
    config = _remote_config()
    if not config:
        return
    base, key, bucket = config
    with path.open("rb") as source:
        response = requests.post(f"{base}/storage/v1/object/{bucket}/{name}", headers={"Authorization": f"Bearer {key}", "apikey": key, "Content-Type": "application/octet-stream", "x-upsert": "true"}, data=source, timeout=120)
    response.raise_for_status()


def _remote_download(name: str, target: Path) -> None:
    config = _remote_config()
    if not config:
        raise FileNotFoundError(name)
    base, key, bucket = config
    response = requests.get(f"{base}/storage/v1/object/{bucket}/{name}", headers={"Authorization": f"Bearer {key}", "apikey": key}, timeout=120)
    if response.status_code == 404:
        raise FileNotFoundError(name)
    response.raise_for_status()
    temporary = target.with_suffix(target.suffix + ".download")
    temporary.write_bytes(response.content)
    temporary.replace(target)


def delete_remote(name: str) -> None:
    config = _remote_config()
    if not config:
        return
    base, key, bucket = config
    response = requests.delete(f"{base}/storage/v1/object/{bucket}/{Path(name).name}", headers={"Authorization": f"Bearer {key}", "apikey": key}, timeout=30)
    if response.status_code not in (200, 204, 404):
        response.raise_for_status()


async def save_upload(upload: UploadFile) -> tuple[str, str, int, str]:
    original = Path(upload.filename or "quadrinho").name
    extension = Path(original).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise UnsafeAssetError("Formato não permitido. Use CBZ, CBR, ZIP, RAR ou PDF.")

    fd, temporary = tempfile.mkstemp(prefix="upload-", suffix=extension, dir=storage_dir())
    digest = hashlib.sha256()
    size = 0
    try:
        with os.fdopen(fd, "wb") as target:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise UnsafeAssetError("Arquivo excede o limite de upload.")
                digest.update(chunk)
                target.write(chunk)
        _validate_file(Path(temporary), extension)
        stored_name = f"{uuid.uuid4().hex}{extension}"
        final_path = storage_dir() / stored_name
        os.replace(temporary, final_path)
        _remote_upload(final_path, stored_name)
        return stored_name, original, size, digest.hexdigest()
    finally:
        await upload.close()
        if os.path.exists(temporary):
            os.remove(temporary)


def resolve_asset(stored_name: str) -> Path:
    base = storage_dir()
    candidate = (base / Path(stored_name).name).resolve()
    if candidate.parent != base:
        raise FileNotFoundError(stored_name)
    if not candidate.is_file():
        _remote_download(Path(stored_name).name, candidate)
    return candidate


def _validate_file(path: Path, extension: str) -> None:
    with path.open("rb") as source:
        header = source.read(8)


    if zipfile.is_zipfile(path):
        total = 0
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                member = PurePosixPath(info.filename.replace("\\", "/"))
                if member.is_absolute() or ".." in member.parts:
                    raise UnsafeAssetError("O arquivo contém caminhos inseguros.")
                total += info.file_size
                if total > MAX_UNCOMPRESSED_BYTES:
                    raise UnsafeAssetError("Conteúdo descompactado excede o limite seguro.")
                if info.compress_size and info.file_size / info.compress_size > 200:
                    raise UnsafeAssetError("Taxa de compressão suspeita (possível ZIP bomb).")
    elif header.startswith(b"Rar!"):
        return
    elif extension == ".pdf" and header.startswith(b"%PDF-"):
        return
    else:
        raise UnsafeAssetError("O conteúdo não corresponde a um quadrinho suportado.")


def cover_jpeg(path: Path, max_size: tuple[int, int] = (360, 520)) -> bytes:
    extension = path.suffix.lower()
    image_data: bytes
    image_exts = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names = sorted(
                (name for name in archive.namelist() if Path(name).suffix.lower() in image_exts),
                key=str.casefold,
            )
            if not names:
                raise UnsafeAssetError("O quadrinho não contém imagens.")
            image_data = archive.read(names[0])
    elif extension in {".cbr", ".rar"}:
        import rarfile
        with rarfile.RarFile(path) as archive:
            names = sorted(
                (name for name in archive.namelist() if Path(name).suffix.lower() in image_exts),
                key=str.casefold,
            )
            if not names:
                raise UnsafeAssetError("O quadrinho não contém imagens.")
            image_data = archive.read(names[0])
    elif extension == ".pdf":
        import pymupdf
        document = pymupdf.open(path)
        try:
            if document.page_count == 0:
                raise UnsafeAssetError("PDF sem páginas.")
            pixmap = document[0].get_pixmap(matrix=pymupdf.Matrix(1.2, 1.2), alpha=False)
            image_data = pixmap.tobytes("png")
        finally:
            document.close()
    else:
        raise UnsafeAssetError("Formato sem suporte para capa.")

    with Image.open(io.BytesIO(image_data)) as image:
        image = image.convert("RGB")
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, "JPEG", quality=85, optimize=True)
        return output.getvalue()
