from komicove_app import storage


def test_old_appdata_is_copied_without_overwriting_new_data(tmp_path, monkeypatch):
    monkeypatch.delenv("KOMICOVE_APPDATA_DIR", raising=False)
    monkeypatch.delenv("PANEL_APPDATA_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    legacy = tmp_path / "Panel"
    current = tmp_path / "Komicove"
    (legacy / "custom_covers").mkdir(parents=True)
    current.mkdir()
    (legacy / "prefs.json").write_text('{"theme":"old"}', encoding="utf-8")
    (current / "prefs.json").write_text('{"theme":"new"}', encoding="utf-8")
    (legacy / "auth_session.json").write_text('{"token":"existing"}', encoding="utf-8")
    (legacy / "custom_covers" / "cover.jpg").write_bytes(b"cover")

    assert storage._appdata_directory() == str(current)
    assert (current / "prefs.json").read_text(encoding="utf-8") == '{"theme":"new"}'
    assert (current / "auth_session.json").read_text(encoding="utf-8") == '{"token":"existing"}'
    assert (current / "custom_covers" / "cover.jpg").read_bytes() == b"cover"
    assert (legacy / "auth_session.json").exists()


def test_failed_migration_keeps_using_old_data(tmp_path, monkeypatch):
    monkeypatch.delenv("KOMICOVE_APPDATA_DIR", raising=False)
    monkeypatch.delenv("PANEL_APPDATA_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    legacy = tmp_path / "Panel"
    legacy.mkdir()

    def cannot_copy(*_args):
        raise OSError("locked")

    monkeypatch.setattr(storage, "_migrate_legacy_data", cannot_copy)
    assert storage._appdata_directory() == str(legacy)
