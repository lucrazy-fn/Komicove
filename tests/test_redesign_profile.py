import komicove_app.runtime as runtime
from komicove_app.account_views import _role_label


def test_profile_roles_use_portuguese_labels(monkeypatch):
    monkeypatch.setattr(runtime, "LANG", "pt")
    assert _role_label("owner") == "Dono"
    assert _role_label("moderator") == "Moderador"
    assert _role_label("user") == "Usuário"


def test_profile_roles_use_english_labels(monkeypatch):
    monkeypatch.setattr(runtime, "LANG", "en")
    assert _role_label("owner") == "Owner"
    assert _role_label("moderator") == "Moderator"
    assert _role_label("user") == "User"
