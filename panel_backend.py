"""Compatibility for Render commands that still import panel_backend.api.app.

The implementation lives in komicove_backend. Keep this module until the
Render start command has been updated to komicove_backend.api.app:app.
"""

from pathlib import Path

__path__ = [str(Path(__file__).resolve().parent / "komicove_backend")]
