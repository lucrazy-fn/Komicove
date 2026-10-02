from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone

def _migrate_legacy_data(legacy, destination):
    """Copy old local data once without replacing anything already in Komicove."""
    for source_dir, dirs, files in os.walk(legacy):
        dirs[:] = [name for name in dirs if not os.path.islink(os.path.join(source_dir, name))]
        target_dir = os.path.join(destination, os.path.relpath(source_dir, legacy))
        os.makedirs(target_dir, exist_ok=True)
        for name in files:
            source = os.path.join(source_dir, name)
            target = os.path.join(target_dir, name)
            if os.path.islink(source) or os.path.lexists(target):
                continue
            fd, temporary = tempfile.mkstemp(prefix=".komicove-migration-", dir=target_dir)
            os.close(fd)
            try:
                shutil.copy2(source, temporary)
                if not os.path.lexists(target):
                    os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.remove(temporary)


def _appdata_directory():
    explicit = os.environ.get("KOMICOVE_APPDATA_DIR") or os.environ.get("PANEL_APPDATA_DIR")
    if explicit:
        return explicit
    root = os.environ.get("APPDATA", os.path.expanduser("~"))
    current = os.path.join(root, "Komicove")
    legacy = os.path.join(root, "Panel")
    if os.path.isdir(legacy):
        try:
            _migrate_legacy_data(legacy, current)
        except OSError:
            # An incomplete copy must never make the existing library vanish.
            return legacy
    return current


APPDATA_DIR = _appdata_directory()
os.makedirs(APPDATA_DIR, exist_ok=True)
LIBRARY_CONFIG_FILE = os.path.join(APPDATA_DIR, "library_config.json")
PROGRESS_FILE = os.path.join(APPDATA_DIR, "reading_progress.json")
BOOKMARKS_FILE = os.path.join(APPDATA_DIR, "bookmarks.json")
FAVORITES_FILE = os.path.join(APPDATA_DIR, "favorites.json")
MANUAL_STATUS_FILE = os.path.join(APPDATA_DIR, "manual_status.json")
PREFS_FILE = os.path.join(APPDATA_DIR, "prefs.json")
STATS_FILE = os.path.join(APPDATA_DIR, "reading_stats.json")
COVER_CACHE_DIR = os.path.join(APPDATA_DIR, "cover_cache")
try:
    os.makedirs(COVER_CACHE_DIR, exist_ok=True)
except FileExistsError:



    COVER_CACHE_DIR = os.path.join(APPDATA_DIR, "cover_cache_files")
    os.makedirs(COVER_CACHE_DIR, exist_ok=True)

def json_load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as source: return json.load(source)
    except (OSError, json.JSONDecodeError): return default

def json_save(path, data):
    try:
        with open(path, "w", encoding="utf-8") as target: json.dump(data, target, indent=2)
    except OSError: return False
    return True

_progress_cache: dict = {}
_progress_dirty = False
_progress_timer = None
_change_listeners = []
def register_change_listener(callback):
    if callback not in _change_listeners: _change_listeners.append(callback)
def _changed(kind,path):
    for callback in list(_change_listeners):
        try: callback(kind,path)
        except Exception: pass

def load_progress():
    if not _progress_cache: _progress_cache.update(json_load(PROGRESS_FILE, {}))
    return _progress_cache

def flush_progress():
    global _progress_dirty, _progress_timer
    _progress_timer = None
    if _progress_dirty: json_save(PROGRESS_FILE, _progress_cache); _progress_dirty = False

def save_progress(path, page):
    global _progress_dirty, _progress_timer
    load_progress(); _progress_cache[path] = {"page": page, "ts": time.time()} if isinstance(page, int) else page
    _progress_dirty = True
    if _progress_timer is not None:
        try:
            import tkinter as tk
            tk._default_root.after_cancel(_progress_timer)
        except Exception: pass
    try:
        import tkinter as tk
        _progress_timer = tk._default_root.after(2000, flush_progress) if tk._default_root else None
        if _progress_timer is None: flush_progress()
    except Exception: flush_progress()
    _changed("progress",path)

