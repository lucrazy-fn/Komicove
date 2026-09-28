"""Capture the redesigned reader with disposable in-memory pages."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageGrab


class PreviewLoader:
    def __init__(self):
        self.pages = [self._page(index) for index in range(6)]
        self.count = len(self.pages)

    @staticmethod
    def _page(index):
        image = Image.new("RGB", (820, 1180), "#e9e6df")
        draw = ImageDraw.Draw(image)
        draw.rectangle((28, 28, 792, 1152), outline="#131821", width=8)
        draw.rectangle((52, 52, 768, 385), fill="#161b23", outline="#e12835", width=5)
        draw.rectangle((52, 410, 382, 820), fill="#242d38", outline="#10141b", width=5)
        draw.rectangle((408, 410, 768, 820), fill="#790f1d", outline="#10141b", width=5)
        draw.rectangle((52, 846, 768, 1125), fill="#11161d", outline="#e12835", width=5)
        draw.text((82, 82), f"KOMICOVE  {index + 1}", fill="#ffffff")
        draw.ellipse((510, 125, 700, 315), fill="#e12835")
        return image

    def get_pil(self, index): return self.pages[index].copy()
    def get_thumbnail_pil(self, index, width, height):
        image = self.pages[index].copy(); image.thumbnail((width, height)); return image
    def prefetch(self, _index): return None
    def close(self): return None


def main():
    root_dir = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root_dir))
    with tempfile.TemporaryDirectory(prefix="komicove-reader-preview-") as data_dir:
        os.environ["KOMICOVE_APPDATA_DIR"] = data_dir
        import tkinter as tk
        from komicove_app.reader_views import ReaderWindow

        root = tk.Tk(); root.withdraw()
        reader = ReaderWindow(root, str(Path(data_dir, "preview.cbz")), PreviewLoader())
        reader.state("zoomed")
        reader.lift()
        reader.attributes("-topmost", True)
        reader.after(500, lambda: reader.attributes("-topmost", False))
        if "--shortcuts" in sys.argv:
            reader.after(800, reader._show_shortcuts)
        if "--editor" in sys.argv:
            reader.after(800, reader._edit_panels)
        if "--preferences" in sys.argv:
            reader.after(800, reader._reader_preferences)
        if "--pages" in sys.argv:
            reader.after(800, reader._show_page_picker)
        if "--bookmarks" in sys.argv:
            reader._toggle_bookmark()
            reader.after(800, reader._show_bookmarks)
        capture = None
        if "--capture" in sys.argv:
            capture = Path(sys.argv[sys.argv.index("--capture") + 1]).resolve()

        def finish():
            reader.update_idletasks()
            target = reader
            children = [child for child in reader.winfo_children() if isinstance(child, tk.Toplevel)]
            if children:
                target = children[-1]
            x, y = target.winfo_rootx(), target.winfo_rooty()
            width, height = target.winfo_width(), target.winfo_height()
            if capture:
                capture.parent.mkdir(parents=True, exist_ok=True)
                ImageGrab.grab((x, y, x + width, y + height)).save(capture)
            try: reader.destroy()
            except tk.TclError: pass
            root.destroy()

        reader.after(2800, finish)
        root.mainloop()


if __name__ == "__main__":
    main()
