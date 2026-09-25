from komicove_backend.config_env import setting


def test_new_prefix_takes_priority_over_legacy(monkeypatch):
    monkeypatch.setenv("PANEL_DATABASE_URL", "sqlite:///./old.db")
    monkeypatch.setenv("KOMICOVE_DATABASE_URL", "sqlite:///./new.db")
    assert setting("KOMICOVE_DATABASE_URL") == "sqlite:///./new.db"


def test_existing_render_prefix_still_works(monkeypatch):
    monkeypatch.delenv("KOMICOVE_DATABASE_URL", raising=False)
    monkeypatch.setenv("PANEL_DATABASE_URL", "postgresql://existing-server")
    assert setting("KOMICOVE_DATABASE_URL") == "postgresql://existing-server"
