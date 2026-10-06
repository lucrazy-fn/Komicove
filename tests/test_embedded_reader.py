import io
import time
import tkinter as tk
import traceback
import zipfile

import pytest
from PIL import Image


def pump(root,condition=lambda:True):
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        root.update()
        if condition():
            root.update_idletasks()
            return
        time.sleep(.01)
    assert condition()


@pytest.fixture
def comic(tmp_path):
    path=tmp_path/'Example.cbz'
    with zipfile.ZipFile(path,'w') as archive:
        for number in range(6):
            with Image.new('RGB',(240,360),(20+number*30,30,40)) as image:
                data=io.BytesIO();image.save(data,'PNG')
                archive.writestr(f'{number:03}.png',data.getvalue())
    return path


@pytest.fixture
def library(monkeypatch):
    from komicove_app.library_views import LibraryWindow
    from komicove_app.storage import save_prefs
    from komicove_app.design.icons import clear_icon_cache
    clear_icon_cache()
    save_prefs(lang='pt',reader_guided=False,reader_auto_fit=True)
    monkeypatch.setattr(LibraryWindow,'_show_auth',lambda self:None)
    class Covers:
        def __init__(self,*args):pass
        def request(self,*args):pass
        def clear_queue(self):pass
        def stop(self):pass
    monkeypatch.setattr('komicove_app.library_views.CoverLoader',Covers)
    root=LibraryWindow();root.geometry('1280x860');root.deiconify()
    root._cover_loader=Covers(root,root._capa_cache)
    root._scan=lambda:[]
    root._build_shell();root._refresh_library()
    errors=[];root.report_callback_exception=lambda *error:errors.append(''.join(traceback.format_exception(*error)))
    yield root
    root.destroy()
    clear_icon_cache()
    if errors:pytest.fail('\n'.join(errors))


def same_window_return_state_shortcuts_and_progress(library,comic,monkeypatch):
    from komicove_app.reader_views import EmbeddedReader
    from komicove_app.storage import get_progress_page
    library._search_query='Example';library._status_filter='unread'
    library._book_sort='title_desc';library._refresh_library()
    pump(library,lambda:not library._library_preparing)
    library.update_idletasks()
    content=tk.Frame(library._lib_content,height=3000,width=600)
    content.pack();library.update_idletasks();library._lib_canvas.yview_moveto(.45)
    initial_scroll=library._lib_canvas.yview()[0]
    old_shell=library._main
    original_window=library.winfo_id()
    library._capa_cache['test']=Image.new('RGB',(20,20))
    original_right=library.bind('<Right>')
    library._open(str(comic),[str(comic)])
    pump(library,lambda:library._embedded_reader is not None)
    reader=library._embedded_reader
    assert isinstance(reader,EmbeddedReader)
    assert reader.winfo_toplevel() is library
    assert library.winfo_id()==original_window
    assert not any(isinstance(w,tk.Toplevel) for w in library.winfo_children())
    assert not old_shell.winfo_exists() and not library._capa_cache
    pump(library,lambda:reader._cv.winfo_width()>100 and not reader._guide_pending)
    reader._idx=2;reader._show(reset=False)
    # Rebuilding controls must not duplicate root hotkeys.
    before=library.bind('<Right>');reader._build();after=library.bind('<Right>')
    assert before.count('dispatch')==after.count('dispatch')==1
    monkeypatch.setattr(library,'_refresh_library',lambda:restore_content(library))
    variables=list(reader._owned_tk_variables)
    reader._close()
    pump(library,lambda:not library._library_preparing)
    assert library._embedded_reader is None
    assert library._search_query=='Example' and library._status_filter=='unread'
    assert library._book_sort=='title_desc'
    assert get_progress_page(str(comic))==2
    assert library.bind('<Right>')==original_right
    assert abs(library._lib_canvas.yview()[0]-initial_scroll)<.02
    assert reader._guide_cache._ai is None or reader._guide_cache._ai._closed
    assert not reader._scheduled
    assert not reader._owned_tk_variables
    assert all(variable._tk is None and variable._root is None for variable in variables)


def restore_content(root):
    from komicove_app.library_views import LibraryWindow
    LibraryWindow._refresh_library(root)
    tk.Frame(root._lib_content,height=3000,width=600).pack()


def book_switch_and_window_close_save_reader(library,comic):
    from komicove_app.storage import get_progress_page
    library._open(str(comic),[str(comic)])
    pump(library,lambda:library._embedded_reader is not None)
    first=library._embedded_reader;pump(library)
    first._idx=3
    library._open(str(comic),[str(comic)])
    pump(library,lambda:library._embedded_reader is not first)
    second=library._embedded_reader
    assert second is not first and first._destroyed
    assert second._idx==3
    assert library._reader_return_state['tab']=='library'
    second._idx=4
    library.destroy()
    assert get_progress_page(str(comic))==4
    assert second._destroyed


