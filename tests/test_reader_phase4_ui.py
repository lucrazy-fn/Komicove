import gc
import os
import time
import tkinter as tk
import pytest
from PIL import Image, ImageGrab
from komicove_app.reader_views import ReaderWindow
from komicove_app import storage
from komicove_app import runtime
from komicove_app.design.icons import clear_icon_cache

@pytest.fixture(scope='module')
def gui():
    root=tk.Tk();root.withdraw()
    yield root
    clear_icon_cache();gc.collect();root.destroy()

@pytest.fixture(autouse=True)
def collect_tk_objects_on_ui_thread():
    yield
    clear_icon_cache();gc.collect()

class Loader:
    count = 2
    def get_pil(self, index): return Image.new('RGB', (1000,1600), 'white')
    def prefetch(self, index): pass
    def close(self): pass
    def get_thumbnail_pil(self, index, width, height): return Image.new('RGB', (width,height), 'white')

def pump(root):
    end = time.monotonic()+.2
    while time.monotonic()<end:
        root.update()
        time.sleep(.01)

def children(widget):
    for child in widget.winfo_children():
        yield child
        yield from children(child)

@pytest.mark.parametrize('embedded', [False,True])
@pytest.mark.parametrize('guided', [False,True])
def test_fullscreen_uses_entire_window_and_restores_chrome(tmp_path, gui, embedded, guided):
    from komicove_app.reader_views import EmbeddedReader
    storage.save_prefs(reader_guided=guided,reader_auto_fit=True)
    path=tmp_path/'fullscreen.cbz';path.write_bytes(b'fullscreen-fixture')
    host=tk.Toplevel(gui) if embedded else None
    if host: host.geometry('1000x760')
    reader=EmbeddedReader(host,str(path),Loader()) if embedded else ReaderWindow(gui,str(path),Loader())
    if embedded: reader.pack(fill='both',expand=True)
    window=host or reader
    window.attributes('-topmost',True)
    try:
        pump(gui);reader._open_thumbnails();pump(gui)
        index=reader._idx;zoom=reader._zoom
        reader._fullscreen();pump(gui)
        assert window.attributes('-fullscreen') and reader._immersive
        for widget in (reader._top,reader._bot,reader._header_divider,reader._thumb_frame):
            assert not widget.winfo_ismapped()
        assert reader._cv.winfo_width()==window.winfo_width()
        assert reader._cv.winfo_height()==window.winfo_height()
        assert reader._idx==index and reader._zoom==pytest.approx(zoom)
        # A rebuilt reader (for example, a theme change) must stay immersive.
        reader._build();pump(gui)
        assert not reader._top.winfo_ismapped() and not reader._bot.winfo_ismapped()
        reader._escape();pump(gui)
        assert not window.attributes('-fullscreen') and not reader._immersive
        assert reader._top.winfo_ismapped() and reader._bot.winfo_ismapped()
        assert reader._thumb_frame.winfo_ismapped()
        reader._fullscreen();pump(gui);reader._fullscreen();pump(gui)
        assert not window.attributes('-fullscreen')
    finally:
        reader._close()
        if host: host.destroy()

@pytest.mark.parametrize('zoom_on', [False,True])
@pytest.mark.parametrize('position_on', [False,True])
def test_actual_close_and_reopen(tmp_path, zoom_on, position_on, gui):
    clear_icon_cache()
    root=gui
    path=tmp_path/'reopen.cbz';path.write_bytes(b'phase4-reopen')
    storage.save_prefs(reader_guided=False,reader_auto_fit=False,reader_persist_zoom=zoom_on,reader_persist_position=position_on)
    try:
        first=ReaderWindow(root,str(path),Loader());pump(root)
        first._zoom=1.5;first._offset=[-120,-160];first._idx=1
        key=first._content_key
        first._close();pump(root)
        assert storage.load_prefs()['reader_persist_position'] is position_on
        from komicove_app.reader import load_state
        assert load_state(key)['offset']==[-120,-160]
        second=ReaderWindow(root,str(path),Loader());pump(root)
        assert second._idx==1
        assert second._zoom==pytest.approx(1.5 if zoom_on else second.Z0)
        if position_on: assert second._offset[1]<0
        else: assert second._offset[1]>=0
        second._close()
    finally:
        clear_icon_cache()

