"""Exercise the local reader controls with an authorial CBZ under a GUI/Xvfb."""

from pathlib import Path
from time import monotonic, sleep
from unittest.mock import patch
import os
import tempfile
import zipfile
import tkinter as tk
from PIL import ImageGrab

from komicove_app.archive import SmartPageLoader
from komicove_app.reader_views import ReaderWindow
from komicove_app.reader import save_manual_panels, load_manual_panels
from komicove_app.storage import save_prefs
from komicove_app.comic_translation import auto_translation_candidate


def pump(root, condition, seconds=60):
    deadline = monotonic() + seconds
    while monotonic() < deadline:
        root.update()
        if condition():
            return
        sleep(.02)
    raise AssertionError("GUI work did not finish")


def main():
    path = Path(__file__).resolve().parents[1] / "build/translation-fixtures/authorial-ocr.cbz"
    assert path.is_file(), "Run tools/translation_fixture.py first"
    save_prefs(reader_guided=True, reader_animate_guided=False)
    root = tk.Tk()
    root.withdraw()
    reader = ReaderWindow(root, str(path), SmartPageLoader(path))
    try:
        pump(root, lambda: reader.winfo_width() > 100)
        panels = [(0.0, 0.0, 1.0, .5), (0.0, .5, 1.0, 1.0)]
        save_manual_panels(reader._content_key, 0, panels)
        reader._guide_key = None
        reader._show(reset=False)
        assert reader._guided and reader._regions == panels
        reader._translation_dialog()
        dialog = reader._translation_window
        assert "experimental" in dialog.title().casefold()
        pump(root, lambda: dialog.future.done())
        dialog.source.set("en")
        dialog.target.set("pt")
        dialog.ocr_language.set("eng")
        dialog.provider.set("local")
        dialog.mode.set("local")
        dialog._mode_changed()
        dialog._start(False)
        pump(root, lambda: bool(dialog.regions))
        assert dialog.regions, (f"OCR found no regions: {dialog.status.cget('text')}; "
                                f"future={dialog.future.exception() if dialog.future.done() else 'running'}")
        assert any("HELLO" in row.original for row in dialog.regions)
        if os.environ.get("KOMICOVE_SMOKE_REAL_LOCAL") == "1":
            dialog._start(True)
            pump(root, lambda: dialog.future.done() and any(row.translated for row in dialog.regions))
        else:
            with patch("komicove_app.translation_views.local_translation_available", return_value=True), \
                 patch("komicove_app.translation_views.local_model_offer", return_value=(None, None)), \
                 patch("komicove_app.translation_views.local_translate", return_value="Olá, herói!"):
                dialog._start(True)
                pump(root, lambda: dialog.future.done() and any(row.translated for row in dialog.regions))
        assert all(row.translated for row in dialog.regions if auto_translation_candidate(row))
        with tempfile.TemporaryDirectory(prefix="komicove-export-") as directory:
            exported = Path(directory) / "authorial-translated.cbz"
            changed = dialog._work_export(exported, dialog._settings(), {}, reader._rotation)
            assert changed > 0 and exported.is_file()
            with zipfile.ZipFile(path) as source, zipfile.ZipFile(exported) as result:
                assert source.namelist() == result.namelist()
                assert any(source.read(name) != result.read(name) for name in source.namelist())
            reopened = SmartPageLoader(exported)
            try:
                assert reopened.count == reader._count
                assert reopened.get_pil(0).size == reader._loader.get_pil(0).size
            finally:
                reopened.close()
        dialog.view.set("overlay")
        dialog._set_view()
        assert reader._translation_page == reader._idx
        assert reader._translation_regions
        dialog.view.set("compare")
        dialog._set_view()
        pump(root, lambda: dialog.preview_layout is not None and
             dialog.preview_layout[2] > dialog.preview_layout[0])
        dialog._zoom_preview(1.5)
        assert dialog.preview_zoom > 1
        dialog._zoom_preview(1, reset=True)
        assert dialog.preview_zoom == 1
        dialog.view.set("overlay")
        dialog._set_view()
        zoom = reader._guided_zoom
        reader._next()
        assert reader._idx == 0 and reader._region_index == 1
        assert reader._guided_zoom == zoom
        assert load_manual_panels(reader._content_key, 0) == [list(panel) for panel in panels]
        original_box = reader._translation_regions[0].box
        reader._rotate()
        assert reader._translation_regions[0].box != original_box
        assert reader._guided_zoom == zoom
        assert load_manual_panels(reader._content_key, 0) == [list(panel) for panel in panels]
        before = reader._idx
        reader._idx = min(reader._count - 1, before + 1)
        reader._show(reset=True)
        assert reader._idx != before
        reader._idx = before
        reader._show(reset=True)
        screenshot = os.environ.get("KOMICOVE_TRANSLATION_SCREENSHOT")
        if screenshot:
            dialog.lift()
            dialog.attributes("-topmost", True)
            for _ in range(30):
                root.update()
                sleep(.03)
            x, y = dialog.winfo_rootx(), dialog.winfo_rooty()
            ImageGrab.grab(bbox=(x, y, x + dialog.winfo_width(),
                                 y + dialog.winfo_height())).save(screenshot)
        engine = "real local" if os.environ.get("KOMICOVE_SMOKE_REAL_LOCAL") == "1" else "mock"
        print(f"GUI smoke: CBZ, OCR, {engine} translation, overlay, guided panels, rotation and navigation PASS")
        dialog.close()
    finally:
        reader._close()
        root.destroy()


if __name__ == "__main__":
    main()
