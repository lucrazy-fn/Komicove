from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from komicove_backend.accounts import contributor_invites
from komicove_backend.accounts.models import User, ContributorInvite, AdminAuditLog, AppUpdate, AppUpdateSelection, _now
from komicove_backend.api.app import app
from komicove_backend.api.deps import get_db
from komicove_backend.db import Base
from komicove_client import releases


@pytest.fixture
def backend(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'api.db'), connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    def override():
        with factory.begin() as db:
            yield db
    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as client:
            sessions = {}
            for role in ('user', 'contributor', 'moderator', 'admin', 'owner'):
                response = client.post('/auth/register', json={'username': 'fixture.' + role, 'password': 'fixture-password'}).json()
                sessions[role] = {'Authorization': 'Bearer ' + response['token']}
                with factory.begin() as db:
                    user = db.get(User, response['user']['id'])
                    user.role = role
                    user.is_moderator = role in {'moderator', 'admin', 'owner'}
            yield client, sessions, factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_token_single_use_history_hash_only_and_existing_session(backend):
    client, sessions, factory = backend
    generated = client.post('/api/contributor-tokens', headers=sessions['moderator'], json={})
    assert generated.status_code == 201
    assert generated.headers['cache-control'] == 'no-store'
    secret = generated.json()['secret']
    assert len(secret) >= 50
    with factory() as db:
        invite = db.get(ContributorInvite, generated.json()['id'])
        assert invite.token_hash != secret and len(invite.token_hash) == 64
    response = client.post('/account/contributor-token', headers=sessions['user'], json={'token': secret})
    assert response.status_code == 200
    assert response.json()['role'] == 'contributor' and response.json()['is_moderator'] is False
    assert client.get('/auth/me', headers=sessions['user']).json()['role'] == 'contributor'
    assert client.post('/account/contributor-token', headers=sessions['user'], json={'token': secret}).status_code == 409
    other = client.post('/auth/register', json={'username': 'fixture.other', 'password': 'fixture-password'}).json()
    assert client.post('/account/contributor-token', headers={'Authorization': 'Bearer ' + other['token']}, json={'token': secret}).status_code == 400
    assert client.get('/auth/me', headers={'Authorization': 'Bearer ' + other['token']}).json()['role'] == 'user'
    row = client.get('/api/contributor-tokens', headers=sessions['admin']).json()[0]
    assert row['status'] == 'used' and row['used_by_username'] == 'fixture.user' and row['used_at']
    assert 'secret' not in row and 'token_hash' not in row
    with factory() as db:
        assert all(secret not in (a.details or '') for a in db.scalars(select(AdminAuditLog)))


@pytest.mark.parametrize('role', ['user', 'contributor'])
def test_non_moderators_cannot_administer_tokens_or_updates(backend, role):
    client, sessions, _ = backend
    for path in ('/api/contributor-tokens', '/api/moderators/updates', '/api/moderators/releases?repository=' + releases.REPOSITORIES[0]):
        assert client.get(path, headers=sessions[role]).status_code == 403
    for path, payload in [('/api/contributor-tokens', {}), ('/api/moderators/updates/preview', {'notes': 'fixture'}), ('/api/moderators/updates', message())]:
        assert client.post(path, headers=sessions[role], json=payload).status_code == 403
    assert client.put('/api/moderators/updates/unknown/selection', headers=sessions[role]).status_code == 403
    assert client.delete('/api/contributor-tokens/unknown', headers=sessions[role]).status_code == 403


def test_expired_revoked_invalid_and_higher_role_never_consume_or_promote(backend):
    client, sessions, factory = backend
    created = client.post('/api/contributor-tokens', headers=sessions['admin'], json={}).json()
    assert client.post('/account/contributor-token', headers=sessions['owner'], json={'token': created['secret']}).status_code == 409
    assert client.get('/api/contributor-tokens', headers=sessions['moderator']).json()[0]['status'] == 'available'
    assert client.delete('/api/contributor-tokens/' + created['id'], headers=sessions['moderator']).status_code == 204
    assert client.post('/account/contributor-token', headers=sessions['user'], json={'token': created['secret']}).status_code == 400
    expired = client.post('/api/contributor-tokens', headers=sessions['moderator'], json={}).json()
    with factory.begin() as db:
        db.get(ContributorInvite, expired['id']).expires_at = _now() - timedelta(seconds=1)
    for secret in (expired['secret'], 'not-a-valid-contributor-token'):
        assert client.post('/account/contributor-token', headers=sessions['user'], json={'token': secret}).status_code == 400
        assert client.get('/auth/me', headers=sessions['user']).json()['role'] == 'user'
    assert client.post('/api/contributor-tokens', headers=sessions['moderator'], json={'max_uses': 2}).status_code == 422


