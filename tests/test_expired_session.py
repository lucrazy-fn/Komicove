from types import SimpleNamespace

import pytest

from komicove_app import library_views
from komicove_client import api_client
from komicove_client import session_store


class _Response:
    status_code = 403

    @staticmethod
    def json():
        return {"detail": "Credenciais inválidas."}


class _ServerFailure:
    status_code = 500

    @staticmethod
    def json():
        return {"detail": "500 Internal Server Error"}


def test_forbidden_api_response_is_an_authentication_error():
    with pytest.raises(api_client.ApiAuthError, match="Credenciais inválidas"):
        api_client._raise_response_error(
            _Response(), "fallback", auth_statuses=(400, 401, 403, 409, 422)
        )


def test_forbidden_response_remains_a_server_error_for_permission_checks():
    with pytest.raises(api_client.ApiServerError, match="Credenciais inválidas"):
        api_client._raise_response_error(_Response(), "fallback")


def test_internal_server_details_are_not_shown_to_users():
    with pytest.raises(api_client.ApiServerError, match="temporariamente indisponível") as error:
        api_client._raise_response_error(_ServerFailure(), "fallback")
    assert "Internal Server Error" not in str(error.value)


def test_server_failure_keeps_saved_session(monkeypatch):
    existing = SimpleNamespace(token="saved-token")
    finished = []
    cleared = []

    class ImmediateThread:
        def __init__(self, *, target, daemon):
            self.target = target

        def start(self):
            self.target()

    window = SimpleNamespace(
        after=lambda delay, callback: callback(),
        _finish_saved_session=lambda user, usable: finished.append((user, usable)),
    )
    monkeypatch.setattr(library_views, "_ACCOUNTS_AVAILABLE", True)
    monkeypatch.setattr(library_views.session_store, "load_session", lambda: existing)
    monkeypatch.setattr(library_views.session_store, "clear_session", lambda: cleared.append(True))
    monkeypatch.setattr(
        library_views.api_client,
        "get_current_user",
        lambda token: (_ for _ in ()).throw(api_client.ApiServerError("offline")),
    )
    monkeypatch.setattr(library_views.threading, "Thread", ImmediateThread)

    library_views.LibraryWindow._show_auth(window)

    assert finished == [(existing, True)]
    assert cleared == []


def test_clear_session_tolerates_a_temporarily_locked_file(tmp_path, monkeypatch):
    session_file = tmp_path / "auth_session.json"
    session_file.write_text("{}", encoding="utf-8")
    attempts = []
    monkeypatch.setattr(session_store, "SESSION_FILE", str(session_file))

    def locked(path):
        attempts.append(path)
        raise PermissionError("File is being inspected")

    monkeypatch.setattr(session_store.os, "remove", locked)
    monkeypatch.setattr(session_store.time, "sleep", lambda delay: None)

    session_store.clear_session()

    assert attempts == [str(session_file)] * 3


def test_expired_session_keeps_app_in_local_guest_mode(monkeypatch):
    warnings = []
    monkeypatch.setattr(
        library_views.messagebox,
        "showwarning",
        lambda title, message, parent=None: warnings.append((title, message, parent)),
    )
    window = SimpleNamespace(
        current_user=SimpleNamespace(token="expired-token"),
        _session_expiry_handled=False,
        _sync_job=object(),
    )

    library_views.LibraryWindow._finish_expired_session(window, "expired-token")

    assert window.current_user is None
    assert window._sync_job is None
    assert window._session_expiry_handled is True
    assert len(warnings) == 1
    assert "local" in warnings[0][1].lower()


def test_profile_client_rejects_server_that_silently_ignores_bio(monkeypatch):
    monkeypatch.setattr(
        api_client,
        "_request_json",
        lambda *args, **kwargs: {"display_name": "Luan", "email": None},
    )
    with pytest.raises(api_client.ApiFeatureUnavailableError, match="Bio"):
        api_client.update_profile("token", "Luan", None, "Minha bio")


def test_profile_client_accepts_persisted_bio(monkeypatch):
    monkeypatch.setattr(
        api_client,
        "_request_json",
        lambda *args, **kwargs: {
            "display_name": "Luan", "email": None, "bio": "Minha bio",
        },
    )
    result = api_client.update_profile("token", "Luan", None, "Minha bio")
    assert result["bio"] == "Minha bio"
