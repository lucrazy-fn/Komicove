import threading
import time

from PIL import Image

from komicove_app.runtime import CoverLoader


class ImmediateRoot:
    def __init__(self):
        self.thread = threading.get_ident()
        self.jobs = {}
        self.serial = 0

    def after(self, _delay, callback):
        assert threading.get_ident() == self.thread
        self.serial += 1
        self.jobs[self.serial] = callback
        return self.serial

    def after_cancel(self, job):
        assert threading.get_ident() == self.thread
        self.jobs.pop(job, None)

    def pump(self, condition):
        deadline = time.monotonic() + 3
        while not condition() and time.monotonic() < deadline:
            jobs, self.jobs = self.jobs, {}
            for callback in jobs.values():
                callback()
            time.sleep(.01)
        assert condition()

    def winfo_exists(self):
        return True


def test_same_cover_updates_every_visible_card():
    started = threading.Event()
    release = threading.Event()
    complete = threading.Event()
    received = []
    root = ImmediateRoot()
    loader = CoverLoader(root, {})

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
        root.pump(complete.is_set)
        assert received == ["cover", "cover"]
    finally:
        release.set()
        loader.stop()
        loader._thread.join(2)


def test_missing_archive_does_not_warn_about_corrupt_cover(tmp_path, monkeypatch, caplog):
    from komicove_app import runtime
    monkeypatch.setattr(runtime, "_cover_cache_path", lambda path: str(tmp_path / "missing.webp"))
    loader = CoverLoader(ImmediateRoot(), {})
    try:
        assert loader._load(str(tmp_path / "missing.cbr")) is None
        assert not caplog.records
    finally:
        loader.stop()
        loader._thread.join(2)


def test_missing_archive_keeps_cached_cover(tmp_path, monkeypatch):
    from komicove_app import runtime
    cover = tmp_path / "cached.png"
    Image.new("RGB", (10, 15), "red").save(cover)
    monkeypatch.setattr(runtime, "_cover_cache_path", lambda path: str(cover))
    loader = CoverLoader(ImmediateRoot(), {})
    try:
        image = loader._load(str(tmp_path / "missing.cbr"))
        assert image.getpixel((0, 0)) == (255, 0, 0)
        image.close()
    finally:
        loader.stop()
        loader._thread.join(2)


def test_cover_cache_and_pending_requests_are_bounded(monkeypatch):
    root = ImmediateRoot()
    monkeypatch.setattr(CoverLoader, 'MAX_CACHED', 5)
    loader = CoverLoader(root, {})
    loader._load = lambda path: Image.new('RGB', (4, 4))
    received = []
    try:
        for number in range(30):
            loader.request(str(number), lambda path, pil: received.append((path, threading.get_ident())))
        root.pump(lambda: len(received) == 30)
        assert len(loader._cache) == 5
        assert all(thread == root.thread for _, thread in received)
        assert not loader._pending
        callback = lambda *args: None
        loader.request('offscreen', callback)
        loader.cancel('offscreen', callback)
        assert 'offscreen' not in loader._queue
        assert 'offscreen' not in loader._pending
    finally:
        loader.stop()
        loader._thread.join(2)


def test_cached_callback_is_cancelled_when_screen_changes():
    root = ImmediateRoot()
    loader = CoverLoader(root, {'one': Image.new('RGB', (4, 4))})
    received = []
    try:
        loader.request('one', lambda *args: received.append(args))
        loader.clear_queue()
        for callback in list(root.jobs.values()):
            callback()
        assert not received
    finally:
        loader.stop()
        loader._thread.join(2)


def test_cached_covers_are_batched_and_individually_cancellable():
    root = ImmediateRoot()
    image = Image.new('RGB', (4, 4))
    loader = CoverLoader(root, {'cached': image})
    received = []
    cancelled = lambda *args: received.append('cancelled')
    try:
        loader.request('cached', cancelled)
        loader.cancel('cached', cancelled)
        for number in range(12):
            loader.request('cached', lambda *args, n=number: received.append(n))
        assert len(root.jobs) == 1
        job = root.jobs.pop(loader._poll)
        job()
        assert 0 < len(received) <= loader.DELIVERY_BATCH
        root.pump(lambda: len(received) == 12)
        assert received == list(range(12))
    finally:
        loader.stop()
        loader._thread.join(2)


