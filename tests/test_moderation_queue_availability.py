from threading import Barrier, Lock

from komicove_backend.api.routes import moderation


def test_asset_availability_checks_unique_files_concurrently(monkeypatch):
    barrier = Barrier(2)
    calls = []
    lock = Lock()

    def exists(name):
        with lock:
            calls.append(name)
        barrier.wait(timeout=2)
        return name == "present.cbz"

    monkeypatch.setattr(moderation, "asset_exists", exists)

    available = moderation._asset_availability(
        ["present.cbz", "missing.cbz", "present.cbz"]
    )

    assert available == {"present.cbz": True, "missing.cbz": False}
    assert sorted(calls) == ["missing.cbz", "present.cbz"]
