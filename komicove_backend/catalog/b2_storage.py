"""Private Backblaze B2 storage for publication assets."""

from __future__ import annotations

import logging
import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit

log = logging.getLogger("komicove.assets")


class RemoteStorageError(RuntimeError):
    pass


class StorageConfigurationError(RemoteStorageError):
    pass


def configured() -> bool:
    names = ("B2_ENDPOINT", "B2_KEY_ID", "B2_APPLICATION_KEY", "B2_BUCKET")
    values = {name: os.environ.get(name, "").strip() for name in names}
    if not any(values.values()):
        return False
    if not all(values.values()):
        raise StorageConfigurationError("Configuração do Backblaze B2 incompleta no servidor.")
    return True


def _client():
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise StorageConfigurationError("Dependência boto3 ausente no servidor.") from exc

    endpoint = os.environ["B2_ENDPOINT"].strip().rstrip("/")
    parsed = urlsplit(endpoint)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.path or parsed.query or parsed.fragment
            or not host.startswith("s3.") or not host.endswith(".backblazeb2.com")):
        raise StorageConfigurationError("B2_ENDPOINT deve ser o endpoint HTTPS S3 do bucket.")
    region = host.removeprefix("s3.").removesuffix(".backblazeb2.com")
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ["B2_KEY_ID"].strip(),
        aws_secret_access_key=os.environ["B2_APPLICATION_KEY"].strip(),
        region_name=region,
        config=Config(signature_version="s3v4", connect_timeout=10, read_timeout=120,
                      retries={"mode": "standard", "max_attempts": 4}),
    )
    return client, os.environ["B2_BUCKET"].strip()


def _missing(exc: Exception) -> bool:
    response = getattr(exc, "response", {})
    code = str(response.get("Error", {}).get("Code", ""))
    return code in {"404", "NoSuchKey", "NotFound"}


def _error_details(exc: Exception) -> tuple[str, int | None]:
    """Return only safe S3 error metadata, never request headers or keys."""
    current: BaseException | None = exc
    for _ in range(4):
        if current is None:
            break
        response = getattr(current, "response", None)
        if isinstance(response, dict):
            error = response.get("Error", {})
            metadata = response.get("ResponseMetadata", {})
            code = error.get("Code") if isinstance(error, dict) else None
            status = metadata.get("HTTPStatusCode") if isinstance(metadata, dict) else None
            safe_code = str(code) if code and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", str(code)) else "unknown"
            safe_status = status if isinstance(status, int) and 100 <= status <= 599 else None
            return safe_code, safe_status
        current = current.__cause__ or current.__context__
    return type(exc).__name__, None


def _error_reason(exc: Exception) -> str:
    """Classify server messages without logging values that may contain secrets."""
    current: BaseException | None = exc
    for _ in range(4):
        if current is None:
            break
        response = getattr(current, "response", None)
        if isinstance(response, dict):
            error = response.get("Error", {})
            message = error.get("Message", "") if isinstance(error, dict) else ""
            if isinstance(message, str):
                lowered = message.lower()
                if "credential" in lowered and "malformed" in lowered:
                    return "malformed_credentials"
                if "checksum" in lowered:
                    return "checksum"
                if "chunk" in lowered:
                    return "chunked_encoding"
                if "region" in lowered:
                    return "region"
                if "bucket" in lowered:
                    return "bucket"
                if "signature" in lowered:
                    return "signature"
                if "authorization" in lowered:
                    return "authorization"
                if "access key" in lowered or "application key" in lowered:
                    return "access_key"
        current = current.__cause__ or current.__context__
    return "other"


def upload(path: Path, name: str) -> None:
    client, bucket = _client()
    try:
        client.upload_file(str(path), bucket, name)
    except Exception as exc:
        code, status = _error_details(exc)
        log.warning("B2 upload failed: code=%s status=%s reason=%s", code, status, _error_reason(exc))
        raise RemoteStorageError("O Backblaze B2 recusou ou interrompeu o envio.") from exc


def exists(name: str) -> bool:
    client, bucket = _client()
    try:
        client.head_object(Bucket=bucket, Key=name)
        return True
    except Exception as exc:
        if _missing(exc):
            return False
        code, status = _error_details(exc)
        log.warning("B2 lookup failed: code=%s status=%s reason=%s", code, status, _error_reason(exc))
        return False


def download(name: str, target: Path) -> bool:
    client, bucket = _client()
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.download")
    try:
        client.download_file(bucket, name, str(temporary))
        temporary.replace(target)
        return True
    except Exception as exc:
        if _missing(exc):
            return False
        raise RemoteStorageError("Não foi possível baixar o arquivo do Backblaze B2.") from exc
    finally:
        temporary.unlink(missing_ok=True)


def delete(name: str) -> None:
    client, bucket = _client()
    try:
        client.delete_object(Bucket=bucket, Key=name)
    except Exception as exc:
        raise RemoteStorageError("Não foi possível excluir o arquivo do Backblaze B2.") from exc