def test_concurrent_redemption_has_one_winner_and_failed_claim_rolls_back(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'race.db'), connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine); factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        people = [User(username=name, password_hash='fixture', password_salt='fixture', role='user') for name in ('creator', 'first', 'second')]
        db.add_all(people); db.flush()
        ids = [u.id for u in people]
        invite, secret = contributor_invites.generate(db, people[0], 24)
    def redeem(user_id):
        with factory.begin() as db:
            return contributor_invites.consume(db, db.get(User, user_id), secret) is not None
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(redeem, ids[1:])) == 1
    with factory() as db:
        assert sorted(db.get(User, key).role for key in ids[1:]) == ['contributor', 'user']
    engine.dispose()


def message(**values):
    return dict({'source': 'manual', 'title': 'Fixture update', 'version': '0.2.2',
        'notes': '# Changelog\n\n**Fixture** change', 'download_destination': 'site'}, **values)


def test_manual_update_preview_permissions_history_and_public_feed(backend):
    client, sessions, factory = backend
    response = client.post('/api/moderators/updates', headers=sessions['moderator'], json=message())
    assert response.status_code == 201
    data = response.json()
    assert data['download_url'] == releases.SITE_DOWNLOAD_URL
    assert data['created_by_username'] == 'fixture.moderator' and data['created_at'].endswith('Z')
    assert data['source'] == 'manual' and data['source_repository'] is None
    assert '<strong>Fixture</strong>' in data['notes_html']
    assert client.get('/updates').json()[0] == data
    assert client.get('/api/moderators/updates', headers=sessions['owner']).json()[0] == data
    assert client.get('/api/moderators/updates').status_code == 401
    preview = client.post('/api/moderators/updates/preview', headers=sessions['moderator'], json={'notes': '<script>x</script>\n![x](https://tracker.invalid/x)\n[x](javascript:alert(1))'}).json()['html']
    assert '<script' not in preview and '<img' not in preview and 'href="javascript:' not in preview
    with factory() as db:
        assert len(db.scalars(select(AppUpdate)).all()) == 1
    for values in ({'assets': []}, {'version': 'invalid'}, {'download_url': 'https://evil.invalid/download'}, {'download_destination':'github','download_url':'javascript:alert(1)'}):
        assert client.post('/api/moderators/updates', headers=sessions['admin'], json=message(**values)).status_code == 422


def test_selected_update_is_the_only_public_item_and_history_is_preserved(backend):
    client, sessions, factory = backend
    first = client.post('/api/moderators/updates', headers=sessions['moderator'], json=message(version='0.2.1', title='First')).json()
    second = client.post('/api/moderators/updates', headers=sessions['moderator'], json=message(version='0.2.1.1', title='Second')).json()
    public = client.get('/updates').json()
    assert [item['id'] for item in public] == [second['id']]
    assert public[0]['selected'] is True and public[0]['selection_token']
    history = client.get('/api/moderators/updates', headers=sessions['moderator']).json()
    assert [item['id'] for item in history] == [second['id'], first['id']]
    assert [item['selected'] for item in history] == [True, False]
    changed = client.put(f"/api/moderators/updates/{first['id']}/selection", headers=sessions['admin'])
    assert changed.status_code == 200 and changed.json()['selected'] is True
    assert [item['id'] for item in client.get('/updates').json()] == [first['id']]
    history = client.get('/api/moderators/updates', headers=sessions['owner']).json()
    assert [item['selected'] for item in history] == [False, True]
    assert client.put('/api/moderators/updates/unknown/selection', headers=sessions['moderator']).status_code == 404
    with factory() as db:
        assert db.get(AppUpdateSelection, 1).update_id == first['id']
        assert any(row.action == 'app_update_selected' for row in db.scalars(select(AdminAuditLog)))


