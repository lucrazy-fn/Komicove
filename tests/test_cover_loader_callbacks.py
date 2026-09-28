import threading

from komicove_app.runtime import CoverLoader


class ImmediateRoot:
    def after(self, _delay, callback):
        callback()

    def winfo_exists(self):
        return True


def test_same_cover_updates_every_visible_card():
    started = threading.Event()
    release = threading.Event()
    complete = threading.Event()
    received = []
    loader = CoverLoader(ImmediateRoot(), {})

    def load(_path):
        started.set()
        release.wait(2)
        return "cover"

    def callback(_path, image):
        received.append(image)
        if len(received) == 2:
            complete.set()

    loader._load = load
    try:
        loader.request("comic.cbz", callback)
        assert started.wait(2)
        loader.request("comic.cbz", callback)
        release.set()
        assert complete.wait(2)
        assert received == ["cover", "cover"]
    finally:
        release.set()
        loader.stop()
