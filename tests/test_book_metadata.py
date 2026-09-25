from komicove_app import book_metadata as metadata


def test_edit_does_not_change_original(tmp_path, monkeypatch):
    monkeypatch.setattr(metadata, 'FILE', str(tmp_path / 'metadata.json'))
    comic = tmp_path / 'original.cbz'
    comic.write_bytes(b'original')
    metadata.save(str(comic), {'title': 'Novo', 'series': 'Serie', 'number': '2', 'writer': 'Autor'})
    assert metadata.get(str(comic))['title'] == 'Novo'
    assert comic.read_bytes() == b'original'
