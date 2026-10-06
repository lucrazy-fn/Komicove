import gc
import time
import tkinter as tk
from threading import Event, current_thread, main_thread
from concurrent.futures import CancelledError

import pytest
from PIL import Image,ImageDraw


@pytest.fixture
def gui():
    try:
        root=tk.Tk()
    except tk.TclError:
        pytest.skip('Requires a graphical Tk runtime')
    root.withdraw()
    from komicove_app.design.icons import clear_icon_cache
    clear_icon_cache()
    yield root
    for child in list(root.winfo_children()):
        child.destroy()
    clear_icon_cache();gc.collect();root.destroy()


def pump(root,condition=lambda:True):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        root.update()
        if condition():
            return
        time.sleep(.01)
    assert condition()


class Loader:
    count=2
    def get_pil(self,index):
        image=Image.new('RGB',(240,360),'white');draw=ImageDraw.Draw(image)
        draw.rectangle((10,10,230,165),fill='black');draw.rectangle((10,195,230,350),fill='black')
        return image
    def prefetch(self,index):pass
    def close(self):pass


@pytest.mark.parametrize('lang', ['pt', 'en'])
def test_guided_starts_focused_and_locate_returns_to_saved_panel(gui,tmp_path,monkeypatch,lang):
    from komicove_app import runtime,storage
    from komicove_app.reader_views import ReaderWindow
    from PIL import ImageTk
    monkeypatch.setattr(runtime,'LANG',lang)
    storage.save_prefs(reader_guided=True,reader_animate_guided=False)
    monkeypatch.setattr('komicove_app.reader_views.load_manual_panels',lambda *args:[[0,0,1,.45],[0,.55,1,1]])
    path=tmp_path/'focused-start.cbz';path.write_bytes(b'focused-start-test')
    window=ReaderWindow(gui,str(path),Loader())
    try:
        window.geometry('900x700');pump(gui,lambda:window._guide_key is not None and not window._fading)
        assert window._guided and not window._guide_overview
        assert window._guided_heading.text==('Se localizar' if lang=='pt' else 'Find your place')
        focused_scale=window._guide_render_scale
        with ImageTk.getimage(window._tk_img).convert('RGB') as frame:
            pixels=frame.tobytes();assert not any(pixels[i]>180 and pixels[i+1]<90 and pixels[i+2]<100 for i in range(0,len(pixels),3))
        window._guided_move(1);pump(gui,lambda:not window._fading and not window._guide_pending and window._guide_motion is None);selected=window._region_index
        window._guided_heading.command();pump(gui)
        assert window._guide_overview and window._region_index==selected
        assert window._guide_render_scale<focused_scale
        assert window._guided_heading.text==('Voltar ao quadro' if lang=='pt' else 'Return to panel')
        with ImageTk.getimage(window._tk_img).convert('RGB') as frame:
            pixels=frame.tobytes();assert any(pixels[i]>180 and pixels[i+1]<90 and pixels[i+2]<100 for i in range(0,len(pixels),3))
        window._guided_heading.command();pump(gui)
        assert not window._guide_overview and window._region_index==selected
        window.destroy();window=ReaderWindow(gui,str(path),Loader());pump(gui,lambda:window._guide_key is not None and not window._fading)
        assert not window._guide_overview and window._region_index==selected
        window._toggle_guided();pump(gui);window._toggle_guided();pump(gui)
        assert window._guided and not window._guide_overview
    finally:
        window.destroy()


