"""Open the redesigned authentication screen without contacting production."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    with tempfile.TemporaryDirectory(prefix="komicove-auth-preview-") as profile:
        os.environ["KOMICOVE_APPDATA_DIR"] = profile
        import tkinter as tk
        from komicove_app.auth_views import AuthWindow
        from komicove_app.storage import save_prefs

        save_prefs(lang="pt")
        root = tk.Tk()
        root.withdraw()
        dialog = AuthWindow(root, lambda _auth: root.destroy())
        if "--register" in sys.argv:
            dialog.after(250, lambda: dialog._switch_mode("register"))
        root.mainloop()


if __name__ == "__main__":
    main()
