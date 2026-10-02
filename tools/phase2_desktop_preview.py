"""Isolated visual QA fixture. Never opens the user's account or library."""
import io
import os
import sys
import tempfile
import shutil
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
test_root = Path(tempfile.mkdtemp(prefix="komicove-phase2-preview-"))
os.environ["KOMICOVE_APPDATA_DIR"] = str(test_root / "data")
from PIL import Image
from komicove_app.monitored_folders import FolderIndex
from komicove_app.storage import save_prefs
from komicove_app.library_views import LibraryWindow
from komicove_app import runtime

clock = [100.0]
index = FolderIndex(test_root / "data" / "monitored_folders.json", clock=lambda: clock[0])
for name, color in [("Quadrinhos de teste", "#b8192e"), ("Leituras pendentes", "#164d87"), ("Independentes", "#965321")]:
    folder = test_root / name
    folder.mkdir()
    index.add(folder)
    for n in range(2):
        png = io.BytesIO()
        Image.new("RGB", (160, 240), color).save(png, format="PNG")
        with zipfile.ZipFile(folder / f"Teste {n}.cbz", "w") as archive:
            archive.writestr("001.jpg", png.getvalue())
            archive.comment = f"{name}:{n}".encode()
index.add(test_root / "Pasta desconectada")
index.rescan()
clock[0] += 4
index.rescan()
save_prefs(lang="pt")


class Preview(LibraryWindow):
    def _show_auth(self):
        self._active_tab = "library"
        self._build_shell()
        self.deiconify()
        self.title("Komicove — Teste visual Fase 2")
        self.geometry("1000x700" if "--small" in sys.argv else "1672x941")
        self._show_folders()


window = Preview()
window.after(100, lambda: window._show_folders())
try:
    window.mainloop()
finally:
    window._folder_watcher.thread.join(3)
    if test_root.resolve().parent == Path(tempfile.gettempdir()).resolve() and test_root.name.startswith("komicove-phase2-preview-"):
        shutil.rmtree(test_root)
