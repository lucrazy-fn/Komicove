from types import SimpleNamespace
from concurrent.futures import Future
from PIL import Image

import pytest

from komicove_app import reader_views


@pytest.mark.parametrize('frames', [(0.0, 2.0), (0.0, 0.0, 2.0)])
def test_page_turn_survives_skipped_animation_frames(monkeypatch, frames):
    clock = iter(frames)
    monkeypatch.setattr(reader_views.time, 'perf_counter', lambda: next(clock))
    saved = []
    monkeypatch.setattr(reader_views, 'save_progress', lambda path, index: saved.append(index))
    pending = []
    rendered = []
    prefetched = []
    future = Future()
    future.set_result(None)
    reader = SimpleNamespace(
        _fading=False, _idx=0, _count=3, _path='example.cbz',
        _page_executor=SimpleNamespace(submit=lambda *args: future),
        _loader=SimpleNamespace(get_pil=lambda index: None),
        _show=lambda **kwargs: rendered.append(reader._idx),
        _prefetch_neighbors=lambda: prefetched.append(reader._idx),
        after=lambda ms, callback: pending.append(callback),
    )
    reader_views.ReaderContent._fade_to(reader, 1)
    while pending:
        pending.pop(0)()
    assert reader._idx == 1
    assert rendered[-1] == 1
    assert saved == [1]
    assert prefetched == [1]
    assert not reader._fading


def test_page_turn_waits_without_blocking_or_repainting(monkeypatch):
    future = Future()
    callbacks = []
    reader = SimpleNamespace(
        _fading=False, _idx=0, _count=3,
        _loader=SimpleNamespace(get_pil=lambda index: pytest.fail('UI loaded page')),
        _page_executor=SimpleNamespace(submit=lambda *args: future),
        after=lambda ms, callback: callbacks.append(callback),
    )
    reader_views.ReaderContent._fade_to(reader, 1)
    assert reader._idx == 0
    assert reader._fading
    assert len(callbacks) == 1
    future.set_exception(ValueError('Invalid page'))
    callbacks.pop()()
    assert reader._idx == 0
    assert not reader._fading


@pytest.mark.parametrize('guided', [False, True])
def test_first_render_from_initialized_reader(monkeypatch, tmp_path, guided):
    """Exercise startup and real PIL rendering without requiring a Tk display."""
    monkeypatch.setattr(reader_views, 'load_prefs', lambda: {'reader_guided': guided})
    monkeypatch.setattr(reader_views, 'load_reader_state', lambda key: {})
    monkeypatch.setattr(reader_views, 'get_progress_page', lambda path: None)
    monkeypatch.setattr(reader_views, 'record_page_read', lambda *args, **kwargs: None)
    monkeypatch.setattr(reader_views, 'load_manual_panels', lambda *args: [(0., 0., 1., 1.)])
    frames, hud = [], []

    class Host:
        def __init__(self, master): pass

    class Reader(reader_views.ReaderContent, Host):
        _embedded = True
        def configure(self, **kwargs): pass
        def bind(self, *args, **kwargs): pass
        def after(self, *args): pass
        def _prefetch_neighbors(self): pass
        def _build(self):
            self._guided_zoom = 1.
            self._guide_render_scale = 1.
            self._cv = SimpleNamespace(winfo_width=lambda: 320, winfo_height=lambda: 480)
        def _present_frame(self, frame, alpha=1.): frames.append(frame)
        def _hud(self): hud.append(True)
        def _save_guided_position(self): pass

    path = tmp_path / 'startup.cbz'
    path.write_bytes(b'startup-regression')
    image = Image.new('RGB', (240, 360), 'white')
    reader = Reader(None, str(path), SimpleNamespace(count=1, get_pil=lambda index: image))
    try:
        reader._show(reset=False)
        assert len(frames) == 1
        assert frames[0].getpixel((160, 240)) == (255, 255, 255)
        assert hud == [True]
    finally:
        reader._page_executor.shutdown(wait=True)
        reader._detection_executor.shutdown(wait=True)
        reader._guide_cache.close()


@pytest.mark.parametrize('rect', [(0., 0., 1., 1.), (.2, .1, .8, .9)])
@pytest.mark.parametrize('zoom', [.5, 1., 4.])
def test_guided_crop_limits_resize_to_viewport(monkeypatch, rect, zoom):
    image = Image.new('RGB', (2400, 3600), 'white')
    sizes = []
    resize = Image.Image.resize
    def tracked_resize(self, size, *args, **kwargs):
        sizes.append(size)
        return resize(self, size, *args, **kwargs)
    monkeypatch.setattr(Image.Image, 'resize', tracked_resize)
    frame, scale = reader_views._guided_crop(image, rect, 800, 600, zoom, Image.Resampling.BILINEAR)
    assert frame.size == (800, 600)
    assert frame.getpixel((400, 300)) == (255, 255, 255)
    assert scale > 0
    assert all(w <= 800 and h <= 600 for w, h in sizes)
