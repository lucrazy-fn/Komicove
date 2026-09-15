
from __future__ import annotations

import os
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def _database_url() -> str:
    return os.environ.get("PANEL_DATABASE_URL", "sqlite:///./panel.db")


_engine = create_engine(
    _database_url(),
    connect_args={"check_same_thread": False} if _database_url().startswith("sqlite") else {},
)
_SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


def init_db() -> None:
    pass


    from panel_backend.accounts import models as _accounts_models  # noqa: F401
    from panel_backend.catalog import models as _catalog_models    # noqa: F401
    from panel_backend.moderation import db_models as _moderation_models  # noqa: F401

    Base.metadata.create_all(_engine)
    _migrate_legacy_schema()


def _migrate_legacy_schema() -> None:
    pass
    inspector = inspect(_engine)
    if "users" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "is_moderator" not in columns:
        with _engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE users ADD COLUMN is_moderator BOOLEAN NOT NULL DEFAULT 0"
            ))
    if "suspended_until" not in columns:
        with _engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ADD COLUMN suspended_until DATETIME"))
    if "punishment_reason" not in columns:
        with _engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ADD COLUMN punishment_reason VARCHAR(255)"))
    if "deleted_at" not in columns:
        with _engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ADD COLUMN deleted_at DATETIME"))
    if "role" not in columns:
        with _engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(16) NOT NULL DEFAULT 'user'"))
            connection.execute(text("UPDATE users SET role = 'moderator' WHERE is_moderator = 1"))
            connection.execute(text(
                "UPDATE users SET role = 'owner' WHERE id = ("
                "SELECT id FROM users WHERE is_moderator = 1 AND deleted_at IS NULL "
                "ORDER BY created_at ASC LIMIT 1)"
            ))
    with _engine.begin() as connection:
        if "email_verified" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT 0"))
        if "totp_secret" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN totp_secret VARCHAR(64)"))
        if "totp_enabled" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN totp_enabled BOOLEAN NOT NULL DEFAULT 0"))
        for name, sql_type in (("totp_pending_secret", "VARCHAR(64)"),
                               ("totp_pending_session", "VARCHAR(64)"),
                               ("totp_pending_expires_at", "TIMESTAMP")):
            if name not in columns:
                connection.execute(text(f"ALTER TABLE users ADD COLUMN {name} {sql_type}"))
    if "library_states" in inspector.get_table_names():
        library_columns = {column["name"] for column in inspector.get_columns("library_states")}
        if "client_updated_at" not in library_columns:
            with _engine.begin() as connection:
                connection.execute(text(
                    "ALTER TABLE library_states ADD COLUMN client_updated_at REAL NOT NULL DEFAULT 0"
                ))
    if "comics" in inspector.get_table_names():
        comic_columns = {column["name"] for column in inspector.get_columns("comics")}
        with _engine.begin() as connection:
            if "series_title" not in comic_columns:
                connection.execute(text("ALTER TABLE comics ADD COLUMN series_title VARCHAR(255)"))
            if "chapter_number" not in comic_columns:
                connection.execute(text("ALTER TABLE comics ADD COLUMN chapter_number INTEGER"))


@contextmanager
def get_session():
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
