from __future__ import annotations
import hashlib
import os
import threading
from .storage import APPDATA_DIR, json_load, json_save

INDEX_FILE = os.path.join(APPDATA_DIR, "content_index.json")
_lock = threading.RLock()

def content_id(path: str) -> str:
    absolute = os.path.abspath(path)
    stat = os.stat(absolute)
    key = os.path.normcase(absolute)
    with _lock:
        index = json_load(INDEX_FILE, {})
        cached = index.get(key)
        if cached and cached.get("size") == stat.st_size and cached.get("mtime_ns") == stat.st_mtime_ns:
            return cached["sha256"]
    digest = hashlib.sha256()
    with open(absolute, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    with _lock:
        index = json_load(INDEX_FILE, {})
        index[key] = {"sha256": value, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
        json_save(INDEX_FILE, index)
    return value

def build_sync_payload(progress: dict, favorites: set[str]):
    payload, paths_by_id = [], {}
    for path in set(progress) | favorites:
        if not os.path.isfile(path): continue
        try: item_id = content_id(path)
        except OSError: continue
        paths_by_id[item_id] = path
        entry = progress.get(path)
        page = entry.get("page") if isinstance(entry, dict) else entry
        stamp = entry.get("ts", 0) if isinstance(entry, dict) else 0
        payload.append({"item_key": item_id, "page": page, "favorite": path in favorites,
                        "client_updated_at": stamp})
    return payload, paths_by_id
