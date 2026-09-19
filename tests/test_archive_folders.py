import io
import zipfile
from PIL import Image
from panel_app.archive import ArchiveBackend, pil_from_bytes


def test_nested_pages_are_read_in_natural_order(tmp_path):
    data = io.BytesIO()
    Image.new('RGB', (16, 24), 'red').save(data, 'PNG')
    path = tmp_path / 'nested.cbz'
    with zipfile.ZipFile(path, 'w') as source:
        for name in ('HQ/Capitulo 1/10.png', 'HQ/Capitulo 1/2.png', 'HQ/Capitulo 1/1.png'):
            source.writestr(name, data.getvalue())
    backend = ArchiveBackend(path)
    try:
        assert backend.names == ['HQ/Capitulo 1/1.png', 'HQ/Capitulo 1/2.png', 'HQ/Capitulo 1/10.png']
        assert all(pil_from_bytes(backend.read_page(i)).size == (16, 24) for i in range(3))
    finally:
        backend.close()
