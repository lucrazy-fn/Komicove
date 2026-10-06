from concurrent.futures import ThreadPoolExecutor
import zipfile

import pytest

from komicove_app import archive


def test_zip_reuses_directory_for_parallel_page_reads_and_closes(tmp_path, monkeypatch):
    path = tmp_path / 'many-pages.cbz'
    with zipfile.ZipFile(path, 'w') as source:
        for index in range(100):
            source.writestr(f'{index:03}.png', str(index).encode())
    backend = archive.ArchiveBackend(path)
    opened = []
    original = zipfile.ZipFile
    def tracked_open(*args, **kwargs):
        source = original(*args, **kwargs)
        opened.append(source)
        return source
    monkeypatch.setattr(archive.zipfile, 'ZipFile', tracked_open)
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            pages = list(executor.map(backend.read_page, range(100)))
        assert pages == [str(index).encode() for index in range(100)]
        assert len(opened) == 1
    finally:
        backend.close()
    assert opened[0].fp is None
    backend.close()
    with pytest.raises(ValueError, match='closed'):
        backend.read_page(0)
