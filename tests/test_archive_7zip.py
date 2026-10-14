import subprocess
from pathlib import Path
from types import SimpleNamespace
import pytest
from komicove_app import archive


def test_bundled_7zip_wins_over_old_system_binary(monkeypatch, tmp_path):
    bundled = tmp_path / "7zz"
    bundled.write_bytes(b"test executable")
    monkeypatch.delenv("KOMICOVE_7ZIP_PATH", raising=False)
    monkeypatch.delenv("PANEL_7ZIP_PATH", raising=False)
    monkeypatch.setattr(archive.sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(archive.shutil, "which", lambda name: str(tmp_path / name))
    assert Path(archive.find_7zip()) == bundled


def test_modern_system_7zz_wins_over_7z(monkeypatch, tmp_path):
    old = tmp_path / "7z"
    modern = tmp_path / "7zz"
    old.write_bytes(b"old")
    modern.write_bytes(b"modern")
    monkeypatch.delenv("KOMICOVE_7ZIP_PATH", raising=False)
    monkeypatch.delenv("PANEL_7ZIP_PATH", raising=False)
    monkeypatch.delattr(archive.sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(archive.shutil, "which", lambda name: str(tmp_path / name))
    assert Path(archive.find_7zip()) == modern


def test_7zip_lists_images_in_page_order_and_reads_stdout(monkeypatch, tmp_path):
    path = tmp_path / "comic.cb7"
    path.write_bytes(b"fake archive")
    monkeypatch.setattr(archive, "find_7zip", lambda: "7z.exe")
    calls = []
    def run(executable, args):
        calls.append(args)
        if args[0] == "l":
            return b"Path = page10.png\n\nPath = readme.txt\n\nPath = page2.jpg\n"
        return b"page bytes"
    monkeypatch.setattr(archive, "run_7zip", run)
    backend = archive.ArchiveBackend(path)
    assert backend.names == ["page2.jpg", "page10.png"]
    assert backend.read_page(0) == b"page bytes"
    assert calls[1][:4] == ["x", "-so", "-spd", "--"]
    with pytest.raises(IndexError):backend.read_page(2)


def test_missing_7zip_has_actionable_message(monkeypatch, tmp_path):
    path = tmp_path / "comic.7z"
    path.write_bytes(b"fake archive")
    monkeypatch.setattr(archive, "find_7zip", lambda: None)
    with pytest.raises(ValueError, match="Instale o 7-Zip"):
        archive.ArchiveBackend(path)


def test_7zip_failure_is_reported(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 2, b"", b"error"))
    with pytest.raises(ValueError, match="não conseguiu ler"):
        archive.run_7zip("7z", ["l", "broken.cb7"])


def test_7zip_warning_with_complete_image_is_usable(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw:
        subprocess.CompletedProcess(a, 1, b"\x89PNG\r\n\x1a\nimage", b"Headers Error"))
    assert archive.run_7zip("7z", ["x", "-so", "comic.cbr", "001.png"]).startswith(b"\x89PNG")
    with pytest.raises(ValueError, match="Headers Error"):
        archive.run_7zip("7z", ["l", "comic.cbr"])


def test_old_rar_page_uses_rarfile_if_7zip_can_list_but_not_extract(monkeypatch, tmp_path):
    path = tmp_path / "old.cbr"
    path.write_bytes(b"RAR fixture")
    monkeypatch.setattr(archive, "find_7zip", lambda: "7zz")
    monkeypatch.setattr(archive.zipfile, "is_zipfile", lambda path: False)

    def sevenzip(_executable, args):
        if args[0] == "l":
            return b"Path = 001.jpg\n"
        raise ValueError("Unsupported RAR method")

    class RarFile:
        def __init__(self, path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, name):
            assert name == "001.jpg"
            return b"image bytes"

    monkeypatch.setattr(archive, "run_7zip", sevenzip)
    monkeypatch.setattr(archive, "rarfile", SimpleNamespace(RarFile=RarFile))
    backend = archive.ArchiveBackend(path)
    assert backend.read_page(0) == b"image bytes"
    backend.close()


@pytest.mark.parametrize("extension", [".cbr", ".cbz", ".pdf", ".cb7"])
def test_missing_archive_reports_missing_file_before_detecting_format(monkeypatch, tmp_path, extension):
    def unexpected_tool_lookup():
        raise AssertionError("A missing file must not start archive detection")
    monkeypatch.setattr(archive, "find_7zip", unexpected_tool_lookup)
    with pytest.raises(FileNotFoundError):
        archive.ArchiveBackend(tmp_path / ("missing" + extension))
