import queue
import threading
from types import SimpleNamespace

from komicove_app import library_views


def test_library_sync_does_not_wait_for_folder_scan_on_ui_thread(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    returned = threading.Event()

    class BusyIndex:
        def paths(self, *, visible_only):
            assert visible_only is False
            entered.set()
            assert release.wait(5)
            return []

        def snapshot(self):
            return {"books": {}}

    app = SimpleNamespace(
        _sync_job=None,
        _sync_running=False,
        _closing_app=False,
        _folder_index=BusyIndex(),
        _sync_events=queue.SimpleQueue(),
    )
    auth = SimpleNamespace(token="test-token")
    monkeypatch.setattr(library_views, "sync_snapshot", lambda: ({}, set(), {}))
    monkeypatch.setattr(library_views, "build_sync_payload", lambda *args: ([], {}))
    monkeypatch.setattr(library_views.api_client, "sync_library_state", lambda *args: [])

    caller = threading.Thread(
        target=lambda: (library_views.LibraryWindow._sync_library_state(app, auth), returned.set()),
        daemon=True,
    )
    caller.start()
    try:
        assert entered.wait(5)
        assert returned.wait(1), "Folder scan blocked the UI callback"
    finally:
        release.set()
        caller.join(5)

    assert app._sync_events.get(timeout=5) == ("test-token", [], {}, None)
