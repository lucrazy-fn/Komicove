import tkinter as tk
from types import SimpleNamespace

from komicove_app import library_views


def test_moderation_card_component_is_imported():
    assert library_views.KomicoveCard is not None


class FakeLabel:
    def __init__(self, exists=True, fail_on_config=False):
        self.exists = exists
        self.fail_on_config = fail_on_config
        self.config_calls = []

    def winfo_exists(self):
        return self.exists

    def config(self, **kwargs):
        if self.fail_on_config:
            raise tk.TclError("invalid command name")
        self.config_calls.append(kwargs)


def owner(generation=1, tab="moderation"):
    return SimpleNamespace(
        _moderation_generation=generation,
        _active_tab=tab,
        _moderation_images=[],
    )


def test_late_cover_does_not_update_destroyed_label(monkeypatch):
    app = owner()
    label = FakeLabel(exists=False)
    monkeypatch.setattr(library_views.ImageTk, "PhotoImage", lambda image: None)

    library_views.LibraryWindow._set_moderation_cover(app, label, object(), 1)

    assert label.config_calls == []
    assert app._moderation_images == []


def test_old_cover_does_not_update_refreshed_moderation():
    app = owner(generation=2)
    label = FakeLabel()

    library_views.LibraryWindow._set_moderation_cover(app, label, None, 1)

    assert label.config_calls == []


def test_cover_update_handles_label_destroyed_during_config(monkeypatch):
    app = owner()
    label = FakeLabel(fail_on_config=True)
    monkeypatch.setattr(library_views.ImageTk, "PhotoImage", lambda image: object())

    library_views.LibraryWindow._set_moderation_cover(app, label, object(), 1)

    assert app._moderation_images == []


def test_unavailable_cover_updates_visible_label():
    app = owner()
    label = FakeLabel()

    library_views.LibraryWindow._set_moderation_cover(app, label, None, 1)

    assert label.config_calls and "text" in label.config_calls[0]


def test_late_moderation_list_does_not_update_new_screen():
    app = owner(generation=2)
    status = FakeLabel(exists=False)
    app._moderation_status = status
    app._moderation_grid = FakeLabel(exists=False)

    library_views.LibraryWindow._moderation_loaded(app, [], None, generation=1)

    assert status.config_calls == []
