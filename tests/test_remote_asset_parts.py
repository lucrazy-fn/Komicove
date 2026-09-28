import json
from urllib.parse import unquote, urlsplit

from komicove_backend.catalog import assets


class FakeResponse:
    def __init__(self, status_code=200, data=b""):
        self.status_code = status_code
        self._data = data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise assets.requests.HTTPError(str(self.status_code))

    def json(self):
        return json.loads(self._data.decode("utf-8"))

    def iter_content(self, size):
        for start in range(0, len(self._data), size):
            yield self._data[start:start + size]

    def close(self):
        return None


def _object_name(url):
    path = unquote(urlsplit(url).path)
    return path.split("/storage/v1/object/", 1)[1].split("/", 1)[1]


def test_large_remote_asset_is_split_and_reassembled(monkeypatch, tmp_path):
    objects = {}
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret")
    monkeypatch.setenv("SUPABASE_BUCKET", "Name: panel-assets")
    monkeypatch.setenv("KOMICOVE_STORAGE_DIR", str(tmp_path / "storage"))

    def post(url, *, data, **_kwargs):
        objects[_object_name(url)] = bytes(data)
        return FakeResponse()

    def get(url, **_kwargs):
        name = _object_name(url)
        return FakeResponse(200, objects[name]) if name in objects else FakeResponse(404)

    def head(url, **_kwargs):
        return FakeResponse(200 if _object_name(url) in objects else 404)

    def delete(url, **_kwargs):
        objects.pop(_object_name(url), None)
        return FakeResponse(200)

    monkeypatch.setattr(assets.requests, "post", post)
    monkeypatch.setattr(assets.requests, "get", get)
    monkeypatch.setattr(assets.requests, "head", head)
    monkeypatch.setattr(assets.requests, "delete", delete)

    payload = b"a" * assets.REMOTE_PART_BYTES + b"b" * assets.REMOTE_PART_BYTES + b"tail"
    source = tmp_path / "large.cbr"
    source.write_bytes(payload)

    assets._remote_upload(source, "comic.cbr")

    manifest_name = assets._manifest_name("comic.cbr")
    manifest = json.loads(objects[manifest_name])
    assert "comic.cbr" not in objects
    assert len(manifest["parts"]) == 3
    assert all(part["size"] <= assets.REMOTE_PART_BYTES for part in manifest["parts"])
    assert assets.asset_exists("comic.cbr") is True

    target = tmp_path / "restored.cbr"
    assets._remote_download("comic.cbr", target)
    assert target.read_bytes() == payload

    assets.delete_remote("comic.cbr")
    assert manifest_name not in objects
    assert not any(name.startswith("_komicove_parts/comic.cbr/") for name in objects)


def test_small_remote_asset_keeps_legacy_single_object_format(monkeypatch, tmp_path):
    objects = {}
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret")
    monkeypatch.setenv("SUPABASE_BUCKET", "panel-assets")
    monkeypatch.setattr(
        assets.requests, "post",
        lambda url, *, data, **_kwargs: (
            objects.__setitem__(_object_name(url), bytes(data)) or FakeResponse()
        ),
    )
    source = tmp_path / "small.cbz"
    source.write_bytes(b"small comic")

    assets._remote_upload(source, "small.cbz")

    assert objects == {"small.cbz": b"small comic"}
