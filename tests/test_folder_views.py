import tkinter as tk
from types import SimpleNamespace

import pytest

from komicove_app.folder_views import render_folders, update_folders
from komicove_app.monitored_folders import FolderIndex
from komicove_app.runtime import THEME
from komicove_app.design.icons import clear_icon_cache


@pytest.fixture(scope="module")
def tk_session():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Requires a graphical Tk session")
    root.withdraw()
    clear_icon_cache()
    yield root
    clear_icon_cache()
    root.destroy()


@pytest.fixture
def folder_window(tmp_path, tk_session):
    root = tk_session
    root.geometry("1000x700")
    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)
    main = tk.Frame(root, bg=THEME["bg"])
    main.pack(fill="both", expand=True)
    index = FolderIndex(tmp_path / "folders.json")
    for n in range(12):
        index.add(tmp_path / f"folder-{n}")
    window = SimpleNamespace(_main=main, _folder_index=index, _search_query="", _folder_report=None,
        _add_monitored_folder=lambda: None, _metadata_filters=lambda: None,
        _refresh_library=lambda: None, _rescan_folders=lambda *args: None, after_idle=root.after_idle)
    window._folder_watcher = SimpleNamespace(refresh=lambda: None)
    yield root, window, errors
    clear_icon_cache()
    if window._main.winfo_exists():
        window._main.destroy()


def test_background_checks_keep_widgets_and_scroll_position(folder_window):
    root, window, errors = folder_window
    render_folders(window, THEME)
    root.update_idletasks()
    canvas = window._folder_canvas
    widgets = tuple(window._main.winfo_children())
    callbacks = tuple(window._folder_row_updates.values())
    canvas.yview_moveto(.4)
    position = canvas.yview()
    for n in range(50):
        for row in window._folder_index.data["folders"].values():
            row.update(checked=1700000000+n*10, count=n, status="updated", new=0)
        update_folders(window, THEME)
        root.update_idletasks()
    assert window._folder_canvas is canvas
    assert tuple(window._main.winfo_children()) == widgets
    assert tuple(window._folder_row_updates.values()) == callbacks
    assert canvas.yview() == position
    assert not errors


def test_summary_is_updated_without_rebuilding_table(folder_window):
    root, window, errors = folder_window
    render_folders(window, THEME)
    root.update_idletasks()
    canvas = window._folder_canvas
    window._folder_report = dict(added=2, duplicates=5, invalid=0)
    update_folders(window, THEME)
    summary = window._folder_summary
    for _ in range(10):
        update_folders(window, THEME)
    assert window._folder_summary is summary
    assert window._folder_canvas is canvas
    window._folder_report = None
    update_folders(window, THEME)
    assert not summary.winfo_exists()
    assert not errors


def test_reopening_after_navigation_and_shell_rebuild_has_no_stale_callbacks(folder_window):
    root, window, errors = folder_window
    window._folder_report = dict(added=1, duplicates=0, invalid=0)
    render_folders(window, THEME)
    root.update_idletasks()
    original = window._folder_canvas
    # Other pages remove the main Configure binding and all its children.
    window._main.unbind("<Configure>")
    for child in window._main.winfo_children():
        child.destroy()
    assert not original.winfo_exists()
    render_folders(window, THEME)
    update_folders(window, THEME)
    root.update_idletasks()
    # Sidebar navigation can replace the main frame itself.
    window._main.destroy()
    window._main = tk.Frame(root, bg=THEME["bg"])
    window._main.pack(fill="both", expand=True)
    render_folders(window, THEME)
    update_folders(window, THEME)
    root.update_idletasks()
    assert window._folder_canvas.winfo_exists()
    assert not errors


def test_update_recovers_if_folder_widgets_were_destroyed(folder_window):
    root, window, errors = folder_window
    render_folders(window, THEME)
    window._folder_canvas.destroy()
    update_folders(window, THEME)
    root.update_idletasks()
    assert window._folder_canvas.winfo_exists()
    assert not errors


def test_visible_toggle_persists_without_rebuilding_and_back_button_navigates(folder_window):
    root, window, errors = folder_window
    from komicove_app.design.styles import KomicoveButton
    from komicove_app.translations import ui
    visits = []
    window._refresh_library = lambda: visits.append("library")
    render_folders(window, THEME)
    root.update_idletasks()
    canvas = window._folder_canvas
    key = next(iter(window._folder_toggle_buttons))
    toggle = window._folder_toggle_buttons[key]
    toggle._invoke()
    assert not FolderIndex(window._folder_index.filename).snapshot()["folders"][key]["enabled"]
    assert toggle.text == ui("Ativar", "Enable")
    toggle._invoke()
    assert window._folder_index.snapshot()["folders"][key]["enabled"]
    assert window._folder_canvas is canvas
    def buttons(widget):
        for child in widget.winfo_children():
            if isinstance(child, KomicoveButton):
                yield child
            yield from buttons(child)
    back = next(b for b in buttons(window._main) if b.text == ui("Voltar à biblioteca", "Back to library"))
    back._invoke()
    assert visits == ["library"]
    assert not errors


@pytest.mark.parametrize("scaling", [1.0, 1.5, 2.0])
def test_last_folder_and_toggle_are_not_clipped_at_different_display_scales(folder_window, scaling):
    root, window, errors = folder_window
    previous = root.tk.call("tk", "scaling")
    try:
        root.tk.call("tk", "scaling", scaling)
        window._folder_index.data["folders"] = dict(list(window._folder_index.data["folders"].items())[:2])
        render_folders(window, THEME)
        root.update_idletasks()
        last = list(window._folder_toggle_buttons.values())[-1]
        state_box = last.master
        row = state_box.master
        content = row.master
        assert content.winfo_height() >= content.winfo_reqheight()
        assert row.winfo_y() + row.winfo_height() <= content.winfo_height()
        assert state_box.winfo_y() + last.winfo_y() + last.winfo_height() <= row.winfo_height()
        assert not errors
    finally:
        root.tk.call("tk", "scaling", previous)
