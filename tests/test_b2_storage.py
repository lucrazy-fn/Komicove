from __future__ import annotations

from pathlib import Path

import pytest

from komicove_backend.catalog import assets, b2_storage


class MissingObject(Exception):
    response = {"Error": {"Code": "404"}}


class FakeB2:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def upload_file(self, source: str, bucket: str, name: str):
        assert bucket == "komicove-assets-luanz"
        self.objects[name] = Path(source).read_bytes()

    def head_object(self, *, Bucket: str, Key: str):
        assert Bucket == "komicove-assets-luanz"
        if Key not in self.objects:
            raise MissingObject()

    def download_file(self, bucket: str, name: str, target: str):
        assert bucket == "komicove-assets-luanz"
        if name not in self.objects:
            raise MissingObject()
        Path(target).write_bytes(self.objects[name])

    def delete_object(self, *, Bucket: str, Key: str):
        assert Bucket == "komicove-assets-luanz"
        self.objects.pop(Key, None)


def _configure_b2(monkeypatch, fake):
    monkeypatch.setattr(b2_storage, "_client", lambda: (fake, "komicove-assets-luanz"))
    monkeypatch.setenv("B2_ENDPOINT", "https://s3.us-east-005.backblazeb2.com")
    monkeypatch.setenv("B2_KEY_ID", "test-id")
    monkeypatch.setenv("B2_APPLICATION_KEY", "test-key")
    monkeypatch.setenv("B2_BUCKET", "komicove-assets-luanz")


def test_b2_upload_download_and_delete_without_supabase(monkeypatch, tmp_path):
    fake = FakeB2()
    _configure_b2(monkeypatch, fake)
    monkeypatch.setenv("KOMICOVE_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    payload = b"a" * (assets.REMOTE_PART_BYTES + 1)
    source = tmp_path / "comic.cbz"
    source.write_bytes(payload)
    assets._remote_upload(source, "comic.cbz")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"cover")
    assets._remote_upload(cover, "comic.cbz.cover.jpg")

    assert fake.objects == {"comic.cbz": payload, "comic.cbz.cover.jpg": b"cover"}
    assert assets.asset_exists("comic.cbz")
    assert assets.resolve_asset("comic.cbz").read_bytes() == payload

    assets.delete_remote("comic.cbz")
    assert not fake.objects
    assert not assets.asset_exists("comic.cbz")


def test_old_supabase_asset_is_read_when_missing_in_b2(monkeypatch, tmp_path):
    _configure_b2(monkeypatch, FakeB2())
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test-secret")
    monkeypatch.setenv("KOMICOVE_STORAGE_DIR", str(tmp_path / "storage"))

    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def iter_content(self, _size):
            yield b"legacy comic"

        def close(self):
            pass

    monkeypatch.setattr(assets.requests, "get", lambda *_args, **_kwargs: Response())
    target = tmp_path / "old.cbz"
    assets._remote_download("old.cbz", target)
    assert target.read_bytes() == b"legacy comic"


def test_partial_b2_configuration_is_rejected(monkeypatch):
    monkeypatch.setenv("B2_BUCKET", "komicove-assets-luanz")
    for name in ("B2_ENDPOINT", "B2_KEY_ID", "B2_APPLICATION_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(assets.RemoteStorageError, match="incompleta"):
        b2_storage.configured()