def get_progress_page(path):
    value = load_progress().get(path)
    return value.get("page") if isinstance(value, dict) else value

def load_bookmarks(): return json_load(BOOKMARKS_FILE, {})
def toggle_bookmark(path, page):
    data=load_bookmarks(); pages=data.get(path, [])
    pages.remove(page) if page in pages else pages.append(page); pages.sort(); data[path]=pages
    json_save(BOOKMARKS_FILE, data); _changed("bookmark",path); return page in pages
def get_bookmarks(path): return load_bookmarks().get(path, [])
def load_favorites(): return json_load(FAVORITES_FILE, [])
def toggle_favorite(path):
    data=load_favorites(); enabled=path not in data
    data.append(path) if enabled else data.remove(path); json_save(FAVORITES_FILE, data); _changed("favorite",path); return enabled
def is_favorite(path): return path in load_favorites()

def preserve_renamed_book(old_path, new_path):
    """Copy path-keyed data without erasing the original or newer destination."""
    progress = load_progress()
    if old_path in progress and new_path not in progress:
        save_progress(new_path, progress[old_path])
    for filename in (BOOKMARKS_FILE, MANUAL_STATUS_FILE, os.path.join(APPDATA_DIR, "book_metadata.json")):
        data = json_load(filename, {})
        if old_path in data and new_path not in data:
            data[new_path] = data[old_path]
            json_save(filename, data)
    favorites = load_favorites()
    if old_path in favorites and new_path not in favorites:
        favorites.append(new_path)
        json_save(FAVORITES_FILE, favorites)
    data = _stats_data()
    changed = False
    for entry in data["books"].values():
        if entry.get("path") == old_path:
            entry["path"] = new_path
            changed = True
    if changed:
        json_save(STATS_FILE, data)
def load_manual_status(): return json_load(MANUAL_STATUS_FILE, {})
def set_manual_status(path, status):
    data=load_manual_status(); data.pop(path, None) if status is None else data.__setitem__(path, status); json_save(MANUAL_STATUS_FILE, data); _changed("status",path)
def get_manual_status(path): return load_manual_status().get(path)
def load_prefs(): return json_load(PREFS_FILE, {})
def save_prefs(**values):
    data=load_prefs(); data.update(values); json_save(PREFS_FILE, data)
def _stats_data():
    data = json_load(STATS_FILE, {"books": {}, "daily": {}})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("version", 2)
    data.setdefault("books", {})
    data.setdefault("daily", {})
    return data


def _stats_book(data, content_key, *, path=None, metadata=None):
    books = data.setdefault("books", {})
    item = books.setdefault(content_key, {
        "pages": [], "seconds": 0, "completed": False, "sessions": 0,
    })
    item.setdefault("pages", [])
    item.setdefault("seconds", 0)
    item.setdefault("completed", False)
    item.setdefault("sessions", 0)
    if path:
        item["path"] = os.path.abspath(path)
        item.setdefault("title", os.path.splitext(os.path.basename(path))[0])
    for key in ("title", "series", "genre", "writer"):
        value = (metadata or {}).get(key)
        if value:
            item[key] = str(value).strip()
    return item


def _day_key(timestamp=None):
    moment = datetime.fromtimestamp(timestamp or time.time(), tz=timezone.utc).astimezone()
    return moment.strftime("%Y-%m-%d")


def record_page_read(content_key, page, total=0, *, path=None, metadata=None, timestamp=None):
    """Record a real page view while keeping legacy totals compatible.

    A page is counted once per book for the all-time total and once per day for
    charts. Repaints of the same page therefore do not inflate the numbers.
    """
    data = _stats_data()
    item = _stats_book(data, content_key, path=path, metadata=metadata)
    page = int(page)
    now = float(timestamp or time.time())
    if page not in item["pages"]:
        item["pages"].append(page)
        item["pages"].sort()
    item.setdefault("first_read_at", now)
    item["last_read_at"] = now
    if total:
        item["total_pages"] = max(0, int(total))
        if page >= int(total) - 1:
            item["completed"] = True
            item.setdefault("completed_at", now)

    daily = data.setdefault("daily", {})
    day = daily.setdefault(_day_key(now), {"page_keys": [], "seconds": 0, "sessions": 0})
    page_key = f"{content_key}:{page}"
    page_keys = day.setdefault("page_keys", [])
    if page_key not in page_keys:
        page_keys.append(page_key)
    day["pages"] = len(page_keys)
    json_save(STATS_FILE, data)


