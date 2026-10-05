from __future__ import annotations
import hashlib
import os
import threading
from contextlib import contextmanager
from . import storage

INDEX_FILE = os.path.join(storage.APPDATA_DIR, "content_index.json")
_lock = threading.RLock()
_index = None
_index_path = None
_dirty = False
_batch_depth = 0


def _load_index():
    global _index, _index_path
    if _index is None or _index_path != INDEX_FILE:
        _index = storage.json_load(INDEX_FILE, {})
        _index_path = INDEX_FILE
    return _index


def _flush_index():
    global _dirty
    if _dirty:
        if not storage.json_save(INDEX_FILE, _index):
            raise OSError("Could not persist content identity index")
        _dirty = False


@contextmanager
def identity_batch():
    global _batch_depth
    with _lock:
        _load_index()
        _batch_depth += 1
        try:
            yield
        finally:
            _batch_depth -= 1
            if not _batch_depth:
                _flush_index()


def content_id(path: str) -> str:
    """Portable v1 item_key: lowercase SHA-256 of the original file bytes."""
    global _dirty
    absolute = os.path.abspath(path)
    key = os.path.normcase(absolute)
    # Warm reader lookups must not wait behind a worker hashing other comics.
    # Index entries are replaced whole, so this snapshot is safe to read.
    stat = os.stat(absolute)
    cached = (_index or {}).get(key) if _index_path == INDEX_FILE else None
    if cached and cached.get("size") == stat.st_size and cached.get("mtime_ns") == stat.st_mtime_ns:
        return cached["sha256"]
    with _lock:
        index = _load_index()
        stat = os.stat(absolute)
        cached = index.get(key)
        if cached and cached.get("size") == stat.st_size and cached.get("mtime_ns") == stat.st_mtime_ns:
            return cached["sha256"]
        digest = hashlib.sha256()
        with open(absolute, "rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        after = os.stat(absolute)
        if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise OSError("Comic changed while hashing")
        value = digest.hexdigest()
        index[key] = {"sha256": value, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
        _dirty = True
        if not _batch_depth:
            _flush_index()
        return value


def seed_content_index(books):
    """Reuse already validated folder digests, only while metadata still matches."""
    global _dirty
    with identity_batch():
        for digest, book in books.items():
            for source in book.get("sources", {}).values():
                path = source.get("path")
                if not path or not source.get("available", True):
                    continue
                try:
                    stat = os.stat(path)
                except OSError:
                    continue
                if source.get("signature") == [stat.st_size, stat.st_mtime_ns]:
                    key = os.path.normcase(os.path.abspath(path))
                    entry = {"sha256": digest, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
                    if _index.get(key) != entry:
                        _index[key] = entry
                        _dirty = True


def build_sync_payload(progress: dict, favorites: set[str], paths=(), state=None, known=None):
    state = state if state is not None else storage.json_load(storage.SYNC_STATE_FILE, {})
    payload, paths_by_id = {}, {}
    with identity_batch():
        if known:
            seed_content_index(known)
        for path in sorted(set(progress) | favorites | set(paths) | set(state)):
            if not os.path.isfile(path):
                continue
            try:
                item_id = content_id(path)
            except OSError:
                continue
            paths_by_id.setdefault(item_id, []).append(path)
            entry = progress.get(path)
            page = entry.get("page") if isinstance(entry, dict) else entry
            row = {"item_key": item_id, "page": page, "favorite": path in favorites,
                   "client_updated_at": storage.sync_stamp(path, progress, state)}
            previous = payload.get(item_id)
            if previous is None or row["client_updated_at"] > previous["client_updated_at"]:
                payload[item_id] = row
            elif row["client_updated_at"] == previous["client_updated_at"] == 0:
                previous["favorite"] |= row["favorite"]
                pages = [x for x in (previous["page"], page) if x is not None]
                previous["page"] = max(pages) if pages else None
    return list(payload.values()), paths_by_id


def apply_sync_response(items, paths_by_id):
    """Apply only against current local state, after the network round trip."""
    with storage.STATE_LOCK:
        progress, favorites, state = storage.sync_snapshot()
        changed = False
        for item in items:
            for path in paths_by_id.get(item["item_key"], []):
                stamp = float(item.get("client_updated_at") or 0)
                if stamp < storage.sync_stamp(path, progress, state):
                    continue
                entry = state.setdefault(path, {})
                entry.update(ts=stamp, favorite=bool(item.get("favorite")))
                if item.get("page") is not None:
                    old = progress.get(path)
                    value = dict(old) if isinstance(old, dict) else {}
                    value.update(page=item["page"], ts=stamp)
                    progress[path] = value
                    entry.update(page=item["page"], page_ts=stamp)
                favorites.add(path) if entry["favorite"] else favorites.discard(path)
                changed = True
        if changed:
            # One atomic journal protects both files if a process stops between writes.
            if not storage.json_save(storage.SYNC_STATE_FILE, state):
                raise OSError("Could not persist synchronized state")
            storage.load_progress().update(progress)
            storage.json_save(storage.PROGRESS_FILE, progress)
            storage.json_save(storage.FAVORITES_FILE, sorted(favorites))
        return changed
