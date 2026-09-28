
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import tempfile
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import quote
import requests

from fastapi import UploadFile
from PIL import Image
from komicove_backend.config_env import setting

ALLOWED_EXTENSIONS = {".cbz", ".zip", ".cbr", ".rar", ".pdf"}

MAX_UPLOAD_BYTES = int(setting("KOMICOVE_MAX_UPLOAD_MB", "250")) * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = int(setting("KOMICOVE_MAX_UNCOMPRESSED_MB", "1500")) * 1024 * 1024

# Supabase Free accepts objects up to 50 MB. Keeping each remote object at
# 5 MB also follows the recommendation to use standard uploads only for small
# files. Large comics are stored as an application-level multipart object and
# transparently reassembled on download.
REMOTE_PART_BYTES = 5 * 1024 * 1024
REMOTE_RETRIES = 4

log = logging.getLogger("komicove.assets")


class UnsafeAssetError(ValueError):
    pass


class RemoteStorageError(RuntimeError):
    pass


def storage_dir() -> Path:
    legacy = Path("./panel_storage")
    path = Path(setting("KOMICOVE_STORAGE_DIR", str(legacy if legacy.exists() else Path("./komicove_storage")))).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _remote_config() -> tuple[str, str, str] | None:
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SECRET_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))
    bucket = os.environ.get("SUPABASE_BUCKET", "panel-assets").strip()
    return (base, key, bucket) if base and key else None


def _remote_url(base: str, bucket: str, name: str) -> str:
    return f"{base}/storage/v1/object/{quote(bucket, safe='')}/{quote(name, safe='/')}"


def _manifest_name(name: str) -> str:
    return f"_komicove_manifests/{Path(name).name}.json"


def _part_name(name: str, index: int) -> str:
    return f"_komicove_parts/{Path(name).name}/{index:06d}.part"


