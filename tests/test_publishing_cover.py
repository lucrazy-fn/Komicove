from unittest.mock import Mock

from komicove_client import api_client


def test_upload_publication_file_sends_optional_cover(monkeypatch, tmp_path):
    comic = tmp_path / "comic.cbz"
    comic.write_bytes(b"comic")
    response = Mock(ok=True, status_code=200)
    response.json.return_value = {
        "publication_id": "publication-1", "original_filename": "comic.cbz",
        "size_bytes": 5, "sha256": "hash",
    }
    request = Mock(return_value=response)
    monkeypatch.setattr(api_client.requests, "put", request)

    api_client.upload_publication_file(
        "token", "publication-1", str(comic), cover_bytes=b"jpeg-preview",
    )

    assert request.call_count == 2
    file_request, cover_request = request.call_args_list
    assert file_request.kwargs["files"]["file"][0] == "comic.cbz"
    assert "cover" not in file_request.kwargs["files"]
    assert cover_request.kwargs["files"]["cover"] == (
        "cover.jpg", b"jpeg-preview", "image/jpeg",
    )
    assert cover_request.args[0].endswith("/publications/publication-1/cover")