@pytest.mark.parametrize('lang', ['pt','en'])
@pytest.mark.parametrize('dark', [False,True])
def test_preferences_ui_and_real_save(tmp_path, lang, dark, monkeypatch, gui):
    clear_icon_cache();root=gui
    path=tmp_path/'preferences.cbz';path.write_bytes(b'phase4-ui')
    storage.save_prefs(lang=lang,reader_guided=False,reader_persist_zoom=True,reader_persist_position=True)
    monkeypatch.setattr(runtime, "LANG", lang)
    if runtime.IS_DARK != dark: runtime.toggle_theme()
    from komicove_app import reader_views
    monkeypatch.setattr(reader_views, "IS_DARK", dark)
    window=ReaderWindow(root,str(path),Loader());pump(root)
    try:
        window._reader_preferences();pump(root)
        dialog=next(w for w in window.winfo_children() if isinstance(w,tk.Toplevel))
        labels=[w.cget('text') for w in children(dialog) if isinstance(w,tk.Label)]
        assert ('Manter nível de zoom' if lang=='pt' else 'Keep zoom level') in labels
        assert ('Manter posição' if lang=='pt' else 'Keep position') in labels
        from komicove_app.reader_views import ReaderSwitch
        switches=[w for w in children(dialog) if isinstance(w,ReaderSwitch)]
        assert len(switches)==7
        # The first two independent controls must stay enabled in every combination.
        switches[0].event_generate('<Button-1>',x=10,y=10);pump(root)
        if os.environ.get('KOMICOVE_PHASE4_QA'):
            output=__import__('pathlib').Path(os.environ['KOMICOVE_PHASE4_QA']);output.mkdir(parents=True,exist_ok=True)
            dialog.attributes('-topmost',True);dialog.lift();dialog.focus_force();pump(root)
            ImageGrab.grab(bbox=(dialog.winfo_rootx(),dialog.winfo_rooty(),dialog.winfo_rootx()+dialog.winfo_width(),dialog.winfo_rooty()+dialog.winfo_height())).save(output/f'pc-{lang}-{dark}.png')
        # Apply through the actual dialog callback.
        save=next(w for w in children(dialog) if getattr(w,'text',None) in ('Salvar preferências','Save preferences'))
        save.command()
        assert storage.load_prefs()['reader_persist_position'] is True
        assert storage.load_prefs()['reader_persist_zoom'] is False
    finally:
        window._close();clear_icon_cache()


@pytest.mark.parametrize('zoom_on', [False, True])
@pytest.mark.parametrize('position_on', [False, True])
def test_drag_zoom_fit_and_page_change_keep_canvas_origin(tmp_path, gui, zoom_on, position_on):
    from types import SimpleNamespace
    root = gui
    path = tmp_path / 'drag-regression.cbz';path.write_bytes(b'phase4-drag')
    storage.save_prefs(reader_guided=False, reader_auto_fit=True,
                       reader_persist_zoom=zoom_on, reader_persist_position=position_on)
    window = ReaderWindow(root, str(path), Loader());pump(root)
    try:
        window._fit()
        window._drag_start(SimpleNamespace(x=400,y=200))
        window._drag_move(SimpleNamespace(x=1400,y=900))
        window._drag_end(None)
        assert window._offset == [0, 0]
        assert window._cv.coords(window._canvas_image) == [0, 0]
        window._set_zoom(1.5)
        window._drag_start(SimpleNamespace(x=400,y=200))
        window._drag_move(SimpleNamespace(x=500,y=350))
        assert window._cv.coords(window._canvas_image) != [0, 0]
        window._drag_end(None)
        assert window._cv.coords(window._canvas_image) == [0, 0]
        assert window._offset == [100, 150]
        window._wheel(SimpleNamespace(delta=120,state=4,x=500,y=350))
        assert window._cv.coords(window._canvas_image) == [0, 0]
        window._idx = 1;window._show(reset=False)
        assert window._cv.coords(window._canvas_image) == [0, 0]
        window._fit()
        assert window._offset == [0, 0]
        assert window._cv.coords(window._canvas_image) == [0, 0]
        x,y=window._cv.winfo_width()//2,window._cv.winfo_height()//2
        assert window._rendered_frame.getpixel((x,y)) == (255,255,255)
    finally:
        window._close()


def test_reader_pill_releases_font_on_ui_thread(gui, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    fonts = []
    original = runtime.tkfont.Font
    def track(*args, **kwargs):
        font = original(*args, **kwargs);fonts.append(font);return font
    monkeypatch.setattr(runtime.tkfont, 'Font', track)
    pill = runtime.make_pill(gui, 'Encaixar', lambda: None)
    assert len(fonts) == 1
    font = fonts[0]
    assert font.name in gui.tk.call('font', 'names')
    pill.destroy()
    assert font.name not in gui.tk.call('font', 'names')
    assert not font.delete_font
    with ThreadPoolExecutor(max_workers=1) as worker:
        worker.submit(font.__del__).result(timeout=2)
