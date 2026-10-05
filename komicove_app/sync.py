from __future__ import annotations
import hashlib
import os
import threading
import subprocess
import zipfile
import tempfile
import zlib
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


def _7zip_batch_pages(backend, names):
    """Frame one extraction by listed sizes and verify each page's CRC/order."""
    from .archive import run_7zip
    listing = run_7zip(backend._seven_zip,
        ["l", "-slt", "-ba", "-sccUTF-8", "--", os.path.abspath(backend.path)]).decode("utf-8")
    selected, records = set(names), []
    for block in listing.replace("\r\n", "\n").split("\n\n"):
        fields = dict(line.split(" = ", 1) for line in block.splitlines() if " = " in line)
        if fields.get("Path") not in selected:
            continue
        size, crc = fields.get("Size", ""), fields.get("CRC", "")
        if not size.isdecimal() or len(crc) != 8:
            return None
        try:
            records.append((fields["Path"], int(size), int(crc, 16)))
        except ValueError:
            return None
    if (len(records) != len(names) or len({row[0] for row in records}) != len(names)
            or any(size > 48 * 1024 * 1024 for _, size, _ in records)
            or sum(size for _, size, _ in records) > 1536 * 1024 * 1024
            or any("\n" in name or "\r" in name for name in names)):
        return None
    fd, list_path = tempfile.mkstemp(prefix="komicove-identity-", suffix=".txt")
    process = None
    timeout = None
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            target.write("\n".join(names))
        process = subprocess.Popen([backend._seven_zip, "x", "-so", "-spd", "-scsUTF-8",
            "-i@" + list_path, "--", os.path.abspath(backend.path)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        timeout = threading.Timer(60, process.kill)
        timeout.daemon = True
        timeout.start()
        pages = {}
        for name, size, expected_crc in records:
            digest, crc, remaining = hashlib.sha256(), 0, size
            while remaining:
                chunk = process.stdout.read(min(65536, remaining))
                if not chunk:
                    raise OSError("Incomplete comic page stream")
                digest.update(chunk)
                crc = zlib.crc32(chunk, crc)
                remaining -= len(chunk)
            if crc != expected_crc:
                raise OSError("Comic extraction order or checksum changed")
            pages[name] = digest.digest()
        if process.stdout.read(1) or process.wait() != 0:
            raise OSError("Unexpected comic page stream")
        return [pages[name] for name in names]
    except OSError:
        # Unusual decoders/orders retain the verified per-page extraction path.
        return None
    finally:
        if timeout is not None:
            timeout.cancel()
        if process is not None:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
            process.wait()
        os.remove(list_path)


def _page_key(path, raw_key):
    from .archive import ArchiveBackend, find_7zip, run_7zip, rarfile, natural_key, IMG_EXTS
    backend = None
    try:
        try:
            backend = ArchiveBackend(path)
        except rarfile.RarCannotExec:
            # A RAR renamed .cbz can need an external tool even to read comments.
            # Identity may use 7-Zip without changing the reader's format handling.
            from pathlib import Path
            from types import SimpleNamespace
            executable = find_7zip()
            if not executable:
                raise
            listing = run_7zip(executable,
                ["l", "-slt", "-ba", "-sccUTF-8", "--", os.path.abspath(path)]).decode("utf-8")
            names = sorted([line[7:] for line in listing.splitlines() if line.startswith("Path = ")
                and Path(line[7:]).suffix.lower() in IMG_EXTS and not Path(line[7:]).name.startswith(".")], key=natural_key)
            backend = SimpleNamespace(kind="7zip", names=names, path=path, _seven_zip=executable, close=lambda: None)
        if backend.kind == "pdf":
            return raw_key
        names = [name for name in backend.names if "__MACOSX" not in name]
        if not names or len(names) > 10000:
            return raw_key
        digest = hashlib.sha256(b"komicove:pages:v2\0" + len(names).to_bytes(4, "big"))
        total = 0
        def hash_stream(source):
            nonlocal total
            page, size = hashlib.sha256(), 0
            for chunk in iter(lambda: source.read(65536), b""):
                size += len(chunk)
                total += len(chunk)
                if size > 48 * 1024 * 1024 or total > 1536 * 1024 * 1024:
                    raise ValueError("Comic exceeds page identity limits")
                page.update(chunk)
            digest.update(page.digest())
        if backend.kind == "zip":
            with zipfile.ZipFile(path) as archive:
                for name in names:
                    with archive.open(name) as source:
                        hash_stream(source)
        elif backend.kind == "7zip" or (backend.kind == "rar" and backend._seven_zip):
            pages = _7zip_batch_pages(backend, names)
            if pages is not None:
                for page in pages:
                    digest.update(page)
                return digest.hexdigest()
            for name in names:
                process = subprocess.Popen([backend._seven_zip, "x", "-so", "-spd", "--", os.path.abspath(path), name],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                timeout = threading.Timer(60, process.kill)
                timeout.daemon = True
                timeout.start()
                try:
                    hash_stream(process.stdout)
                    if process.wait() != 0:
                        raise OSError("Could not read comic pages")
                finally:
                    timeout.cancel()
                    process.stdout.close()
                    if process.poll() is None:
                        process.kill()
                    process.wait()
        else:
            from .archive import rarfile
            with rarfile.RarFile(path) as archive:
                for name in names:
                    with archive.open(name) as source:
                        hash_stream(source)
        return digest.hexdigest()
    except Exception:
        # Keep the compatible byte identity when a format/decoder is unavailable.
        return raw_key
    finally:
        if backend is not None:
            backend.close()


def portable_id(path):
    """Sync v2 identifies ordered image bytes; reader/storage IDs remain v1."""
    global _dirty
    with _lock:
        raw_key = content_id(path)
        absolute = os.path.abspath(path)
        key = os.path.normcase(absolute)
        entry = _load_index()[key]
        if (entry.get("identity_version") == 2 and entry.get("item_key")
                and (entry["item_key"] != raw_key or absolute.lower().endswith(".pdf")
                     or entry.get("fallback_revision") == 2)):
            return entry["item_key"], raw_key
        value = _page_key(absolute, raw_key)
        after = os.stat(absolute)
        if (entry["size"], entry["mtime_ns"]) != (after.st_size, after.st_mtime_ns):
            raise OSError("Comic changed while identifying pages")
        _index[key] = dict(entry, item_key=value, identity_version=2, fallback_revision=2)
        _dirty = True
        if not _batch_depth:
            _flush_index()
        return value, raw_key


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
                    if any((_index.get(key) or {}).get(field) != value for field, value in entry.items()):
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
                item_id, old_id = portable_id(path)
            except OSError:
                continue
            paths_by_id.setdefault(item_id, []).append(path)
            entry = progress.get(path)
            page = entry.get("page") if isinstance(entry, dict) else entry
            row = {"item_key": item_id, "page": page, "favorite": path in favorites,
                   "client_updated_at": storage.sync_stamp(path, progress, state)}
            legacy = [old_id] if old_id != item_id else []
            previous = payload.get(item_id)
            if previous:
                legacy = sorted(set(previous.get("legacy_keys", [])) | set(legacy))
            if legacy:
                row["legacy_keys"] = legacy
            if previous is None or row["client_updated_at"] > previous["client_updated_at"]:
                payload[item_id] = row
            else:
                if legacy:
                    previous["legacy_keys"] = legacy
                if row["client_updated_at"] == previous["client_updated_at"] == 0:
                    previous["favorite"] |= row["favorite"]
                    pages = [x for x in (previous["page"], page) if x is not None]
                    previous["page"] = max(pages) if pages else None
    rows = []
    for row in payload.values():
        legacy = row.get("legacy_keys", [])
        for offset in range(0, max(1, len(legacy)), 16):
            rows.append(dict(row, legacy_keys=legacy[offset:offset + 16]) if legacy else row)
    return rows, paths_by_id


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
                entry = dict(state.get(path, {}))
                entry.update(ts=stamp, favorite=bool(item.get("favorite")))
                value = progress.get(path)
                if item.get("page") is not None:
                    value = dict(value) if isinstance(value, dict) else {}
                    value.update(page=item["page"], ts=stamp)
                    entry.update(page=item["page"], page_ts=stamp)
                if (state.get(path) == entry and progress.get(path) == value
                        and (path in favorites) == entry["favorite"]):
                    continue
                state[path] = entry
                if item.get("page") is not None:
                    progress[path] = value
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