def record_reading_time(content_key, seconds, *, path=None, metadata=None, timestamp=None):
    """Finish a reading session and add its real duration to daily history."""
    seconds = max(0, min(int(seconds), 6 * 60 * 60))
    if seconds <= 0:
        return
    data = _stats_data()
    item = _stats_book(data, content_key, path=path, metadata=metadata)
    now = float(timestamp or time.time())
    item["seconds"] = int(item.get("seconds", 0)) + seconds
    item["sessions"] = int(item.get("sessions", 0)) + 1
    item.setdefault("first_read_at", now)
    item["last_read_at"] = now
    day = data.setdefault("daily", {}).setdefault(
        _day_key(now), {"page_keys": [], "seconds": 0, "sessions": 0}
    )
    day["seconds"] = int(day.get("seconds", 0)) + seconds
    day["sessions"] = int(day.get("sessions", 0)) + 1
    day["pages"] = len(day.get("page_keys", []))
    json_save(STATS_FILE, data)


def personal_statistics():
    data = _stats_data()
    books = data.get("books", {})
    daily = data.get("daily", {})
    genres = {}
    for item in books.values():
        page_count = len(set(item.get("pages", [])))
        raw = str(item.get("genre") or "").replace(";", ",")
        names = [name.strip() for name in raw.split(",") if name.strip()]
        for name in names:
            genres[name] = genres.get(name, 0) + page_count
    normalized_daily = {}
    for day, entry in daily.items():
        if not isinstance(entry, dict):
            continue
        normalized_daily[day] = {
            "pages": max(0, int(entry.get("pages", len(entry.get("page_keys", []))) or 0)),
            "seconds": max(0, int(entry.get("seconds", 0) or 0)),
            "sessions": max(0, int(entry.get("sessions", 0) or 0)),
        }
    return {
        "completed": sum(bool(x.get("completed")) for x in books.values()),
        "pages": sum(len(set(x.get("pages", []))) for x in books.values()),
        "seconds": sum(int(x.get("seconds", 0)) for x in books.values()),
        "started": len(books),
        "sessions": sum(int(x.get("sessions", 0)) for x in books.values()),
        "daily": normalized_daily,
        "genres": genres,
    }
def export_backup(path):
    json_save(path, {"progress":json_load(PROGRESS_FILE,{}),"bookmarks":json_load(BOOKMARKS_FILE,{}),
        "favorites":json_load(FAVORITES_FILE,[]),"manual_status":json_load(MANUAL_STATUS_FILE,{}),
        "prefs":json_load(PREFS_FILE,{}),"statistics":json_load(STATS_FILE,{}),"exported_at":time.time()})
def import_backup(path):
    data=json_load(path,{})
    for key,file,default in [("progress",PROGRESS_FILE,{}),("bookmarks",BOOKMARKS_FILE,{}),
        ("manual_status",MANUAL_STATUS_FILE,{}),("prefs",PREFS_FILE,{}),("statistics",STATS_FILE,{})]:
        if key in data:
            current=json_load(file,default); current.update(data[key]); json_save(file,current)
    if "favorites" in data: json_save(FAVORITES_FILE,data["favorites"])
    _progress_cache.clear()
def collection_progress(files):
    data=load_progress(); read=0; latest=None; latest_ts=-1
    for path in files:
        entry=data.get(path)
        if entry is not None:
            stamp=entry.get("ts",0) if isinstance(entry,dict) else 0
            if stamp>latest_ts: latest_ts=stamp; latest=path
            read+=1
    return read,len(files),latest
def collection_read_count(files): return collection_progress(files)
