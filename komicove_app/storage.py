from __future__ import annotations

import json
import os
import shutil
import tempfile
import time

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
def load_manual_status(): return json_load(MANUAL_STATUS_FILE, {})
def set_manual_status(path, status):
    data=load_manual_status(); data.pop(path, None) if status is None else data.__setitem__(path, status); json_save(MANUAL_STATUS_FILE, data); _changed("status",path)
def get_manual_status(path): return load_manual_status().get(path)
def load_prefs(): return json_load(PREFS_FILE, {})
def save_prefs(**values):
    data=load_prefs(); data.update(values); json_save(PREFS_FILE, data)
def record_page_read(content_key, page, total=0):
    data=json_load(STATS_FILE,{"books":{}}); books=data.setdefault("books",{})
    item=books.setdefault(content_key,{"pages":[],"seconds":0,"completed":False})
    page=int(page)
    if page not in item["pages"]: item["pages"].append(page); item["pages"].sort()
    if total and page >= int(total)-1: item["completed"]=True
    json_save(STATS_FILE,data)
def record_reading_time(content_key, seconds):
    seconds=max(0,min(int(seconds),6*60*60))
    data=json_load(STATS_FILE,{"books":{}}); books=data.setdefault("books",{})
    item=books.setdefault(content_key,{"pages":[],"seconds":0,"completed":False})
    item["seconds"]=int(item.get("seconds",0))+seconds; json_save(STATS_FILE,data)
def personal_statistics():
    books=json_load(STATS_FILE,{"books":{}}).get("books",{})
    return {"completed":sum(bool(x.get("completed")) for x in books.values()),
            "pages":sum(len(set(x.get("pages",[]))) for x in books.values()),
            "seconds":sum(int(x.get("seconds",0)) for x in books.values()),
            "started":len(books)}
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
