import logging

import pytest
import requests
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError, OperationalError, TimeoutError as PoolTimeoutError

from komicove_backend import db
from komicove_backend.accounts import models as accounts_models  # noqa: F401
from komicove_backend.api.failures import RequestDiagnostics
from komicove_backend.catalog import models as catalog_models  # noqa: F401
from komicove_backend.catalog.assets import RemoteStorageError
from komicove_backend.catalog.b2_storage import StorageConfigurationError
from komicove_backend.moderation import db_models as moderation_models  # noqa: F401


def test_postgres_pool_settings_and_sqlite_fallback(monkeypatch):
    captured = []
    real_create_engine = create_engine

    def capture(url, **kwargs):
        captured.append((url, kwargs))
        return object()

    monkeypatch.setattr(db, "create_engine", capture)
    monkeypatch.setenv("KOMICOVE_DB_POOL_PRE_PING", "false")
    monkeypatch.setenv("KOMICOVE_DB_POOL_SIZE", "7")
    monkeypatch.setenv("KOMICOVE_DB_MAX_OVERFLOW", "3")
    monkeypatch.setenv("KOMICOVE_DB_POOL_TIMEOUT", "8")
    monkeypatch.setenv("KOMICOVE_DB_POOL_RECYCLE", "600")
    db._create_engine("postgresql+psycopg://example/db")
    assert captured[-1][1] == {
        "pool_pre_ping": False, "pool_size": 7, "max_overflow": 3,
        "pool_timeout": 8, "pool_recycle": 600,
    }
    db._create_engine("sqlite://")
    assert captured[-1][1] == {"connect_args": {"check_same_thread": False}}
    monkeypatch.setenv("KOMICOVE_DB_POOL_SIZE", "0")
    with pytest.raises(ValueError, match="KOMICOVE_DB_POOL_SIZE"):
        db._create_engine("postgresql+psycopg://example/db")
    monkeypatch.setattr(db, "create_engine", real_create_engine)
    engine = db._create_engine("sqlite://")
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT 1").scalar() == 1
    finally:
        engine.dispose()


def test_phase9_index_migration_is_repeatable(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    db.Base.metadata.create_all(engine)
    for table in db.Base.metadata.tables.values():
        for index in table.indexes:
            if index.name and index.name.startswith("ix_phase9_"):
                index.drop(bind=engine)
    monkeypatch.setattr(db, "_engine", engine)
    db.init_db()
    db.init_db()
    inspector = inspect(engine)
    for table_name, names in {
        "publications": {"ix_phase9_publications_status_published", "ix_phase9_publications_user_created"},
        "notifications": {"ix_phase9_notifications_user_created"},
        "session_tokens": {"ix_phase9_sessions_user_created"},
    }.items():
        assert names <= {index["name"] for index in inspector.get_indexes(table_name)}
    assert ["user_id", "item_key"] in [
        constraint["column_names"] for constraint in inspector.get_unique_constraints("library_states")
    ]
    engine.dispose()


def test_legacy_sqlite_user_migration_preserves_rows(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old-users.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, username VARCHAR(32), "
                                "password_hash VARCHAR(255), password_salt VARCHAR(64), "
                                "is_active BOOLEAN, is_moderator BOOLEAN, created_at DATETIME)"))
        connection.execute(text("INSERT INTO users VALUES ('legacy-id', 'legacy', 'hash', 'salt', "
                                "1, 1, '2020-01-01 00:00:00')"))
    monkeypatch.setattr(db, "_engine", engine)
    db.init_db()
    db.init_db()
    with engine.connect() as connection:
        assert connection.execute(text("SELECT id, username, role FROM users")).one() == (
            "legacy-id", "legacy", "owner"
        )
    engine.dispose()


def test_failure_status_and_safe_request_id(caplog):
    async def fail(scope, receive, send):
        kind = scope["path"].rsplit("/", 1)[-1]
        if kind == "unavailable":
            raise DBAPIError("SELECT secret", {"password": "hidden-password"},
                             Exception("hidden-password"), connection_invalidated=True)
        if kind in {"pg-disconnect", "pg-query-timeout"}:
            class DriverFailure(Exception):
                sqlstate = "08006" if kind == "pg-disconnect" else "57014"

            raise DBAPIError("SELECT secret", {}, DriverFailure("hidden-password"))
        if kind == "pool-timeout":
            raise PoolTimeoutError("hidden-password")
        if kind == "storage-timeout":
            raise RemoteStorageError("hidden-password") from requests.Timeout("hidden-password")
        if kind == "storage-unavailable":
            raise RemoteStorageError("hidden-password")
        if kind == "storage-config":
            raise StorageConfigurationError("hidden-password")
        if kind == "storage-raw-timeout":
            raise requests.Timeout("hidden-password")
        if kind == "sql-error":
            raise OperationalError("SELECT secret", {"password": "hidden-password"},
                                   Exception("hidden-password"))
        raise RuntimeError("hidden-password")

    api = RequestDiagnostics(fail)

    async def call(kind, request_id):
        messages = []
        scope = {
            "type": "http", "http_version": "1.1", "method": "GET",
            "scheme": "http", "path": f"/failure/{kind}", "raw_path": f"/failure/{kind}".encode(),
            "query_string": b"", "root_path": "", "server": ("test", 80),
            "client": ("test", 1),
            "headers": [(b"x-request-id", request_id.encode())],
        }

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        coroutine = api(scope, receive, send)
        try:
            coroutine.send(None)
        except StopIteration:
            pass
        else:
            raise AssertionError("Unexpected suspended ASGI coroutine")
        start = next(message for message in messages if message["type"] == "http.response.start")
        body = b"".join(message.get("body", b"") for message in messages)
        return start["status"], dict(start["headers"]), body

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        for kind, status in (("unavailable", 503), ("pg-disconnect", 503),
                             ("pg-query-timeout", 504), ("pool-timeout", 504),
                             ("storage-timeout", 504), ("storage-raw-timeout", 504),
                             ("storage-unavailable", 503), ("storage-config", 500),
                             ("sql-error", 500), ("internal", 500)):
            actual, headers, body = await_without_loop(call(kind, "phase9-test"))
            assert actual == status
            assert headers[b"x-request-id"] == b"phase9-test"
            assert b"hidden-password" not in body
        _, headers, _ = await_without_loop(call("internal", "unsafe\tvalue"))
    assert headers[b"x-request-id"] != b"unsafe\tvalue"
    assert "request_id=phase9-test" in caplog.text
    assert "hidden-password" not in caplog.text
    assert "SELECT secret" not in caplog.text


def test_request_id_on_existing_response():
    messages = []

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 404, "headers": []})
        await send({"type": "http.response.body", "body": b"missing"})

    async def send(message):
        messages.append(message)

    await_without_loop(RequestDiagnostics(app)(
        {"type": "http", "method": "GET", "headers": []}, None, send
    ))
    assert messages[0]["status"] == 404
    assert len(dict(messages[0]["headers"])[b"x-request-id"]) == 32


def await_without_loop(coroutine):
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError("Unexpected suspended coroutine")
