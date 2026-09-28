"""Launch the copied Tkinter app with isolated, disposable local data.

This exercises the redesigned shell and empty library without opening the
user's real library, session, or network account. Run from the copied repo.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    with tempfile.TemporaryDirectory(prefix="komicove-redesign-smoke-") as data_dir:
        os.environ["KOMICOVE_APPDATA_DIR"] = data_dir
        from komicove_app import library_views
        from komicove_app.storage import save_prefs

        save_prefs(lang="pt")
        with patch.object(library_views, "AuthWindow", lambda _parent, callback: callback(None)):
            with patch.object(library_views.updater, "check", return_value=None):
                app = library_views.LibraryWindow()
                failures: list[str] = []

                def check() -> None:
                    try:
                        if not getattr(app, "_library_search", None):
                            failures.append("Library search was not created")
                        if not getattr(app, "_lib_content", None):
                            failures.append("Library content was not created")
                        if not app.winfo_viewable():
                            failures.append("Desktop window is not visible")
                        if app.winfo_width() < 700:
                            failures.append("Desktop window did not lay out")
                    finally:
                        app.destroy()

                app.after(700, check)
                app.mainloop()
                if failures:
                    raise RuntimeError("; ".join(failures))
                print("Redesigned desktop shell and empty library: OK")


if __name__ == "__main__":
    main()
