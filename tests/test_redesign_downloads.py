import io
from zipfile import ZipFile

from PIL import Image

import komicove_app.downloads as downloads
from komicove_app.downloads import DownloadTask, _visible_downloads


def test_download_filters_use_real_status_and_search():
    tasks = [
        DownloadTask("one", "Cidade Azul", "", "", None, status="downloading"),
        DownloadTask("two", "Cidade Vermelha", "", "", None, status="completed"),
        DownloadTask("three", "Noite", "", "", None, status="failed"),
    ]
    assert [task.id for task in _visible_downloads(tasks, "all", "")] == ["three", "two", "one"]
    assert [task.id for task in _visible_downloads(tasks, "downloading", "")] == ["one"]
    assert [task.id for task in _visible_downloads(tasks, "completed", "")] == ["two"]
    assert [task.id for task in _visible_downloads(tasks, "failed", "")] == ["three"]
    assert [task.id for task in _visible_downloads(tasks, "all", "CIDADE")] == ["two", "one"]


def test_completed_download_uses_first_page_as_cover(tmp_path, monkeypatch):
    monkeypatch.setattr(downloads, "COVER_CACHE_DIR", str(tmp_path / "covers"))
    comic = tmp_path / "comic.cbz"
    image = Image.new("RGB", (80, 120), (220, 30, 40))
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="PNG")
    with ZipFile(comic, "w") as archive:
        archive.writestr("001.png", image_bytes.getvalue())
    task = DownloadTask("real-cover", "Comic", "", str(comic), None, status="completed")

    assert downloads._cache_local_cover(task)
    with Image.open(downloads._cover_path(task)) as cover:
        assert cover.size == (196, 264)
        red, green, blue = cover.getpixel((100, 120))
        assert red > 180 and green < 80 and blue < 90


def test_active_download_uses_publication_cover(tmp_path, monkeypatch):
    monkeypatch.setattr(downloads, "COVER_CACHE_DIR", str(tmp_path / "covers"))
    image = Image.new("RGB", (80, 120), (20, 40, 200))
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="PNG")
    called = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, _size):
            yield image_bytes.getvalue()

    def fake_get(url, **kwargs):
        called["url"] = url
        called["headers"] = kwargs["headers"]
        return FakeResponse()

    monkeypatch.setattr(downloads.requests, "get", fake_get)
    task = DownloadTask("remote-cover", "Comic", "https://example.test/publications/abc/content",
                        str(tmp_path / "comic.cbz"), "test-token", status="downloading")
    downloads._cache_remote_cover(task)

    assert called["url"] == "https://example.test/publications/abc/cover"
    assert called["headers"] == {"Authorization": "Bearer test-token"}
    assert downloads.os.path.isfile(downloads._cover_path(task))


def test_publication_cover_takes_priority_over_archive_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(downloads, "COVER_CACHE_DIR", str(tmp_path / "covers"))
    task = DownloadTask("priority", "Comic", "", str(tmp_path / "comic.cbz"), None)

    def picture(color):
        output = io.BytesIO()
        Image.new("RGB", (40, 60), color).save(output, format="PNG")
        return output.getvalue()

    downloads._store_cover(task, picture((220, 30, 40)))
    downloads._store_cover(task, picture((20, 40, 220)), remote=True)
    downloads._store_cover(task, picture((220, 30, 40)))
    with Image.open(downloads._cover_path(task)) as cover:
        red, green, blue = cover.getpixel((100, 120))
        assert blue > 180 and red < 80 and green < 90
