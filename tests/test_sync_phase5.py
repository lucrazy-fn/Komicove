import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select, inspect, text
from sqlalchemy.orm import Session

from komicove_app import storage, sync
from komicove_backend.db import Base
from komicove_backend.accounts.models import User, LibraryState, LibraryStateAlias
from komicove_backend.api.routes.account import sync_state
from komicove_backend.api.schemas import LibrarySyncRequest


@pytest.fixture
def local(tmp_path, monkeypatch):
    for name in ("PROGRESS_FILE", "FAVORITES_FILE", "SYNC_STATE_FILE", "BOOKMARKS_FILE", "MANUAL_STATUS_FILE", "STATS_FILE", "PREFS_FILE"):
        monkeypatch.setattr(storage, name, str(tmp_path / (name + ".json")))
    monkeypatch.setattr(sync, "INDEX_FILE", str(tmp_path / "content_index.json"))
    monkeypatch.setattr(sync, "_index", None)
    monkeypatch.setattr(sync, "_dirty", False)
    storage._progress_cache.clear()
    yield tmp_path
    storage._progress_cache.clear()


@pytest.fixture
def server(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "server.db"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(username="existing", password_hash="fixture", password_salt="fixture")
        db.add(user)
        db.commit()
        def exchange(items):
            rows = sync_state(LibrarySyncRequest(items=items), user, db)
            db.commit()
            return [row.model_dump() for row in rows]
        yield db, user, exchange
    engine.dispose()


def test_same_bytes_pc_and_android_contract_and_batched_cache(local, monkeypatch):
    contract = json.loads((Path(__file__).parents[1] / "android/app/src/test/resources/portable_identity_v1.json").read_text())
    first = local / "PC.cbz"
    second = local / "Android-copy.cbz"
    for path in (first, second): path.write_bytes(contract["utf8"].encode())
    saves = []
    real_save = storage.json_save
    monkeypatch.setattr(storage, "json_save", lambda path, data: (saves.append(path), real_save(path, data))[1])
    payload, mapping = sync.build_sync_payload({str(first): 8}, {str(second)})
    assert payload == [{"item_key": contract["sha256"], "page": 8, "favorite": True, "client_updated_at": 0}]
    assert len(mapping[contract["sha256"]]) == 2
    assert saves.count(sync.INDEX_FILE) == 1
    monkeypatch.setattr(hashlib, "sha256", lambda: pytest.fail("unchanged file was rehashed"))
    sync.build_sync_payload({}, set(), paths=[str(first), str(second)])
    assert saves.count(sync.INDEX_FILE) == 1


def test_folder_validated_hash_is_reused_and_changed_file_rehashed(local, monkeypatch):
    path = local / "book.cbz"; path.write_bytes(b"original")
    digest = hashlib.sha256(b"original").hexdigest(); stat = path.stat()
    known = {digest: {"sources": {"source": {"path": str(path), "signature": [stat.st_size, stat.st_mtime_ns]}}}}
    real_hash = hashlib.sha256
    monkeypatch.setattr(hashlib, "sha256", lambda: pytest.fail("validated folder digest was rehashed"))
    assert sync.build_sync_payload({}, set(), [str(path)], known=known)[0][0]["item_key"] == digest
    monkeypatch.setattr(hashlib, "sha256", real_hash)
    path.write_bytes(b"different size")
    assert sync.content_id(str(path)) != digest


def test_cached_reader_identity_does_not_wait_for_heavy_batch(local):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    path = local / "warm.cbz"; path.write_bytes(b"warm reader")
    expected = sync.content_id(str(path))
    held, release = threading.Event(), threading.Event()
    def background_batch():
        with sync.identity_batch():
            held.set()
            assert release.wait(3)
    with ThreadPoolExecutor(max_workers=2) as worker:
        batch = worker.submit(background_batch)
        assert held.wait(2)
        try:
            assert worker.submit(sync.content_id, str(path)).result(timeout=1) == expected
        finally:
            release.set()
        batch.result()


def test_pc_to_android_to_pc_and_conflict_preserves_inflight_edits(local, server):
    db, user, exchange = server
    path = str(local / "comic.cbz"); Path(path).write_bytes(b"same comic")
    storage.save_progress(path, {"page": 7, "ts": 100, "extra": "preserve"})
    storage.json_save(storage.FAVORITES_FILE, [path])
    payload, mapping = sync.build_sync_payload(*storage.sync_snapshot()[:2])
    key = payload[0]["item_key"]
    assert exchange(payload)[0]["page"] == 7  # PC -> Android portable key.
    remote = exchange([{"item_key": key, "page": 2, "favorite": False, "client_updated_at": 200}])
    sync.apply_sync_response(remote, mapping)  # Android -> PC, intentional backwards reading.
    assert storage.get_progress_page(path) == 2 and not storage.is_favorite(path)
    assert storage.load_progress()[path]["extra"] == "preserve"
    assert exchange([{"item_key": key, "page": 19, "favorite": True, "client_updated_at": 199}])[0]["page"] == 2
    assert exchange([{"item_key": key, "page": 19, "favorite": True, "client_updated_at": 200}])[0]["page"] == 2
    storage.save_progress(path, 11)
    sync.apply_sync_response(remote, mapping)
    assert storage.get_progress_page(path) == 11


def test_existing_uri_account_migration_and_old_client_continues(server):
    db, user, exchange = server
    key, old = "a" * 64, "uri-" + "b" * 64
    exchange([{"item_key": old, "page": 9, "favorite": True, "client_updated_at": 40}])
    migrated = exchange([{"item_key": key, "page": None, "client_updated_at": 0, "legacy_keys": [old]}])
    assert all(row["page"] == 9 and row["favorite"] for row in migrated)
    assert len(db.scalars(select(LibraryState)).all()) == 1
    assert len(db.scalars(select(LibraryStateAlias)).all()) == 1
    updated = exchange([{"item_key": old, "page": 3, "favorite": False, "client_updated_at": 41}])
    assert {row["item_key"] for row in updated} == {key, old}
    assert all(row["page"] == 3 and not row["favorite"] for row in updated)
    other = User(username="another", password_hash="fixture", password_salt="fixture")
    db.add(other); db.commit()
    assert sync_state(LibrarySyncRequest(), other, db) == []


def test_legacy_zero_timestamp_bootstrap_preserves_progress_and_favorites(server):
    db, user, exchange = server
    key = "c" * 64
    exchange([{"item_key": key, "page": 6, "favorite": True, "client_updated_at": 0}])
    rows = exchange([{"item_key": key, "page": None, "favorite": False, "client_updated_at": 0}])
    assert rows[0]["page"] == 6 and rows[0]["favorite"]


def test_alias_collision_merges_latest_account_state_and_is_idempotent(server):
    db, user, exchange = server
    key, old = "d" * 64, "uri-" + "e" * 64
    exchange([{"item_key": key, "page": 4, "favorite": False, "client_updated_at": 10},
              {"item_key": old, "page": 2, "favorite": True, "client_updated_at": 20}])
    migration = [{"item_key": key, "page": None, "client_updated_at": 0, "legacy_keys": [old]}]
    for _ in range(2):
        rows = exchange(migration)
        assert all(row["page"] == 2 and row["favorite"] and row["client_updated_at"] == 20 for row in rows)
    assert len(db.scalars(select(LibraryState)).all()) == 1


def test_alias_cannot_be_rebound_to_other_content(server):
    from fastapi import HTTPException
    db, user, exchange = server
    old = "uri-" + "f" * 64
    exchange([{"item_key": "a" * 64, "page": 8, "favorite": True, "client_updated_at": 20, "legacy_keys": [old]}])
    with pytest.raises(HTTPException) as rejected:
        sync_state(LibrarySyncRequest(items=[{"item_key": "b" * 64, "legacy_keys": [old]}]), user, db)
    assert rejected.value.status_code == 409
    db.rollback()
    rows = exchange([])
    assert all(row["page"] == 8 and row["favorite"] for row in rows)


def test_offline_favorite_removal_is_persisted_and_retryable(local, server):
    _, _, exchange = server
    path = str(local / "comic.cbz"); Path(path).write_bytes(b"offline comic")
    storage.json_save(storage.FAVORITES_FILE, [path])
    storage.json_save(storage.PROGRESS_FILE, {path: 5})
    assert storage.toggle_favorite(path) is False
    progress, favorites, state = storage.sync_snapshot()
    rows, mapping = sync.build_sync_payload(progress, favorites, state=state)
    assert rows[0]["page"] == 5 and rows[0]["client_updated_at"] > 0 and not rows[0]["favorite"]
    storage._progress_cache.clear()
    assert storage.get_progress_page(path) == 5 and not storage.is_favorite(path)
    sync.apply_sync_response(exchange(rows), mapping)
    assert storage.get_progress_page(path) == 5 and not storage.is_favorite(path)


def test_atomic_journal_recovers_if_secondary_files_fail(local, monkeypatch):
    path = str(local / "book.cbz"); Path(path).write_bytes(b"journal")
    storage.save_progress(path, {"page": 4, "ts": 10})
    real_save = storage.json_save
    monkeypatch.setattr(storage, "json_save", lambda filename, data: real_save(filename, data) if filename == storage.SYNC_STATE_FILE else False)
    sync.apply_sync_response([{"item_key": "key", "page": 8, "favorite": True, "client_updated_at": 20}], {"key": [path]})
    storage._progress_cache.clear()
    assert storage.get_progress_page(path) == 8 and storage.is_favorite(path)


def test_desktop_debounce_coalesces_edits():
    from komicove_app.library_views import LibraryWindow
    jobs, cancelled = [], []
    window = SimpleNamespace(current_user=object(), _closing_app=False, _sync_job=None,
        after=lambda delay, callback: (jobs.append((delay, callback)), len(jobs))[1],
        after_cancel=cancelled.append)
    LibraryWindow._schedule_sync(window, "progress", "book")
    LibraryWindow._schedule_sync(window, "favorite", "book")
    assert cancelled == [1] and [job[0] for job in jobs] == [1500, 1500]
    LibraryWindow._schedule_sync(window, "bookmark", "book")
    assert len(jobs) == 2


@pytest.mark.parametrize("stamp", [float("nan"), float("inf"), -1])
def test_invalid_conflict_timestamps_rejected(stamp):
    with pytest.raises(ValueError):
        LibrarySyncRequest(items=[{"item_key": "comic", "client_updated_at": stamp}])


def test_incremental_schema_migration_keeps_existing_rows(tmp_path, monkeypatch):
    from komicove_backend import db as database
    engine = create_engine("sqlite:///" + str(tmp_path / "old.db"))
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE library_state_aliases"))
        connection.execute(text("INSERT INTO library_states(id,user_id,item_key,page,favorite,client_updated_at,updated_at) VALUES ('old','account','old-id',7,1,30,CURRENT_TIMESTAMP)"))
    monkeypatch.setattr(database, "_engine", engine)
    database.init_db(); database.init_db()
    assert "library_state_aliases" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.execute(text("SELECT page,favorite FROM library_states WHERE id='old'")).one() == (7, 1)
    engine.dispose()
