"""Komicove settings with support for existing PANEL deployments."""

import os


def setting(name: str, default: str = "") -> str:
    suffix = name.removeprefix("KOMICOVE_")
    return (os.environ.get("KOMICOVE_" + suffix)
            or os.environ.get("PANEL_" + suffix)
            or default)
