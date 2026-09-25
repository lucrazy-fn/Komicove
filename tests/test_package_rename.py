from importlib import import_module
from pathlib import Path


def test_render_legacy_start_command_still_resolves():
    legacy = import_module("panel_backend.api.app")
    current = import_module("komicove_backend.api.app")
    assert legacy.app.title == current.app.title == "Komicove API"


def test_android_keeps_installed_app_identity():
    root = Path(__file__).parents[1]
    gradle = (root / "android/app/build.gradle").read_text(encoding="utf-8")
    manifest = (root / "android/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    assert "namespace 'com.lucrazy.komicove'" in gradle
    assert "applicationId 'com.lucrazy.panel'" in gradle
    assert 'android:name="com.lucrazy.komicove.MainActivity"' in manifest