def test_whole_page_guided_render_avoids_copy_and_preserves_pixels(gui,tmp_path):
    from komicove_app.reader_views import ReaderWindow
    from komicove_app.runtime import THEME
    from PIL import ImageTk
    path=tmp_path/'no-full-copy.cbz';path.write_bytes(b'isolated-test')
    window=ReaderWindow(gui,str(path),Loader())
    source=Image.new('RGB',(240,360),(17,129,253))
    try:
        window.geometry('800x600');pump(gui)
        window._guided=True;window._guide_overview=False
        window._guide_fallback=True;window._guide_manual=False
        window._guide_pending=False;window._guide_result=None
        window._regions=[(0.,0.,1.,1.)];window._region_index=0
        window._guide_motion=None;window._guided_zoom=1.
        window._guide_key=(window._idx,window._rotation,window._double,window._manga)
        window._compose_pages=lambda:source
        cw,ch=window._cv.winfo_width(),window._cv.winfo_height()
        scale=min(max(1,cw-24)/source.width,max(1,ch-24)/source.height)
        with source.copy() as copied:
            with copied.resize((max(1,int(source.width*scale)),max(1,int(source.height*scale))),Image.Resampling.LANCZOS) as resized:
                expected=Image.new('RGB',(cw,ch),THEME['canvas_bg'])
                expected.paste(resized,((cw-resized.width)//2,(ch-resized.height)//2))
        def unnecessary_copy(*args,**kwargs):raise AssertionError('Full-page copy/crop allocated')
        source.copy=unnecessary_copy;source.crop=unnecessary_copy
        window._show(reset=False)
        with ImageTk.getimage(window._tk_img).convert('RGB') as actual:
            assert actual.tobytes()==expected.tobytes()
        expected.close()
    finally:
        window.destroy();source.close()


def test_manual_redetect_preserves_saved_order_and_normal_ui(gui,tmp_path,monkeypatch):
    from komicove_app import reader
    from komicove_app.reader_views import ReaderWindow
    monkeypatch.setattr(reader,'MANUAL_PANELS_FILE',str(tmp_path/'manual.json'))
    monkeypatch.setattr('komicove_app.reader_views.messagebox.showinfo',lambda *args,**kwargs:None)
    path=tmp_path/'guided.cbz';path.write_bytes(b'guided-ui-test')
    window=ReaderWindow(gui,str(path),Loader())
    try:
        manual=[[0,.55,1,1],[0,0,1,.45]];reader.save_manual_panels(window._content_key,0,manual)
        window._guided=True;window._show(reset=False);pump(gui)
        window._redetect_panels();pump(gui,lambda:not window._guide_pending)
        assert window._guide_manual
        assert [list(r) for r in window._regions]==manual
        assert reader.load_manual_panels(window._content_key,0)==manual
        for size in ('800x600','1280x860'):
            window.geometry(size);pump(gui);window._hud()
            assert window._guided_reader_actions.winfo_ismapped()
            for control in window._guided_header_items:
                assert control.winfo_rootx()+control.winfo_width()<=window.winfo_rootx()+window.winfo_width()
        window._toggle_guided();pump(gui)
        assert window._standard_reader_actions.winfo_ismapped()
        assert window._normal_reader_controls.winfo_ismapped()
        assert not window._guided_reader_actions.winfo_ismapped()
    finally:
        window.destroy()


def test_editor_redetect_recalculates_and_save_keeps_original_page(gui,tmp_path,monkeypatch):
    from komicove_app import reader
    from komicove_app.reader_views import ReaderWindow
    from komicove_app.panel_editor import PanelEditor
    monkeypatch.setattr(reader,'MANUAL_PANELS_FILE',str(tmp_path/'manual.json'))
    path=tmp_path/'editor.cbz';path.write_bytes(b'editor-ui-test')
    window=ReaderWindow(gui,str(path),Loader())
    try:
        window._edit_panels()
        pump(gui,lambda:any(isinstance(child,PanelEditor) for child in window.winfo_children()))
        editor=next(child for child in window.winfo_children() if isinstance(child,PanelEditor))
        editor.auto_regions=[[0,0,1,1]]
        editor._reset();pump(gui,lambda:not editor._detecting)
        assert len(editor.regions)==2
        assert reader.load_manual_panels(window._content_key,0) is None
        window._idx=1;editor._save()
        assert len(reader.load_manual_panels(window._content_key,0))==2
        assert reader.load_manual_panels(window._content_key,1) is None
    finally:
        window.destroy()


def test_editor_ai_does_not_block_interface_or_change_original_page(gui,tmp_path):
    from komicove_app.reader_views import ReaderWindow
    from komicove_app.panel_editor import PanelEditor
    from komicove_app.guided import DetectionCache
    entered,release=Event(),Event()
    class SlowAI:
        def detect(self,image,baseline,**kwargs):
            assert current_thread() is not main_thread()
            entered.set()
            assert release.wait(3)
            return baseline
        def close(self):release.set()
    path=tmp_path/'async-editor.cbz';path.write_bytes(b'async-editor-test')
    window=ReaderWindow(gui,str(path),Loader())
    try:
        window._guide_cache.close();window._guide_cache=DetectionCache(ai=SlowAI())
        window._edit_panels();pump(gui,entered.is_set)
        assert not any(isinstance(child,PanelEditor) for child in window.winfo_children())
        ran=[];gui.after_idle(lambda:ran.append(True));pump(gui,lambda:bool(ran))
        window._idx=1;release.set()
        pump(gui,lambda:any(isinstance(child,PanelEditor) for child in window.winfo_children()))
        editor=next(child for child in window.winfo_children() if isinstance(child,PanelEditor))
        assert len(editor.regions)==2
        editor.destroy();assert window._editor_cancel.is_set()
    finally:
        release.set();window.destroy()


def test_closing_reader_cancels_pending_editor_ai(gui,tmp_path):
    from komicove_app.reader_views import ReaderWindow
    from komicove_app.guided import DetectionCache
    entered,finished=Event(),Event()
    class WaitingAI:
        def detect(self,image,baseline,**kwargs):
            entered.set()
            try:
                assert kwargs['cancel'].wait(3)
                raise CancelledError()
            finally:finished.set()
        def close(self):pass
    path=tmp_path/'closing-editor.cbz';path.write_bytes(b'closing-editor-test')
    window=ReaderWindow(gui,str(path),Loader())
    try:
        window._guide_cache.close();window._guide_cache=DetectionCache(ai=WaitingAI())
        window._edit_panels();pump(gui,entered.is_set)
    finally:
        window.destroy()
    assert finished.wait(3)
    assert not window._guide_cache._items
