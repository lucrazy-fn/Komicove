"""Persistent, content-addressed folder index. Never modify source archives."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import queue
import tempfile
import threading
import time
from pathlib import Path

from .archive import SUPPORTED_EXTENSIONS, ArchiveBackend


class FolderIndex:
    SETTLE_SECONDS = 3
    MAX_FILES = 100000
    MAX_BYTES = 1536 * 1024 * 1024

    def __init__(self, filename, legacy_folder="", *, clock=time.time, validator=None):
        self.filename = Path(filename)
        self.clock = clock
        self.validator = validator or self._validate
        self.lock = threading.RLock()
        self._save_lock = threading.Lock()
        self._data_revision = 0
        self._saved_revision = 0
        self.pending = {}
        self.invalid = {}
        new_index = False
        try:
            self.data = json.loads(self.filename.read_text(encoding="utf-8"))
            if self.data.get("version") != 1:
                raise ValueError("Unsupported folder index")
        except FileNotFoundError:
            self.data = {"version": 1, "folders": {}, "books": {}}
            new_index = True
        if legacy_folder and new_index:
            self.add(legacy_folder)

    @staticmethod
    def key(path):
        return os.path.normcase(os.path.abspath(path))

    @staticmethod
    def _validate(path):
        import zipfile
        if Path(path).suffix.lower() in {".cbz", ".zip"}:
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                if len(entries) > 20000 or sum(e.file_size for e in entries) > 1536 * 1024 * 1024:
                    raise ValueError("Archive limits exceeded")
                if any(e.file_size > 48 * 1024 * 1024 for e in entries):
                    raise ValueError("Archive entry limit exceeded")
                pages = sum(Path(entry.filename).suffix.lower() in {".jpg", ".jpeg", ".png",
                             ".webp", ".gif", ".bmp"} and not Path(entry.filename).name.startswith(".")
                            and not entry.is_dir() for entry in entries)
                if not 0 < pages <= 10000:
                    raise ValueError("Invalid page count")
            return
        source = ArchiveBackend(path)
        try:
            if not 0 < source.count <= 10000:
                raise ValueError("Invalid page count")
        finally:
            source.close()

    def _save_state(self):
        self._data_revision += 1
        return self._data_revision, copy.deepcopy(self.data)

    def _save(self, state=None):
        if state is None:
            with self.lock:
                state = self._save_state()
        revision, data = state
        with self._save_lock:
            if revision <= self._saved_revision:
                return
            self._write(data)
            self._saved_revision = revision

    def _write(self, data):
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        failure = None
        for attempt in range(3):
            name = None
            try:
                fd, raw_name = tempfile.mkstemp(
                    prefix=f".{self.filename.name}.", suffix=".tmp",
                    dir=self.filename.parent)
                name = Path(raw_name)
                with os.fdopen(fd, "w", encoding="utf-8") as target:
                    json.dump(data, target, ensure_ascii=False)
                    target.flush()
                    os.fsync(target.fileno())
                os.replace(name, self.filename)
                return
            except PermissionError as error:
                failure = error
                if attempt < 2:
                    time.sleep(.025 * (attempt + 1))
            finally:
                try:
                    if name is not None and name.exists():
                        name.unlink()
                except OSError:
                    pass
        raise failure

    def add(self, path):
        key = self.key(path)
        state = None
        with self.lock:
            if key not in self.data["folders"]:
                self.data["folders"][key] = {"path": os.path.abspath(path),
                    "name": Path(path).name or path, "enabled": True,
                    "checked": 0, "status": "checking", "count": 0, "new": 0}
                state = self._save_state()
        if state is not None:
            self._save(state)
        return key

    def configure(self, key, *, enabled=None, name=None, remove=False):
        with self.lock:
            if remove:
                self.data["folders"].pop(key, None)
            else:
                row = self.data["folders"][key]
                if enabled is not None:
                    row["enabled"] = enabled
                if name:
                    row["name"] = name[:80]
            state = self._save_state()
        self._save(state)

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.data)

    def paths(self, *, visible_only=False):
        snapshot = self.snapshot()
        active = {key for key, row in snapshot["folders"].items() if row["enabled"]}
        return [book["path"] for book in snapshot["books"].values()
                if not visible_only or not book.get("sources")
                or any(source["folder"] in active for source in book["sources"].values())]

    def _folder_covers(self, stop):
        from PIL import Image
        import io
        directory = self.filename.parent / "folder_covers"
        snapshot = self.snapshot()
        covers = {}
        first_by_folder = {}
        for digest, book in snapshot["books"].items():
            if not book.get("available"):
                continue
            for source in book["sources"].values():
                if source.get("available", True):
                    first_by_folder.setdefault(source["folder"], (digest, book))
        for key, folder in snapshot["folders"].items():
            if stop and stop.is_set():
                return covers
            candidate = first_by_folder.get(key)
            if candidate is None:
                continue
            digest, book = candidate
            destination = directory / (digest + ".png")
            if not destination.is_file():
                source = None
                try:
                    directory.mkdir(exist_ok=True)
                    source = ArchiveBackend(book["path"])
                    data = source.read_page(0)
                    if len(data) > 48 * 1024 * 1024:
                        continue
                    with Image.open(io.BytesIO(data)) as image:
                        image.thumbnail((68, 82))
                        image.convert("RGB").save(destination)
                except Exception:
                    continue
                finally:
                    if source:
                        source.close()
            if folder.get("cover") != str(destination):
                covers[key] = str(destination)
        return covers

    def rescan(self, keys=None, stop=None, progress=None, publish=None):
        """All folders are reconciled together so cross-folder moves keep identity."""
        before = self.snapshot()
        results, files = {}, {}
        now = self.clock()
        for key, folder in before["folders"].items():
            if not folder["enabled"] or keys is not None and key not in keys:
                continue
            try:
                root = Path(folder["path"])
                if not root.is_dir():
                    raise OSError("Unavailable folder")
                rows = {}
                # Do not follow links, junctions or cycles outside the selected tree.
                def walk_error(error):
                    raise error
                for directory, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
                    if stop and stop.is_set():
                        return None
                    if len(Path(directory).relative_to(root).parts) > 32:
                        raise OSError("Folder depth limit")
                    dirs[:] = [d for d in dirs if not Path(directory, d).is_symlink()
                               and not os.path.islink(Path(directory, d))
                               and not (hasattr(os.path, "isjunction") and os.path.isjunction(Path(directory, d)))]
                    for name in names:
                        path = Path(directory, name)
                        if path.suffix.lower() not in SUPPORTED_EXTENSIONS or path.is_symlink():
                            continue
                        stat = path.stat()
                        if len(rows) >= self.MAX_FILES:
                            raise OSError("Folder entry limit")
                        rows[(key, self.key(path))] = (str(path), stat.st_size, stat.st_mtime_ns, key)
                results[key] = "updated"
                files.update(rows)
            except OSError:
                results[key] = "unavailable"

        indexed_paths = {}
        for digest, book in before["books"].items():
            for path, metadata in book.get("sources", {}).items():
                indexed_paths[self.key(metadata.get("path", path))] = (digest, metadata)
        discovered, waiting, duplicates, invalid = {}, set(), 0, 0
        computed = {}
        total = len(files)
        processed = 0
        last_notice = 0.0
        last_publish = time.monotonic()
        unpublished = {}
        if progress:
            progress(0, total)

        def publish_books():
            if not unpublished:
                return
            with self.lock:
                for digest, sources in unpublished.items():
                    for source in sources.values():
                        old = indexed_paths.get(self.key(source["path"]))
                        if old and old[0] != digest and old[0] in self.data["books"]:
                            previous = self.data["books"][old[0]]
                            previous["sources"] = {key: item for key, item in previous["sources"].items()
                                if self.key(item["path"]) != self.key(source["path"])}
                            if not previous["sources"]:
                                self.data["books"].pop(old[0])
                    book = self.data["books"].setdefault(digest, {
                        "path": next(iter(sources.values()))["path"], "sources": {}})
                    book["sources"].update(sources)
                    book["available"] = True
                state = self._save_state()
            self._save(state)
            unpublished.clear()
            publish()
        for location, (path, size, modified, folder) in files.items():
            key = location[1]
            if stop and stop.is_set():
                return None
            processed += 1
            if progress and time.monotonic() - last_notice >= .1:
                progress(processed - 1, total)
                last_notice = time.monotonic()
            signature = [size, modified]
            known = indexed_paths.get(key)
            if key in computed:
                digest = computed[key]
            elif known and known[1].get("signature") == signature:
                digest = known[0]
            else:
                observed = self.pending.get(key)
                if not observed or observed[0] != signature:
                    self.pending[key] = (signature, now)
                    waiting.add(folder)
                    continue
                if now - observed[1] < self.SETTLE_SECONDS:
                    waiting.add(folder)
                    continue
                if size <= 0 or size > self.MAX_BYTES or self.invalid.get(key) == signature:
                    invalid += 1
                    continue
                try:
                    self.validator(path)
                    hasher = hashlib.sha256()
                    with open(path, "rb") as source:
                        while chunk := source.read(1024 * 1024):
                            if stop and stop.is_set():
                                return None
                            hasher.update(chunk)
                    stat = os.stat(path)
                    if [stat.st_size, stat.st_mtime_ns] != signature:
                        self.pending.pop(key, None)
                        waiting.add(folder)
                        continue
                    digest = hasher.hexdigest()
                except Exception as error:
                    # A partially copied/corrupt archive remains pending, not imported.
                    if not isinstance(error, OSError):
                        self.invalid[key] = signature
                    invalid += 1
                    continue
            sources = discovered.setdefault(digest, {})
            if digest in before["books"] or sources:
                duplicates += 1
            computed[key] = digest
            source_key = folder + "\0" + key
            source = {"path": path, "folder": folder, "signature": signature, "available": True}
            sources[source_key] = source
            if publish and (digest not in before["books"] or not known or known[0] != digest):
                unpublished.setdefault(digest, {})[source_key] = source
            self.pending.pop(key, None)
            if publish and time.monotonic() - last_publish >= .5:
                publish_books()
                last_publish = time.monotonic()

        if publish:
            publish_books()
        if progress:
            progress(total, total)
        added, moves = len(discovered.keys() - before["books"].keys()), []
        with self.lock:
            # A modified path has one current owner. Retire only its old source;
            # other copies of the original content remain available.
            current_owners = {self.key(source["path"]): digest
                              for digest, sources in discovered.items()
                              for source in sources.values()}
            for digest, book in list(self.data["books"].items()):
                for source_key, source in list(book.get("sources", {}).items()):
                    if current_owners.get(self.key(source["path"])) not in (None, digest):
                        book["sources"].pop(source_key)
                if not book.get("sources") and digest in before["books"]:
                    self.data["books"].pop(digest)
            for digest, book in self.data["books"].items():
                sources = book.setdefault("sources", {})
                for path in list(sources):
                    owner = sources[path]["folder"]
                    if owner in results:
                        sources[path]["available"] = False
            for digest, sources in discovered.items():
                if digest not in self.data["books"]:
                    self.data["books"][digest] = {"path": next(iter(sources.values()))["path"],
                                                  "sources": {}}
                retained = self.data["books"][digest]["sources"]
                # Old path-keyed records remain readable; normalize only confirmed locations.
                confirmed = {(source["folder"], self.key(source["path"])) for source in sources.values()}
                for key, source in list(retained.items()):
                    if (source["folder"], self.key(source["path"])) in confirmed:
                        retained.pop(key)
                retained.update(sources)
            for book in self.data["books"].values():
                old = book["path"]
                available_sources = [s for s in book["sources"].values()
                                     if s["folder"] in self.data["folders"] and s.get("available", True) and
                                     (s["folder"] not in results or results[s["folder"]] != "unavailable")]
                available = [s["path"] for s in available_sources]
                book["available"] = bool(available)
                active = [s["path"] for s in available_sources if self.data["folders"][s["folder"]]["enabled"]]
                preferred = active or available
                if preferred and old not in preferred:
                    book["path"] = preferred[0]
                    moves.append((old, book["path"]))
            for key, state in results.items():
                row = self.data["folders"].get(key)
                if row is None:
                    continue
                row.update(checked=now, status="checking" if key in waiting else state,
                           count=sum(any(s["folder"] == key for s in b["sources"].values())
                                     for b in self.data["books"].values()),
                           new=sum(d not in before["books"] and any(s["folder"] == key for s in src.values())
                                   for d, src in discovered.items()))
            state = self._save_state()
        self._save(state)
        covers = self._folder_covers(stop)
        if covers:
            with self.lock:
                for key, path in covers.items():
                    if key in self.data["folders"]:
                        self.data["folders"][key]["cover"] = path
                state = self._save_state()
            self._save(state)
        current_paths = {key[1] for key in files}
        self.pending = {k: v for k, v in self.pending.items() if k in current_paths}
        self.invalid = {k: v for k, v in self.invalid.items() if k in current_paths}
        return {"added": added, "duplicates": duplicates, "moves": moves,
                "changed": before["books"] != self.snapshot()["books"], "waiting": bool(waiting), "invalid": invalid}


class FolderWatcher:
    """Portable polling watcher; all disk work stays off the Tk event thread."""
    def __init__(self, index, interval=10):
        self.index = index
        self.interval = interval
        self.events = queue.SimpleQueue()
        self.updates = queue.SimpleQueue()
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name="folder-watcher")
        self.thread.start()

    def _run(self):
        while not self.stop.is_set():
            delay = self.interval
            try:
                result = self.index.rescan(stop=self.stop,
                    progress=lambda done, total: self.updates.put({"progress": (done, total)}),
                    publish=lambda: self.updates.put({"partial": True}))
                if result:
                    self.events.put(result)
                    if result["waiting"]:
                        delay = min(self.interval, self.index.SETTLE_SECONDS + .1)
            except Exception:
                import logging
                logging.getLogger("komicove").exception("Folder index scan failed")
            self.wake.wait(delay)
            self.wake.clear()

    def refresh(self):
        self.wake.set()

    def close(self):
        self.stop.set()
        self.wake.set()
