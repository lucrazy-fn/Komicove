import math
import threading
import time
import traceback
from types import SimpleNamespace

import pytest
from PIL import Image


def pump(root, condition, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root.update()
        if condition():
            root.update_idletasks()
            return
        time.sleep(.01)
    assert condition()


@pytest.fixture(scope='module')
def library_session(tmp_path_factory):
    from komicove_app import library_views, library_widgets
    from komicove_app.design.icons import clear_icon_cache
    from komicove_app.storage import save_prefs
    clear_icon_cache()
    monkeypatch = pytest.MonkeyPatch()
    save_prefs(lang='pt', book_sort='title')
    monkeypatch.setattr(library_views.LibraryWindow, '_show_auth', lambda self: None)
    monkeypatch.setattr(library_views.CoverLoader, '_load', lambda self, path: Image.new('RGB', (136, 188), 'red'))
    library_widgets._COMIC_INFO_CACHE.clear()
    root = library_views.LibraryWindow()
    root._cover_loader = library_views.CoverLoader(root, root._capa_cache)
    root._folder_watcher.close()
    root.geometry('1280x860')
    root.deiconify()
    root._scan = lambda: []
    root._build_shell()
    root.update()
    errors = []
    root.report_callback_exception = lambda *error: errors.append(''.join(traceback.format_exception(*error)))
    tmp_path = tmp_path_factory.mktemp('library')
    yield root, [str(tmp_path / f'Issue {number}.cbz') for number in range(3000)]
    root.destroy()
    clear_icon_cache()
    library_widgets._COMIC_INFO_CACHE.clear()
    monkeypatch.undo()
    assert not errors, '\n'.join(errors)


@pytest.fixture
def library(library_session):
    root, paths = library_session
    root._search_query = ''
    root._status_filter = 'all'
    root._book_sort = 'title'
    from komicove_app import library_widgets
    library_widgets._COMIC_INFO_CACHE.clear()
    return root, paths


def test_large_library_keeps_only_viewport_cards_and_can_open_last_issue(library):
    root, paths = library
    root._scan = lambda: paths
    opened = []
    root._open = lambda path: opened.append(path)
    root._refresh_library()
    pump(root, lambda: root._library_grid is not None)
    canvas, grid = root._lib_canvas, root._library_grid
    assert [item for item in canvas.find_all() if canvas.type(item) == 'window'] == [root._lib_win_id]
    assert float(canvas.cget('scrollregion').split()[3]) > 32767
    limit = grid.columns * (math.ceil(canvas.winfo_height() / grid.row_height) + 4)
    for position in (0, .3, .7, 1, .1, 1):
        canvas.yview_moveto(position)
        root.update()
        assert len(root._card_map) <= limit
        assert len(grid.cards) == len(root._card_map)
        assert [item for item in canvas.find_all() if canvas.type(item) == 'window'] == [root._lib_win_id]
    last = root._card_map[paths[-1]]
    last.cv.event_generate('<Button-1>', x=20, y=20)
    assert opened == [paths[-1]]
    assert root._lib_canvas is canvas
    assert root._library_grid is grid


def test_refresh_preserves_scroll_and_filters_and_sort_remain_correct(library):
    root, paths = library
    root._scan = lambda: paths
    root._refresh_library()
    pump(root, lambda: root._library_grid is not None)
    root._lib_canvas.yview_moveto(.6)
    root.update()
    position = root._lib_canvas.yview()[0]
    root._refresh_library(preserve_scroll=True)
    pump(root, lambda: root._library_grid is not None)
    assert abs(root._lib_canvas.yview()[0] - position) < .01
    root._search_query = 'Issue 299'
    root._book_sort = 'title_desc'
    root._populate_library_grid()
    pump(root, lambda: root._library_grid is not None)
    assert root._library_grid.paths == list(reversed([paths[299], *paths[2990:3000]]))
    assert root._lib_canvas.yview()[0] == 0, (
        root._lib_canvas.yview(), root._lib_canvas.cget('scrollregion'),
        root._lib_canvas.winfo_height(), root._library_grid.row_height,
        root._lib_content.winfo_reqheight(), root._library_grid.columns)


def test_rapid_scroll_and_hover_keep_card_geometry_and_release_bindings(library):
    root, paths = library
    root._scan = lambda: paths
    root._refresh_library()
    pump(root, lambda: root._library_grid is not None)
    canvas, grid = root._lib_canvas, root._library_grid
    command_count = len(canvas._tclCommands)
    first = next(iter(root._card_map.values()))
    hit_item = first._hit_item
    first._on_enter(None)
    pump(root, lambda: first._alpha == 1 and first._anim_id is None)
    assert first._hit_item == hit_item and canvas.type(hit_item) == 'image'
    for direction in (1, -1):
        for step in range(35):
            canvas.yview_scroll(3 * direction, 'units')
            root.update()
            for card, tag in grid.cards.values():
                bounds = canvas.bbox(tag)
                assert abs(bounds[1] - card.y) <= 1
                assert bounds[3] - bounds[1] <= card.height + 2
                assert all(canvas.type(item) != 'window' for item in canvas.find_withtag(tag))
    assert len(canvas._tclCommands) < command_count + 50
    assert len(root._card_map) < 100


def test_slow_metadata_never_blocks_tk_or_overwrites_new_search(library, monkeypatch):
    from komicove_app import library_widgets
    root, paths = library
    entered, release = threading.Event(), threading.Event()
    main_thread = threading.get_ident()

    def read(path):
        assert threading.get_ident() != main_thread
        if path == paths[0]:
            entered.set()
            release.wait(5)
        return {}

    monkeypatch.setattr(library_widgets, 'read_comic_info', read)
    root._scan = lambda: paths
    try:
        root._refresh_library()
        pump(root, entered.is_set)
        cancel = root._library_prepare_cancel
        root._check_ncols()
        assert root._library_prepare_cancel is cancel and not cancel.is_set()
        heartbeat = []
        root.after(0, lambda: heartbeat.append(True))
        pump(root, lambda: bool(heartbeat))
        root._scan = lambda: [paths[-1]]
        root._search_query = '2999'
        root._populate_library_grid()
        pump(root, lambda: root._library_grid is not None)
        current = root._library_grid
        assert current.paths == [paths[-1]]
        release.set()
        root.update()
        assert root._library_grid is current
    finally:
        release.set()


def test_canvas_card_preserves_tooltips_favorites_status_and_open_menu(library, monkeypatch):
    from komicove_app import library_widgets, storage
    root, paths = library
    shown, opened, menus = [], [], []
    tooltip = SimpleNamespace(show=lambda widget, path: shown.append(path), hide=lambda: None)
    root._meta_tooltip = tooltip
    root._scan = lambda: paths[:20]
    root._open = lambda path: opened.append(path)
    root._refresh_library()
    pump(root, lambda: root._library_grid is not None)
    card = root._card_map[paths[0]]
    monkeypatch.setattr(library_widgets.tk.Menu, 'tk_popup', lambda menu, *args: menus.append(menu))
    try:
        card.cv.event_generate('<Motion>', x=20, y=20)
        root.update()
        assert paths[0] in shown
        card._show_context_menu(SimpleNamespace(x_root=0, y_root=0))
        menu = menus[-1]
        menu.invoke(0)
        assert storage.is_favorite(paths[0])
        menu.invoke(3)
        assert storage.get_manual_status(paths[0]) == 'done'
        # The fixture has no source file, so availability takes precedence over progress.
        assert card._unavailable
        menu.invoke(5)
        assert opened == [paths[0]]
        root._library_grid.close()
        assert not card.winfo_exists() and card._tk_img is None and card._hit_photo is None
    finally:
        root._meta_tooltip = None
        for menu in menus:
            menu.destroy()
        storage.set_manual_status(paths[0], None)
        if storage.is_favorite(paths[0]):
            storage.toggle_favorite(paths[0])


def test_navigating_away_closes_virtual_cards_and_ignores_late_covers(library):
    root, paths = library
    root._scan = lambda: paths
    root._refresh_library()
    pump(root, lambda: root._library_grid is not None)
    grid = root._library_grid
    root._show_folders()
    root.update()
    assert grid.closed and not grid.cards
    assert not root._card_map
    root._refresh_library()
    pump(root, lambda: root._library_grid is not None and root._library_grid is not grid)
    assert len(root._card_map) < 100