def reader_theme_guided_dialogs_and_fullscreen(library,comic):
    library._open(str(comic),[str(comic)])
    pump(library,lambda:library._embedded_reader is not None)
    reader=library._embedded_reader
    pump(library)
    reader._toggle_guided()
    pump(library,lambda:not reader._guide_pending)
    assert reader._guided
    reader._fullscreen();pump(library,lambda:bool(library.attributes('-fullscreen')))
    reader._escape();pump(library,lambda:not library.attributes('-fullscreen'))
    reader._open_webtoon()
    assert reader._webtoon.winfo_toplevel() is library
    assert not isinstance(reader._webtoon,tk.Toplevel)
    webtoon=reader._webtoon
    webtoon._fullscreen();pump(library,lambda:bool(library.attributes('-fullscreen')))
    assert not webtoon._bar.winfo_ismapped() and not webtoon.scrollbar.winfo_ismapped()
    webtoon._escape();pump(library,lambda:not library.attributes('-fullscreen'))
    assert webtoon._bar.winfo_ismapped()
    reader._webtoon.destroy()
    assert reader._webtoon is None
    reader._reader_preferences()
    dialog=next(w for w in reader.winfo_children() if isinstance(w,tk.Toplevel))
    dialog.destroy()
    reader._close()
    assert not library.attributes('-fullscreen')


def collection_detail_return_route(library,comic,monkeypatch):
    collection={'name':'Example','files':[str(comic)],'alias_key':'test:example'}
    library._active_tab='collections';library._show_collection_detail(collection)
    library._open(str(comic),[str(comic)])
    pump(library,lambda:library._embedded_reader is not None)
    reader=library._embedded_reader;pump(library)
    reader._close()
    assert library._active_tab=='collections'
    assert library._reader_collection is collection
    # A resize queued by the old library must not repaint destroyed widgets
    # or replace the collection screen after returning from the reader.
    library._check_ncols()
    library._populate_library_grid()
    assert library._active_tab=='collections'


def test_single_window_reader_lifecycle(library,comic,monkeypatch):
    # One interpreter per app, like production; exercise multiple navigations
    # and book switches before finally closing the same host window.
    same_window_return_state_shortcuts_and_progress(library,comic,monkeypatch)
    reader_theme_guided_dialogs_and_fullscreen(library,comic)
    collection_detail_return_route(library,comic,monkeypatch)
    library._reader_collection=None;library._active_tab='library'
    opening_is_nonblocking_and_cancelled(library,comic,monkeypatch)
    book_switch_and_window_close_save_reader(library,comic)


def opening_is_nonblocking_and_cancelled(library,comic,monkeypatch):
    from threading import Event, current_thread, main_thread
    from komicove_app.archive import SmartPageLoader
    entered,release,closed,heartbeat=Event(),Event(),Event(),Event()
    class DelayedLoader(SmartPageLoader):
        def __init__(self,path):
            assert current_thread() is not main_thread()
            entered.set()
            assert release.wait(5)
            super().__init__(path)
        def close(self):
            super().close()
            closed.set()
    with monkeypatch.context() as patch:
        patch.setattr('komicove_app.library_views.SmartPageLoader',DelayedLoader)
        try:
            start=time.monotonic()
            library._open(str(comic),[str(comic)])
            assert time.monotonic()-start<.5
            assert entered.wait(2)
            library.after(0,heartbeat.set)
            pump(library,heartbeat.is_set)
            assert library._embedded_reader is None
            library._cancel_reader_open()
            release.set()
            assert closed.wait(3)
            pump(library)
            assert library._embedded_reader is None
            assert not library._opening_poll and library._opening_handoff is None
        finally:
            release.set()


def test_cover_clear_discards_inflight_results(monkeypatch):
    from threading import Event
    from komicove_app.runtime import CoverLoader
    entered,release,finished=Event(),Event(),Event()
    image=Image.new('RGB',(20,20))
    def load(self,path):
        entered.set();release.wait(3);finished.set();return image
    monkeypatch.setattr(CoverLoader,'_load',load)
    class Root:
        def after(self,*args):return 'poll'
        def after_cancel(self,*args):pass
        def winfo_exists(self):raise AssertionError('Obsolete result reached UI')
    cache={};loader=CoverLoader(Root(),cache)
    try:
        loader.request('one',lambda *args:None)
        assert entered.wait(3)
        loader.stop();release.set()
        loader._thread.join(3)
        assert finished.is_set() and not loader._thread.is_alive()
        assert not cache and not loader._pending
        with pytest.raises(ValueError):image.getpixel((0,0))
    finally:
        loader.stop();release.set()
