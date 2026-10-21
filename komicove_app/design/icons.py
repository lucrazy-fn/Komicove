"""Local Lucide icon loader for Tkinter and CustomTkinter controls."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageTk


def _resource_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    if Path("/.flatpak-info").exists():
        return Path("/app")
    return Path(__file__).resolve().parents[2]


_ROOT = _resource_root()
_GENERATED = _ROOT / "assets_redesign" / "icons" / "generated"
_CACHE: dict[tuple[str, int, str, bool], ImageTk.PhotoImage] = {}


def lucide_icon(name: str, *, size: int = 18, state: str = "normal",
                dark: bool = True) -> ImageTk.PhotoImage | None:
    """Return a cached Tk image without doing any network access at runtime."""
    state = state if state in {"normal", "hover", "active", "white"} else "normal"
    key = (name, size, state, dark)
    if key in _CACHE:
        return _CACHE[key]
    variant = "white" if state == "white" else f"{'dark' if dark else 'light'}-{state}"
    path = _GENERATED / variant / f"{name}.png"
    if not path.exists():
        return None
    image = Image.open(path).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    tk_image = ImageTk.PhotoImage(image)
    _CACHE[key] = tk_image
    return tk_image


def clear_icon_cache() -> None:
    """Drop theme-specific Tk images after the application theme changes."""
    _CACHE.clear()
