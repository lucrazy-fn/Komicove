import time
import tkinter as tk
import pytest
from PIL import Image, ImageDraw


def test_guided_motion_reaches_target_and_can_be_disabled(tmp_path):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Requer sessão gráfica Tk')
    root.withdraw()
    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)
    from panel_app.reader_views import ReaderWindow
    class Loader:
        count = 2
        def get_pil(self, index):
            image = Image.new('RGB', (240, 360), 'white')
            draw = ImageDraw.Draw(image)
            draw.rectangle((10, 10, 230, 165), fill='black')
            draw.rectangle((10, 195, 230, 350), fill='black')
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
        assert len(window._regions) >= 2
        window._guided_move(1)
        deadline = time.monotonic() + .7
        while time.monotonic() < deadline:
            root.update()
            time.sleep(.01)
        assert window._region_index == 1
        assert window._guide_motion is None
        window._animate_guided = False
        window._guided_move(-1)
        assert window._region_index == 0
        assert window._guide_motion is None
        assert not errors
    finally:
        if window is not None:
            window.destroy()
        root.destroy()