def _remote_headers(key: str, content_type: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {key}", "apikey": key}
    if content_type:
        headers.update({"Content-Type": content_type, "x-upsert": "true"})
    return headers


def _remote_put_bytes(base: str, key: str, bucket: str, name: str,
                      data: bytes, content_type: str = "application/octet-stream") -> None:
    last_error: Exception | None = None
    for attempt in range(REMOTE_RETRIES):
        try:
            response = requests.post(
                _remote_url(base, bucket, name),
                headers=_remote_headers(key, content_type), data=data, timeout=120,
            )
            response.raise_for_status()
            return
        except requests.RequestException as exc:
            last_error = exc
            if attempt + 1 >= REMOTE_RETRIES:
                break
            time.sleep(0.4 * (2 ** attempt))
    raise RemoteStorageError(
        "O armazenamento online recusou ou interrompeu o envio. Tente novamente."
    ) from last_error


def _remote_delete_object(base: str, key: str, bucket: str, name: str) -> None:
    response = requests.delete(
        _remote_url(base, bucket, name), headers=_remote_headers(key), timeout=30,
    )
    if response.status_code not in (200, 204, 404):
        response.raise_for_status()


def _remote_get_json(base: str, key: str, bucket: str, name: str) -> dict | None:
    response = requests.get(
        _remote_url(base, bucket, name), headers=_remote_headers(key), timeout=30,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    try:
        value = response.json()
    except ValueError as exc:
        raise RemoteStorageError("Manifesto remoto inválido.") from exc
    return value if isinstance(value, dict) else None


def _remote_upload(path: Path, name: str) -> None:
    config = _remote_config()
    if not config:
        return
    base, key, bucket = config
    size = path.stat().st_size
    if size <= REMOTE_PART_BYTES:
        _remote_put_bytes(base, key, bucket, name, path.read_bytes())
        return

    parts: list[dict[str, int | str]] = []
    uploaded: list[str] = []
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            index = 0
            while chunk := source.read(REMOTE_PART_BYTES):
                part_name = _part_name(name, index)
                _remote_put_bytes(base, key, bucket, part_name, chunk)
                uploaded.append(part_name)
                parts.append({"name": part_name, "size": len(chunk)})
                digest.update(chunk)
                index += 1
        manifest = {
            "format": "komicove.multipart.v1",
            "name": Path(name).name,
            "size": size,
            "sha256": digest.hexdigest(),
            "parts": parts,
        }
        _remote_put_bytes(
            base, key, bucket, _manifest_name(name),
            json.dumps(manifest, separators=(",", ":")).encode("utf-8"),
            "application/json",
        )
    except Exception:
        for part_name in uploaded:
            try:
                _remote_delete_object(base, key, bucket, part_name)
            except requests.RequestException:
                log.warning("Não foi possível limpar a parte incompleta %s", part_name)
        raise


def _cover_name(stored_name: str) -> str:
    return f"{Path(stored_name).name}.cover.jpg"


def asset_exists(stored_name: str) -> bool:
    """Check availability without downloading the complete comic archive."""
    local = storage_dir() / Path(stored_name).name
    if local.is_file():
        return True
    config = _remote_config()
    if not config:
        return False
    base, key, bucket = config
    for remote_name in (Path(stored_name).name, _manifest_name(stored_name)):
        try:
            response = requests.head(
                _remote_url(base, bucket, remote_name),
                headers=_remote_headers(key), timeout=20,
            )
            if response.status_code == 200:
                return True
            if response.status_code in (400, 405):
                response = requests.get(
                    _remote_url(base, bucket, remote_name),
                    headers={**_remote_headers(key), "Range": "bytes=0-0"},
                    timeout=20, stream=True,
                )
                if response.status_code in (200, 206):
                    response.close()
                    return True
                response.close()
        except requests.RequestException:
            continue
    return False


async def save_cover_preview(upload: UploadFile, stored_name: str) -> None:
    """Validate and persist the small client-generated cover beside the archive."""
    preview_name = _cover_name(stored_name)
    target = storage_dir() / preview_name
    temporary = target.with_suffix(".upload")
    size = 0
    try:
        with temporary.open("wb") as output:
            while chunk := await upload.read(256 * 1024):
                size += len(chunk)
                if size > 10 * 1024 * 1024:
                    raise UnsafeAssetError("A imagem de capa excede o limite permitido.")
                output.write(chunk)
        with Image.open(temporary) as image:
            image.verify()
        temporary.replace(target)
        _remote_upload(target, preview_name)
    finally:
        await upload.close()
        temporary.unlink(missing_ok=True)


def resolve_cover(stored_name: str) -> Path | None:
    try:
        return resolve_asset(_cover_name(stored_name))
    except FileNotFoundError:
        return None


def _remote_download(name: str, target: Path) -> None:
    config = _remote_config()
    if not config:
        raise FileNotFoundError(name)
    base, key, bucket = config
    temporary = target.with_suffix(target.suffix + ".download")
    response = requests.get(
        _remote_url(base, bucket, name), headers=_remote_headers(key),
        timeout=120, stream=True,
    )
    if response.status_code != 404:
        response.raise_for_status()
        try:
            with temporary.open("wb") as output:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        output.write(chunk)
            temporary.replace(target)
            return
        finally:
            response.close()
            temporary.unlink(missing_ok=True)
    response.close()

    manifest = _remote_get_json(base, key, bucket, _manifest_name(name))
    if manifest is None:
        raise FileNotFoundError(name)
    if manifest.get("format") != "komicove.multipart.v1":
        raise RemoteStorageError("Formato multipart remoto não reconhecido.")
    parts = manifest.get("parts")
    expected_size = manifest.get("size")
    expected_hash = manifest.get("sha256")
    if (not isinstance(parts, list) or not isinstance(expected_size, int)
            or expected_size < 0 or expected_size > MAX_UPLOAD_BYTES):
        raise RemoteStorageError("Manifesto multipart remoto inválido.")

    written = 0
    digest = hashlib.sha256()
    try:
        with temporary.open("wb") as output:
            for index, part in enumerate(parts):
                expected_name = _part_name(name, index)
                if not isinstance(part, dict) or part.get("name") != expected_name:
                    raise RemoteStorageError("Parte remota inválida.")
                part_response = requests.get(
                    _remote_url(base, bucket, expected_name),
                    headers=_remote_headers(key), timeout=120, stream=True,
                )
                if part_response.status_code == 404:
                    part_response.close()
                    raise FileNotFoundError(name)
                part_response.raise_for_status()
                try:
                    part_size = 0
                    for chunk in part_response.iter_content(1024 * 1024):
                        if not chunk:
                            continue
                        output.write(chunk)
                        digest.update(chunk)
                        written += len(chunk)
                        part_size += len(chunk)
                    if part_size != part.get("size"):
                        raise RemoteStorageError("Parte remota incompleta.")
                finally:
                    part_response.close()
        if written != expected_size or digest.hexdigest() != expected_hash:
            raise RemoteStorageError("Arquivo remoto incompleto ou corrompido.")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def delete_remote(name: str) -> None:
    local_name = Path(name).name
    (storage_dir() / local_name).unlink(missing_ok=True)
    (storage_dir() / _cover_name(local_name)).unlink(missing_ok=True)
    config = _remote_config()
    if not config:
        return
    base, key, bucket = config
    manifest_name = _manifest_name(name)
    manifest = None
    try:
        manifest = _remote_get_json(base, key, bucket, manifest_name)
    except requests.RequestException:
        log.warning("Não foi possível consultar o manifesto de %s durante a remoção", name)
    for remote_name in (Path(name).name, _cover_name(name)):
        _remote_delete_object(base, key, bucket, remote_name)
    if isinstance(manifest, dict):
        for part in manifest.get("parts", []):
            part_name = part.get("name") if isinstance(part, dict) else None
            if isinstance(part_name, str) and part_name.startswith(
                    f"_komicove_parts/{Path(name).name}/"):
                _remote_delete_object(base, key, bucket, part_name)
    _remote_delete_object(base, key, bucket, manifest_name)


async def save_upload(upload: UploadFile) -> tuple[str, str, int, str]:
    original = Path(upload.filename or "quadrinho").name
    extension = Path(original).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise UnsafeAssetError("Formato não permitido. Use CBZ, CBR, ZIP, RAR ou PDF.")

    fd, temporary = tempfile.mkstemp(prefix="upload-", suffix=extension, dir=storage_dir())
    digest = hashlib.sha256()
    size = 0
    final_path: Path | None = None
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
    except Exception:
        if final_path is not None:
            final_path.unlink(missing_ok=True)
        raise
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