def test_import_is_read_only_and_server_resolves_official_release(backend, monkeypatch):
    client, sessions, _ = backend
    calls = []
    raw = {'id': 17, 'tag_name': 'v0.2.3', 'name': 'Official fixture', 'body': '**Official** notes', 'html_url': 'https://github.com/lucrazy-fn/Komicove/releases/tag/v0.2.3'}
    def get(repository, endpoint):
        calls.append((repository, endpoint))
        return [raw] if '?' in endpoint else raw
    monkeypatch.setattr(releases, 'github_get', get)
    rows = client.get('/api/moderators/releases', params={'repository': releases.REPOSITORIES[1]}, headers=sessions['moderator']).json()
    assert rows[0]['version'] == 'v0.2.3'
    payload = {'source': 'github', 'repository': releases.REPOSITORIES[1], 'release_id': 17, 'download_destination': 'github'}
    response = client.post('/api/moderators/updates', headers=sessions['moderator'], json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data['notes'] == raw['body'] and data['title'] == raw['name']
    assert data['source_release_id'] == 17 and data['source_release_url'] == raw['html_url']
    assert data['download_url'] == releases.release_url('v0.2.3')
    assert calls == [(releases.REPOSITORIES[1], '?per_page=30'), (releases.REPOSITORIES[1], '/17')]
    for invalid in ({'repository': 'attacker/repo'}, {'title': 'spoofed'}, {'download_url': 'https://github.com/attacker/repo/releases/latest'}):
        assert client.post('/api/moderators/updates', headers=sessions['admin'], json=dict(payload, **invalid)).status_code == 422


def test_contributor_does_not_gain_legacy_moderation_flag(backend):
    client, sessions, factory = backend
    with factory() as db:
        user_id = db.scalar(select(User.id).where(User.username == 'fixture.user'))
    response = client.patch('/api/moderators/users/' + user_id, headers=sessions['owner'], json={'action': 'set_role', 'role': 'contributor'})
    assert response.status_code == 200 and response.json()['is_moderator'] is False
    assert client.get('/auth/me', headers=sessions['user']).status_code == 401  # Existing role changes revoke sessions.
    signed_in = client.post('/auth/login', json={'username': 'fixture.user', 'password': 'fixture-password'}).json()
    assert client.get('/moderation/queue', headers={'Authorization': 'Bearer ' + signed_in['token']}).status_code == 403


def test_two_tokens_for_one_account_only_consume_one(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'account-race.db'), connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine); factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        user = User(username='fixture', password_hash='fixture', password_salt='fixture', role='user')
        db.add(user); db.flush(); user_id = user.id
        secrets = [contributor_invites.generate(db, user, 24)[1] for _ in range(2)]
    def redeem(secret):
        with factory.begin() as db:
            return contributor_invites.consume(db, db.get(User, user_id), secret) is not None
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(redeem, secrets)) == 1
    with factory() as db:
        assert sum(i.used_at is not None for i in db.scalars(select(ContributorInvite))) == 1
        assert db.get(User, user_id).role == 'contributor'
    engine.dispose()


def test_incremental_migration_preserves_existing_account_and_library(tmp_path, monkeypatch):
    from komicove_backend import db as database
    from komicove_backend.accounts.models import LibraryState, ModeratorInvite, SessionToken
    from sqlalchemy import inspect
    engine = create_engine('sqlite:///' + str(tmp_path / 'old.db'))
    Base.metadata.create_all(engine, tables=[table for table in Base.metadata.sorted_tables if table.name not in {'app_updates','contributor_invites'}])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        user = User(username='fixture.old', password_hash='fixture', password_salt='fixture', role='admin', is_moderator=True)
        db.add(user); db.flush(); user_id = user.id
        db.add(SessionToken(token='fixture-old-session', user_id=user_id))
        db.add(LibraryState(user_id=user_id, item_key='fixture-old-id', page=17, favorite=True))
        invite, secret = __import__('komicove_backend.accounts.moderator_invites', fromlist=['generate']).generate(db, user, max_uses=3, valid_hours=24)
        invite_id = invite.id
    monkeypatch.setattr(database, '_engine', engine)
    database.init_db(); database.init_db()
    assert {'app_updates','app_update_selection','contributor_invites'} <= set(inspect(engine).get_table_names())
    with factory() as db:
        assert db.get(User, user_id).role == 'admin' and db.get(User, user_id).is_moderator
        assert db.get(SessionToken, 'fixture-old-session').is_valid()
        state = db.scalar(select(LibraryState))
        assert state.item_key == 'fixture-old-id' and state.page == 17 and state.favorite
        assert db.get(ModeratorInvite, invite_id).max_uses == 3 and db.get(ModeratorInvite, invite_id).is_usable()
    engine.dispose()


def test_panel_assets_allowlist_and_release_pagination(backend, monkeypatch):
    client, sessions, _ = backend
    for asset in ('moderators-i18n.js','moderators-features.js'):
        response = client.get('/moderators/' + asset)
        assert response.status_code == 200 and 'javascript' in response.headers['content-type']
    assert client.get('/moderators/unknown.js').status_code == 404
    assert client.get('/api/moderators/releases', params={'repository':releases.REPOSITORIES[0], 'page':0}, headers=sessions['moderator']).status_code == 422
    calls=[]
    monkeypatch.setattr(releases, 'github_get', lambda repo, endpoint: calls.append(endpoint) or [])
    assert client.get('/api/moderators/releases', params={'repository':releases.REPOSITORIES[0], 'page':2}, headers=sessions['moderator']).status_code == 200
    assert calls == ['?per_page=30&page=2']


def test_download_url_is_derived_from_version_and_cannot_be_overridden(backend):
    client, sessions, _ = backend
    response = client.post('/api/moderators/updates', headers=sessions['moderator'], json=message(version='v0.2.1',download_destination='github'))
    assert response.status_code == 201
    assert response.json()['download_url'] == 'https://github.com/lucrazy-fn/PANEL-ComicBookReader/releases/tag/v0.2.1'
    response = client.post('/api/moderators/updates', headers=sessions['moderator'], json=message(download_destination='github',download_url='https://github.com/lucrazy-fn/PANEL-ComicBookReader/releases/tag/v0.2.1'))
    assert response.status_code == 422
