import math
import threading
import time
import traceback
from pathlib import Path
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


@pytest.mark.parametrize('size', [1000, 5000, 10000])
def test_phase6_sizes_keep_virtualization_cache_limits_and_last_item(library, size):
    root, fixture = library
    paths = [str(Path(fixture[0]).parent / f'Issue {i}.cbz') for i in range(size)]
    root._scan = lambda: paths
    root._refresh_library()
    pump(root, lambda: root._library_grid is not None)
    for position in (0, .2, .7, 1, .5, 0, 1):
        root._lib_canvas.yview_moveto(position)
        root.update()
        assert len(root._card_map) < 100
        assert len(root._capa_cache) <= root._cover_loader.MAX_CACHED
        assert len(root._cover_loader._pending) < 100
    assert paths[-1] in root._card_map
    index = root._library_query
    root._search_query = 'Issue 99'
    root._populate_library_grid()
    pump(root, lambda: root._library_grid is not None)
    assert root._library_query is index
    assert root._library_grid.paths == [p for p in paths if 'Issue 99' in p]


def test_custom_cover_replaced_at_same_path_is_refreshed(library, tmp_path, monkeypatch):
    from komicove_app import book_metadata
    root, paths = library
    cover = tmp_path / 'custom.png'
    path = paths[0]
    Image.new('RGB', (8, 12), 'red').save(cover)
    book_metadata.save(path, {'cover': str(cover)})

    def load(key):
        assert threading.get_ident() != main_thread
        with Image.open(key[1]) as source:
            return source.convert('RGB')

    main_thread = threading.get_ident()
    monkeypatch.setattr(root._cover_loader, '_load', load)
    root._scan = lambda: [path]
    try:
        root._refresh_library()
        pump(root, lambda: path in root._card_map and root._card_map[path]._img_pil is not None)
        assert root._card_map[path]._img_pil.getpixel((0, 0)) == (255, 0, 0)
        Image.new('RGB', (8, 12), 'blue').save(cover)
        root._refresh_library()
        pump(root, lambda: path in root._card_map and root._card_map[path]._img_pil is not None)
        assert root._card_map[path]._img_pil.getpixel((0, 0)) == (0, 0, 255)
    finally:
        book_metadata.save(path, {'cover': ''})


@pytest.mark.parametrize('size', [1000, 5000, 10000])
def test_collections_and_details_virtualize_without_changing_actions(library, size):
    root, fixture = library
    paths = [str(Path(fixture[0]).parent / f'Folder {i}' / 'Issue 1.cbz') for i in range(size)]
    root._collection_groups = None
    root._collection_query = ''
    root._col_filter = 'all'
    root._col_sort = 'name'
    root._scan = lambda: paths
    root._show_collections()
    pump(root, lambda: root._library_grid is not None and not root._library_preparing, timeout=20)
    grid = root._library_grid
    assert len(grid.paths) == size + 1
    assert len(grid.cards) < 30
    for position in (0, .5, 1, .25, 1):
        grid.canvas.yview_moveto(position)
        root.update()
        assert len(grid.cards) < 30
        assert len(root._cover_loader._pending) < 90
    group = grid.paths[-1]
    assert group['files'] == paths
    opened = []
    root._open = lambda path, siblings=None: opened.append((path, siblings))
    root._show_collection_detail(group)
    pump(root, lambda: root._library_grid is not None and root._library_grid is not grid
         and not root._library_preparing, timeout=20)
    details = root._library_grid
    assert details.paths == paths
    for position in (0, .5, 1, .1, 1):
        details.canvas.yview_moveto(position)
        root.update()
        assert len(details.cards) < 50
    card = root._card_map[paths[-1]]
    assert card.frame.winfo_viewable()
    card.cv.event_generate('<Button-1>', x=20, y=20)
    assert opened == [(paths[-1], paths)]
    root._show_collections()
    pump(root, lambda: root._library_grid is not None and not root._library_preparing)
    assert details.closed and not details.cards


def test_collection_queries_reuse_orders_and_invalidate_progress(library, monkeypatch):
    from komicove_app import library_widgets, storage
    root, fixture = library
    paths = [str(Path(fixture[0]).parent / f'Folder {folder}' / f'Issue {i}.cbz')
             for folder in ('A', 'B') for i in (1, 2)]
    root._scan = lambda: paths
    root._collection_groups = None
    root._collection_query = ''
    root._col_sort = 'progress'
    storage.save_progress(paths[0], 0)
    monkeypatch.setattr(library_widgets, 'collection_read_count',
                        lambda files: pytest.fail('Card reread all progress on UI'))
    root._show_collections()
    pump(root, lambda: not root._library_preparing)
    order = root._collection_orders['progress']
    assert order['subfolders'][0]['name'] == 'Folder A'
    root._collection_query = 'Folder B'
    root._show_collections()
    pump(root, lambda: not root._library_preparing)
    assert root._collection_orders['progress'] is order
    assert [item['name'] for item in root._library_grid.paths] == ['Folder B']
    storage.save_progress(paths[2], 0)
    storage.save_progress(paths[3], 0)
    root._collection_query = ''
    root._show_collections()
    pump(root, lambda: not root._library_preparing)
    assert root._collection_orders['progress'] is not order
    assert root._collection_orders['progress']['subfolders'][0]['name'] == 'Folder B'


def test_metadata_filter_controls_reuse_snapshot_without_io(library, monkeypatch):
    from komicove_app import library_views
    root, paths = library
    root._scan = lambda: paths
    root._refresh_library()
    pump(root, lambda: not root._library_preparing)
    index = root._library_query
    index.field_choices = {'series': ['Series 1'], 'writer': ['Author']}
    monkeypatch.setattr(root, '_scan', lambda: pytest.fail('Filter dialog rescanned library'))
    monkeypatch.setattr(library_views, 'get_comic_info', lambda *args: pytest.fail('Filter dialog read metadata on UI'))
    root._metadata_filters()
    dialogs = [widget for widget in root.winfo_children() if isinstance(widget, library_views.tk.Toplevel)]
    assert len(dialogs) == 1
    try:
        entries = [widget for widget in dialogs[0].winfo_children()
                   if isinstance(widget, library_views.ttk.Combobox)]
        assert [tuple(entry['values']) for entry in entries] == [('', 'Series 1'), ('', 'Author')]
        assert all(str(entry['state']) == 'readonly' for entry in entries)
        assert root._library_query is index
    finally:
        dialogs[0].destroy()


def test_repeated_queries_release_old_grid_callbacks(library):
    import gc
    import weakref
    root, paths = library
    root._scan = lambda: paths
    root._refresh_library()
    pump(root, lambda: not root._library_preparing)
    canvas = root._lib_canvas
    command_count = len(canvas._tclCommands)
    old_grids = []
    for i in range(20):
        old_grids.append(weakref.ref(root._library_grid))
        root._search_query = 'Issue ' + str(i % 10)
        root._populate_library_grid()
        pump(root, lambda: not root._library_preparing)
        assert len(canvas._tclCommands) <= command_count + 5
    gc.collect()
    assert all(grid() is None for grid in old_grids)
