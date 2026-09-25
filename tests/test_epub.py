import io
import zipfile
import pytest
from PIL import Image
from komicove_app.archive import ArchiveBackend


def fixture(path, body='<img src="../images/2.png"/>', encrypted=False):
    png = io.BytesIO()
    Image.new('RGB', (20, 30)).save(png, 'PNG')
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="OEBPS/book.opf"/></rootfiles></container>')
        z.writestr('OEBPS/book.opf', '<package><manifest><item id="a" href="pages/a.xhtml" media-type="application/xhtml+xml"/><item id="b" href="images/1.png" media-type="image/png"/></manifest><spine><itemref idref="a"/><itemref idref="b"/></spine></package>')
        z.writestr('OEBPS/pages/a.xhtml', '<html><body>' + body + '</body></html>')
        for name in ('1.png', '2.png'):
            z.writestr('OEBPS/images/' + name, png.getvalue())
        if encrypted:
            z.writestr('META-INF/encryption.xml', '<encryption/>')


def test_epub_uses_spine_not_filename_order(tmp_path):
    path = tmp_path / 'book.epub'
    fixture(path)
    book = ArchiveBackend(path)
    assert book.names == ['OEBPS/images/2.png', 'OEBPS/images/1.png']
    assert Image.open(io.BytesIO(book.read_page(0))).size == (20, 30)
    book.close()


@pytest.mark.parametrize('body', ['<p>Texto não pode desaparecer</p><img src="../images/2.png"/>',
                                '<img src="../images/2.png"/><img src="../images/1.png"/>',
                                '<img src="https://example.com/image.png"/>',
                                '<img src="../../../fora.png"/>'])
def test_rejects_unsupported_or_unsafe_epubs(tmp_path, body):
    path = tmp_path / 'book.epub'
    fixture(path, body)
    with pytest.raises(ValueError):
        ArchiveBackend(path)


def test_rejects_encrypted_epub(tmp_path):
    path = tmp_path / 'book.epub'
    fixture(path, encrypted=True)
    with pytest.raises(ValueError, match='DRM'):
        ArchiveBackend(path)
