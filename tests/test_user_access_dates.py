from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from komicove_backend.api.app import app
from komicove_backend.api.deps import get_db
from komicove_backend.accounts import service
from komicove_backend.accounts.models import User
from komicove_backend import db as database


def test_record_access_throttles_updates(monkeypatch):
    now = datetime(2026, 9, 18, 12)
    monkeypatch.setattr(service, '_now', lambda: now)
    user = User()
    service.record_access(user)
    assert user.last_seen_at == now
    user.last_seen_at = now - timedelta(seconds=30)
    service.record_access(user)
    assert user.last_seen_at == now - timedelta(seconds=30)
    user.last_seen_at = now - timedelta(seconds=61)
    service.record_access(user)
    assert user.last_seen_at == now


def test_admin_dates_not_public():
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    def override():
        with sessions.begin() as db:
            yield db
    with sessions.begin() as db:
        owner = service.register_user(db, username='dateowner', password='testing-password')
        owner.user.role = 'owner'
        user = service.register_user(db, username='dateuser', password='testing-password')
        user_id, owner_token, user_token = user.user.id, owner.token, user.token
    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    try:
        headers = {'Authorization': 'Bearer ' + user_token}
        assert client.get('/api/moderators/users', headers=headers).status_code == 403
        response = client.get('/auth/me', headers=headers)
        assert response.status_code == 200
        assert 'last_seen_at' not in response.json()
        response = client.get('/api/moderators/users', headers={'Authorization': 'Bearer ' + owner_token})
        assert response.status_code == 200
        row = next(row for row in response.json() if row['id'] == user_id)
        assert row['created_at'] and row['last_seen_at']
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()


def test_access_migration_keeps_old_users(monkeypatch):
    engine = create_engine('sqlite://')
    database.Base.metadata.create_all(engine)
    with engine.begin() as db:
        db.execute(text('ALTER TABLE users DROP COLUMN last_seen_at'))
    monkeypatch.setattr(database, '_engine', engine)
    database._migrate_legacy_schema()
    database._migrate_legacy_schema()
    assert 'last_seen_at' in {c['name'] for c in inspect(engine).get_columns('users')}
