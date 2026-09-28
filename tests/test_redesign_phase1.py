"""Static checks for the isolated Tkinter redesign's first phase."""

from pathlib import Path

from komicove_app.design.colors import DARK, LIGHT
from komicove_app.design.spacing import SIDEBAR_WIDTH


ROOT = Path(__file__).resolve().parent.parent


def test_palettes_keep_all_legacy_tokens():
    assert DARK.keys() == LIGHT.keys()
    assert {"bg", "surface", "surface_alt", "border", "accent", "text",
            "canvas_bg", "progress_bg", "search_bg"} <= DARK.keys()
    assert DARK["accent"] != DARK["bg"]
    assert SIDEBAR_WIDTH >= 200


def test_only_real_art_assets_are_used_in_phase_one():
    assert (ROOT / "assets_redesign/banners/library_noir.png").is_file()
    assert (ROOT / "assets_redesign/backgrounds/auth_noir.png").is_file()
    assert not (ROOT / "assets_redesign/screenshots").exists()


def test_git_configuration_matches_workspace_role():
    if ROOT.name.endswith("-REDESIGN"):
        assert not (ROOT / ".git").exists()
    else:
        assert (ROOT / ".git").exists()
