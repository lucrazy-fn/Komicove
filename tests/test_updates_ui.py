import gc
import time
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
import pytest
from komicove_app import library_views as views, runtime, storage
from komicove_app.design.styles import KomicoveButton
from komicove_app.design.icons import clear_icon_cache
from komicove_client import releases


def children(widget):
    for child in widget.winfo_children():
        yield child
        yield from children(child)


def pump(root, condition):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        root.update()
        if condition():
            return
        time.sleep(.01)
    assert condition()


@pytest.fixture(scope='module')
def root():
    window = tk.Tk(); window.withdraw()
    yield window
    clear_icon_cache(); gc.collect(); window.destroy()


@pytest.mark.parametrize('language', ['pt-BR', 'en'])
def test_update_selection_changelog_date_and_real_download(monkeypatch, language, root):
    monkeypatch.setattr(runtime, 'LANG', language)
    records = [dict(id='fixture', title='Original title', version='0.2.2', source='panel',
        notes='# Original changelog\n\n**Original notes**', created_at='2026-10-06T10:00:00Z', url=releases.SITE_DOWNLOAD_URL),
        dict(id='no-download', title='Message without download', version='0.2.1', source='panel', notes='Original content', created_at='2026-10-06T09:00:00Z', url=None)]
    monkeypatch.setattr(views.updater, 'fetch', lambda: records)
    opened = []
    monkeypatch.setattr(views.webbrowser, 'open', opened.append)
    root._release_notes = lambda data: views.LibraryWindow._release_notes(root, data)
    try:
        views.LibraryWindow._check_updates(root)
        dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
        selector = next(w for w in children(dialog) if isinstance(w, ttk.Combobox))
        pump(root, lambda: selector.current() == 0)
        notes = next(w for w in children(dialog) if isinstance(w, tk.Text))
        assert 'Original notes' in notes.get('1.0', 'end')
        assert any('2026-10-06' in w.cget('text') for w in children(dialog) if isinstance(w, tk.Label))
        button = next(w for w in children(dialog) if isinstance(w, KomicoveButton))
        button._invoke()
        assert opened == [releases.SITE_DOWNLOAD_URL]
        selector.current(1); selector.event_generate('<<ComboboxSelected>>'); root.update()
        assert not button.winfo_ismapped() and notes.get('1.0', 'end').strip() == 'Original content'
        assert 'fixture' in storage.load_prefs()['update_seen_messages']
        assert 'no-download' in storage.load_prefs()['update_seen_messages']
    finally:
        for widget in root.winfo_children(): widget.destroy()
        clear_icon_cache(); gc.collect()


def test_redeemed_role_persists_existing_session_and_refreshes_profile(monkeypatch):
    user = SimpleNamespace(token='fixture-session', user_id='fixture-user', username='fixture', display_name='Reader', email='fixture@example.invalid', role='user', is_moderator=False)
    refreshed, saved = [], []
    host = SimpleNamespace(current_user=user, _open_profile=lambda: refreshed.append(True))
    monkeypatch.setattr(views.session_store, 'save_session', saved.append)
    views.LibraryWindow._profile_updated(host, dict(role='contributor', is_moderator=False, display_name='Reader', email=user.email))
    assert saved[0].token == 'fixture-session' and saved[0].role == 'contributor'
    assert not saved[0].is_moderator and user.email == 'fixture@example.invalid'
    assert refreshed == [True]
