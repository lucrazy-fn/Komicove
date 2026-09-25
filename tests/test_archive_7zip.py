import subprocess
import pytest
from komicove_app import archive


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
