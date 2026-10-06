from types import SimpleNamespace
import pytest
from PIL import Image
from komicove_app import reader_views, storage


@pytest.fixture
def reader(monkeypatch, tmp_path):
    monkeypatch.setattr(reader_views, 'load_reader_state', lambda key: {})
    monkeypatch.setattr(reader_views, 'get_progress_page', lambda path: None)
    monkeypatch.setattr(reader_views, 'record_page_read', lambda *a, **kw: None)
    class Host:
        def __init__(self, master): pass
    class Reader(reader_views.ReaderContent, Host):
        _embedded = True
        def configure(self, **kw): pass
        def bind(self, *a, **kw): pass
        def after(self, *a): pass
        def _prefetch_neighbors(self): pass
        def _build(self):
            self._guided_zoom = 1.
            self._guide_render_scale = 1.
            self._cv = SimpleNamespace(winfo_width=lambda: 320, winfo_height=lambda: 480)
        def _present_frame(self, frame, alpha=1.): pass
        def _hud(self): pass
    path = tmp_path / 'phase4.cbz'
    path.write_bytes(b'phase4-fixture')
    image = Image.new('RGB', (1000, 1600), 'white')
    instance = Reader(None, str(path), SimpleNamespace(count=3, get_pil=lambda i: image))
    yield instance
    instance._page_executor.shutdown(wait=True)
    instance._detection_executor.shutdown(wait=True)
    instance._guide_cache.close()
    image.close()


@pytest.mark.parametrize('zoom_on', [False, True])
@pytest.mark.parametrize('position_on', [False, True])
@pytest.mark.parametrize('manga', [False, True])
@pytest.mark.parametrize('auto_fit', [False, True])
def test_four_combinations_on_actual_page_render(reader, zoom_on, position_on, manga, auto_fit):
    reader._guided = False
    reader._persist_zoom = zoom_on
    reader._persist_position = position_on
    reader._manga = manga
    reader._auto_fit = auto_fit
    reader._show(reset=False)
    reader._zoom = 1.5
    reader._offset = [-120, -160]
    reader._idx = 1
    reader._show(reset=False)
    expected_zoom = 1.5 if zoom_on else (min(296/1000, 456/1600)*.95 if auto_fit else reader.Z0)
    assert reader._zoom == pytest.approx(expected_zoom)
    mx, my = max(0, (1000*expected_zoom-320)/2), max(0, (1600*expected_zoom-480)/2)
    if position_on:
        assert reader._offset == pytest.approx([max(-mx, -120*expected_zoom/1.5), max(-my, -160*expected_zoom/1.5)])
    else:
        assert reader._offset == pytest.approx([(-1 if manga else 1)*mx, my])
    unchanged = reader._offset[:]
    reader._show(reset=False)
    assert reader._offset == unchanged


@pytest.mark.parametrize('old', [False, True])
def test_migration_is_persisted_and_preserves_preferences(monkeypatch, tmp_path, old):
    file = tmp_path / 'prefs.json'
    monkeypatch.setattr(storage, 'PREFS_FILE', str(file))
    storage.json_save(str(file), {'reader_persist_zoom': old, 'lang': 'en', 'unknown': 42})
    prefs = storage.load_prefs()
    assert prefs['reader_persist_position'] is old
    assert prefs['reader_persist_zoom'] is old
    assert prefs['lang'] == 'en' and prefs['unknown'] == 42
    assert storage.json_load(str(file), {}) == prefs
    storage.save_prefs(reader_persist_position=not old)
    assert storage.load_prefs()['reader_persist_position'] is not old


@pytest.mark.parametrize('zoom_on', [False, True])
@pytest.mark.parametrize('position_on', [False, True])
def test_reopen_honors_each_preference(reader, zoom_on, position_on):
    reader._guided = False
    reader._persist_zoom = zoom_on
    reader._persist_position = position_on
    reader._has_saved_zoom = zoom_on
    reader._restored_position = position_on
    reader._auto_fit = False
    reader._zoom = 1.5
    reader._offset = [-120, -160]
    reader._initial_render()
    z = 1.5 if zoom_on else reader.Z0
    assert reader._zoom == z
    if position_on:
        assert reader._offset == pytest.approx([-120*z/1.5, -160*z/1.5])
    else:
        assert reader._offset == pytest.approx([max(0,(1000*z-320)/2),max(0,(1600*z-480)/2)])
