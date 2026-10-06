import time
import tkinter as tk
import pytest
from PIL import Image, ImageDraw


@pytest.mark.parametrize('page_size', [(240, 360), (2400, 3600)])
def test_guided_motion_reaches_target_and_can_be_disabled(tmp_path, monkeypatch, page_size):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Requer sessão gráfica Tk')
    root.withdraw()
    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)
    from komicove_app.reader_views import ReaderWindow
    if page_size[0] > 1000:
        monkeypatch.setattr('komicove_app.reader_views.load_manual_panels',
                            lambda *args: [(0., 0., 1., .46), (0., .54, 1., 1.)])
    image = Image.new('RGB', page_size, 'white')
    draw = ImageDraw.Draw(image)
    w, h = page_size
    draw.rectangle((w*.04, h*.03, w*.96, h*.46), fill='black')
    draw.rectangle((w*.04, h*.54, w*.96, h*.97), fill='black')
    class Loader:
        count = 2
        def get_pil(self, index):
            return image
        def prefetch(self, index): pass
        def close(self): pass
    path = tmp_path / 'test.cbz'
    path.write_bytes(b'test-guided-animation')
    window = None
    try:
        window = ReaderWindow(root, str(path), Loader())
        window._guided = True
        window._show(reset=False)
        deadline=time.monotonic()+3
        while window._guide_pending and time.monotonic()<deadline:
            root.update()
            time.sleep(.01)
        assert not window._guide_pending
        assert len(window._regions) >= 2
        window._guide_overview = False
        window._show(reset=False)
        window._guided_move(1)
        deadline = time.monotonic() + .7
        while time.monotonic() < deadline:
            root.update()
            time.sleep(.01)
        assert window._region_index == 1
        assert window._guide_motion is None
        assert window._guide_preview is not None
        assert max(window._guide_preview.size) <= 2048
        window._animate_guided = False
        window._guided_move(-1)
        assert window._region_index == 0
        assert window._guide_motion is None
        assert not errors
    finally:
        if window is not None:
            window.destroy()
            window=None
        from komicove_app.design.icons import clear_icon_cache
        import gc
        clear_icon_cache()
        gc.collect()
        root.destroy()