def test_slow_cached_cover_callback_yields_to_ui(monkeypatch):
    from komicove_app import runtime
    root = ImmediateRoot()
    loader = CoverLoader(root, {'cached': Image.new('RGB', (4, 4))})
    clock = [0.]
    monkeypatch.setattr(runtime.time, 'perf_counter', lambda: clock[0])
    received = []
    def callback(*args):
        received.append(True)
        clock[0] += loader.DELIVERY_SECONDS * 2
    try:
        for _ in range(8):
            loader.request('cached', callback)
        root.jobs.pop(loader._poll)()
        assert len(received) == 1
        root.pump(lambda: len(received) == 8)
    finally:
        loader.stop()
        loader._thread.join(2)


def test_cover_callback_can_request_another_cover_without_duplicate_timers():
    root = ImmediateRoot()
    loader = CoverLoader(root, {'cached': Image.new('RGB', (4, 4))})
    received = []
    def callback(*args):
        received.append(True)
        if len(received) == 1:
            loader.request('cached', callback)
    try:
        loader.request('cached', callback)
        root.jobs.pop(loader._poll)()
        assert received == [True, True]
        assert len(root.jobs) == 1
    finally:
        loader.stop()
        loader._thread.join(2)
        assert not loader._thread.is_alive()


def test_large_jpeg_cover_is_decoded_at_thumbnail_size(tmp_path, monkeypatch):
    import io
    from komicove_app import runtime
    data = io.BytesIO()
    Image.new('RGB', (4000, 6000), 'red').save(data, 'JPEG')
    monkeypatch.setattr(runtime, 'extract_cover_only', lambda path: data.getvalue())
    monkeypatch.setattr(runtime, '_cover_cache_path', lambda path: str(tmp_path / 'cover.webp'))
    decoded = []
    convert = Image.Image.convert
    def track_convert(self, *args, **kwargs):
        decoded.append(self.size)
        return convert(self, *args, **kwargs)
    monkeypatch.setattr(Image.Image, 'convert', track_convert)
    loader = CoverLoader(ImmediateRoot(), {})
    try:
        image = loader._load('synthetic.cbz')
        assert image.size == (runtime.CAPA_W, runtime.CAPA_H)
        assert decoded
        assert all(w <= runtime.CAPA_W and h <= runtime.CAPA_H for w, h in decoded)
    finally:
        loader.stop()
        loader._thread.join(2)


def test_lru_promotes_hits_and_evicts_oldest(monkeypatch):
    root = ImmediateRoot()
    monkeypatch.setattr(CoverLoader, 'MAX_CACHED', 2)
    loader = CoverLoader(root, {})
    loader._load = lambda p: Image.new('RGB', (4, 4))
    received = []
    try:
        for key in ('one', 'two', 'one', 'three'):
            count = len(received)
            loader.request(key, lambda *args: received.append(args[0]))
            root.pump(lambda: len(received) > count)
        assert list(loader._cache) == ['one', 'three']
    finally:
        loader.stop()
        loader._thread.join(2)


def test_custom_cover_decode_runs_off_ui_and_is_reduced(tmp_path, monkeypatch):
    root = ImmediateRoot()
    cover = tmp_path / 'custom.jpg'
    Image.new('RGB', (4000, 6000), 'red').save(cover)
    from komicove_app import runtime
    opened = []
    original = runtime.Image.open

    def open_image(*args, **kwargs):
        opened.append(threading.get_ident())
        return original(*args, **kwargs)

    monkeypatch.setattr(runtime.Image, 'open', open_image)
    loader = CoverLoader(root, {})
    received = []
    try:
        loader.request(('comic.cbz', str(cover)), lambda path, pil: received.append(pil.size))
        root.pump(lambda: bool(received))
        assert all(thread != root.thread for thread in opened)
        assert received[0][0] <= runtime.CAPA_W and received[0][1] <= runtime.CAPA_H
    finally:
        loader.stop()
        loader._thread.join(2)
