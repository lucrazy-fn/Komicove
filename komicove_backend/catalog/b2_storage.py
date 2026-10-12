"""Private Backblaze B2 storage for publication assets."""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit

log = logging.getLogger("komicove.assets")


class RemoteStorageError(RuntimeError):
    pass


def configured() -> bool:
    names = ("B2_ENDPOINT", "B2_KEY_ID", "B2_APPLICATION_KEY", "B2_BUCKET")
    values = {name: os.environ.get(name, "").strip() for name in names}
    if not any(values.values()):
        return False
    if not all(values.values()):
        raise RemoteStorageError("Configura��o do Backblaze B2 incompleta no servidor.")
    return True


def _client():
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise RemoteStorageError("Depend�ncia boto3 ausente no servidor.") from exc

    endpoint = os.environ["B2_ENDPOINT"].strip().rstrip("/")
    parsed = urlsplit(endpoint)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.path or parsed.query or parsed.fragment
            or not host.startswith("s3.") or not host.endswith(".backblazeb2.com")):
        raise RemoteStorageError("B2_ENDPOINT deve ser o endpoint HTTPS S3 do bucket.")
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


def upload(path: Path, name: str) -> None:
    client, bucket = _client()
    try:
        client.upload_file(str(path), bucket, name)
    except Exception as exc:
        raise RemoteStorageError("O Backblaze B2 recusou ou interrompeu o envio.") from exc


def exists(name: str) -> bool:
    client, bucket = _client()
    try:
        client.head_object(Bucket=bucket, Key=name)
        return True
    except Exception as exc:
        if _missing(exc):
            return False
        log.warning("N�o foi poss�vel consultar o arquivo %s no B2: %s", name, type(exc).__name__)
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
        raise RemoteStorageError("N�o foi poss�vel baixar o arquivo do Backblaze B2.") from exc
    finally:
        temporary.unlink(missing_ok=True)


def delete(name: str) -> None:
    client, bucket = _client()
    try:
        client.delete_object(Bucket=bucket, Key=name)
    except Exception as exc:
        raise RemoteStorageError("N�o foi poss�vel excluir o arquivo do Backblaze B2.") from exc
