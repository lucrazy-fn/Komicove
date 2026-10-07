import json
from pathlib import Path
import requests
from komicove_app import updater
from komicove_client import releases


def release(version, repository, **fields):
    return dict({'tag_name': version, 'name': 'Fixture release', 'body': 'Fixture notes',
        'html_url': f'https://github.com/{repository}/releases/tag/{version}',
        'published_at': '2026-10-06T10:00:00Z'}, **fields)


def wire(monkeypatch, primary, secondary, messages=None):
    calls = []
    class Response:
        status_code = 200
        def __init__(self, data): self.data = data
        def raise_for_status(self): pass
        def json(self): return self.data
    def get(url, **kwargs):
        calls.append(url)
        result = primary if 'PANEL-ComicBookReader' in url else secondary if 'api.github.com' in url else messages or []
        if isinstance(result, Exception): raise result
        return Response(result)
    monkeypatch.setattr(updater.requests, 'get', get)
    monkeypatch.delenv('KOMICOVE_UPDATE_MANIFEST_URL', raising=False)
    monkeypatch.delenv('PANEL_UPDATE_MANIFEST_URL', raising=False)
    return calls


def test_queries_both_official_repositories_and_selects_version_not_publish_date(monkeypatch):
    calls = wire(monkeypatch, release('0.2.9', releases.REPOSITORIES[0], published_at='2026-10-06T23:00:00Z'), release('v0.2.10', releases.REPOSITORIES[1], published_at='2026-10-05T10:00:00Z'))
    assert updater.check()['version'] == '0.2.10'
    assert updater.API_URL in calls and updater.SECOND_API_URL in calls


def test_alias_repositories_same_version_make_one_update_and_panel_keeps_download_destination(monkeypatch):
    message = {'id':'message-fixture','title':'Internal fixture','version':'0.2.2','notes':'# Official notes',
        'download_url': releases.SITE_DOWNLOAD_URL, 'source':'github','created_at':'2026-10-06T12:00:00Z'}
    wire(monkeypatch, release('v0.2.2', releases.REPOSITORIES[0]), release('0.2.2+build', releases.REPOSITORIES[1]), [message])
    items = updater.fetch()
    assert len(items) == 1 and items[0]['title'] == 'Internal fixture'
    assert items[0]['url'] == releases.SITE_DOWNLOAD_URL


def test_offline_source_does_not_hide_other_source_and_legacy_panel_series_is_ignored(monkeypatch):
    wire(monkeypatch, requests.ConnectionError('fixture offline'), release('0.3.0', releases.REPOSITORIES[1]))
    assert updater.check()['version'] == '0.3.0'
    wire(monkeypatch, release('v1.4.99', releases.REPOSITORIES[0]), release('0.2.1', releases.REPOSITORIES[1]))
    assert updater.check() is None


def test_messages_for_installed_version_are_visible_once_without_new_version_claim(monkeypatch):
    message={'id':'notice','title':'News','version':'0.2.1','notes':'Fixture news','download_url': None,'source':'manual'}
    wire(monkeypatch, release('0.2.1', releases.REPOSITORIES[0]), release('0.2.1', releases.REPOSITORIES[1]), [message])
    assert updater.check() is None
    assert updater.check([])['id'] == 'notice'
    assert updater.check(['notice']) is None
    assert updater.fetch()[0]['url'] is None
    assert not updater.is_newer(message)


def test_server_selection_overrides_github_and_reselection_has_a_new_identity(monkeypatch):
    selected={'id':'selected','selection_token':'selected:2','title':'Chosen update','version':'0.2.1.1',
        'notes':'Chosen notes','download_url':None,'source':'manual'}
    monkeypatch.setattr(updater, 'CURRENT_VERSION', '0.2.1.1')
    wire(monkeypatch, release('0.2.9', releases.REPOSITORIES[0]), release('0.2.8', releases.REPOSITORIES[1]), [selected])
    items=updater.fetch()
    assert len(items)==1 and items[0]['title']=='Chosen update'
    assert updater.check(['selected:1'])['selection_token']=='selected:2'
    assert updater.check(['selected:2']) is None


def test_shared_version_order_and_android_marker_contract():
    contract=json.loads((Path(__file__).parents[1]/'android/app/src/test/resources/update_versions.json').read_text())
    for older,newer in contract['ordered_pairs']:
        assert releases.version_key(older)<releases.version_key(newer)
    for first,second in contract['equal_versions']:
        assert releases.version_id(first)==releases.version_id(second)
    assert releases.platform_version('0.2.3', contract['notes'], 'android') == '0.2.4'
    assert releases.platform_version('0.2.3', contract['notes']) == '0.2.3'


def test_changelog_is_not_replaced_in_english_and_role_is_translated(monkeypatch):
    from komicove_app import runtime
    from komicove_app.library_views import LibraryWindow
    from komicove_app.account_views import _role_label
    monkeypatch.setattr(runtime,'LANG','en')
    assert LibraryWindow._release_notes(None, {'notes': '# Conteúdo original\n**do autor**'}) == 'Conteúdo original\ndo autor'
    assert _role_label('contributor') == 'Contributor'


def test_revision_release_is_recognized_and_android_marker_keeps_four_numbers(monkeypatch):
    assert releases.platform_version('v0.2.1.1', 'Android version 0.2.1.1', 'android') == '0.2.1.1'
    monkeypatch.setattr(updater, 'CURRENT_VERSION', '0.2.1')
    wire(monkeypatch, release('v0.2.1.1', releases.REPOSITORIES[0]), release('0.2.1', releases.REPOSITORIES[1]))
    assert updater.check()['version'] == '0.2.1.1'
    monkeypatch.setattr(updater, 'CURRENT_VERSION', '0.2.1.1')
    assert updater.check() is None


def test_legacy_manifest_override_is_preserved_with_second_source(monkeypatch):
    calls=[]
    class Response:
        status_code=200
        def raise_for_status(self): pass
        def json(self): return {'version':'0.2.5','notes':'Custom fixture'} if 'manifest' in calls[-1] else [] if calls[-1].endswith('/updates') else release('0.2.4', releases.REPOSITORIES[1])
    monkeypatch.setattr(updater.requests,'get',lambda url,**kw: (calls.append(url),Response())[1])
    monkeypatch.setenv('PANEL_UPDATE_MANIFEST_URL','https://fixture.invalid/manifest')
    assert updater.check()['version']=='0.2.5'
    assert updater.SECOND_API_URL in calls
