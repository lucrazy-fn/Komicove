"""Open Phase 1 with disposable guest data for visual comparison.

No real Komicove account, library, or preferences are used. Close the window
to remove the temporary profile.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

from PIL import ImageGrab


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    with tempfile.TemporaryDirectory(prefix="komicove-redesign-preview-") as profile:
        os.environ["KOMICOVE_APPDATA_DIR"] = profile
        from komicove_app import library_views, runtime
        from komicove_app.storage import (
            record_page_read, record_reading_time, save_prefs, save_progress,
        )

        # Sample accounts must never contact the configured production API.
        library_views.api_client.sync_library_state = lambda *_args: []

        save_prefs(lang="pt")
        if ("--populated" in sys.argv or "--collections" in sys.argv
                or "--statistics-sample" in sys.argv):
            comics = Path(profile, "comics")
            comics.mkdir()
            sample_cover = Path(__file__).resolve().parent.parent / "komicovelogo.png"
            if "--collections" in sys.argv:
                folders = [(comics / "Arquivo Noir", f"Arquivo Noir #{number:02d}.cbz")
                           for number in range(1, 5)]
                folders += [(comics, f"Cidade Eclipse #{number:02d}.cbz")
                            for number in range(1, 5)]
            else:
                folders = [(comics, f"HQ de teste {number:02d}.cbz")
                           for number in range(1, 9)]
            for number, (directory, filename) in enumerate(folders, 1):
                directory.mkdir(exist_ok=True)
                comic = directory / filename
                with ZipFile(comic, "w") as archive:
                    archive.write(sample_cover, "001.png")
                if not runtime.extract_cover_only(str(comic)):
                    raise RuntimeError(f"Could not extract test cover: {comic.name}")
                if number <= 2:
                    save_progress(str(comic), 0)
                if "--statistics-sample" in sys.argv and number <= 5:
                    for page in range(number * 3):
                        record_page_read(f"preview-book-{number}", page,
                                         total=number * 3 if number <= 2 else 100)
                    record_reading_time(f"preview-book-{number}", number * 1700)
            runtime.save_library_config(str(comics))
        with patch.object(library_views, "AuthWindow", lambda _parent, callback: callback(None)):
            with patch.object(library_views.updater, "check", return_value=None):
                app = library_views.LibraryWindow()
                app.geometry("1672x941+0+0")
                if "--collections" in sys.argv or "--collections-empty" in sys.argv:
                    def show_collections():
                        app._active_tab = "collections"
                        app._build_shell()
                        app._show_collections()
                    app.after(800, show_collections)
                if "--downloads-sample" in sys.argv:
                    from komicove_app.downloads import DownloadTask, _store_cover, manager
                    examples = [
                        ("HQ de teste 01", "downloading", 6, 10),
                        ("HQ de teste 02", "completed", 10, 10),
                        ("HQ de teste 03", "failed", 2, 10),
                    ]
                    preview_art = [
                        Path(__file__).resolve().parent.parent / "komicovelogo.png",
                        Path(__file__).resolve().parent.parent / "assets_redesign/banners/library_noir.png",
                        Path(__file__).resolve().parent.parent / "assets_redesign/empty_states/library_desktop.png",
                    ]
                    for number, (title, status, received, total) in enumerate(examples, 1):
                        key = f"preview-{number}"
                        task = DownloadTask(
                            key, title, "", str(Path(profile, f"test-{number}.cbz")),
                            None, status=status, received=received, total=total,
                        )
                        manager.tasks[key] = task
                        _store_cover(task, preview_art[number - 1].read_bytes())
                    app.after(800, app._open_downloads)
                if "--downloads-empty" in sys.argv:
                    app.after(800, app._open_downloads)
                if "--statistics-sample" in sys.argv:
                    app.after(800, app._open_statistics)
                if "--discover-sample" in sys.argv or "--submissions-sample" in sys.argv:
                    sample_cover = (Path(__file__).resolve().parent.parent
                                    / "assets_redesign/placeholders/comic_cover.png").read_bytes()
                    examples = [
                        {"publication_id": f"preview-{number}",
                         "title": f"HQ de exemplo {number:02d}",
                         "author": f"Autor {number:02d}", "has_file": True,
                         "status": "approved"}
                        for number in range(1, 9)
                    ]
                    library_views.api_client.discovery = lambda: examples
                    library_views.api_client.my_publications = lambda _token: [
                        {**item, "status": ("approved", "pending_review", "rejected")[index % 3]}
                        for index, item in enumerate(examples)
                    ]
                    library_views.api_client.publication_cover = lambda *_args: sample_cover
                    if "--submissions-sample" in sys.argv:
                        def show_submissions():
                            app.current_user = SimpleNamespace(
                                token="preview", username="Preview", display_name="Teste",
                                role="user")
                            app._open_my_publications()
                        app.after(800, show_submissions)
                    else:
                        app.after(800, app._open_discovery)
                if "--notifications-sample" in sys.argv or "--notifications-empty" in sys.argv:
                    notifications = [
                        {"id": f"preview-{number}",
                         "title": "Seu envio foi analisado" if number % 2 else "Conta suspensa",
                         "message": (f"“HQ de exemplo {number:02d}” foi aprovado."
                                     if number % 2 else "Suspensa por 1 hora(s). Motivo: Teste."),
                         "kind": "publication_decision" if number % 2 else "punishment",
                         "read_at": None if number <= 3 else "2026-09-25T12:00:00+00:00",
                         "created_at": f"2026-09-25T{10+number:02d}:30:00+00:00"}
                        for number in range(1, 7)
                    ] if "--notifications-sample" in sys.argv else []
                    library_views.api_client.notifications = lambda _token: notifications
                    library_views.api_client.mark_notification_read = lambda *_args: None
                    def show_notifications():
                        app.current_user = SimpleNamespace(
                            token="preview", username="Preview", display_name="Teste",
                            role="user")
                        app._open_notifications()
                    app.after(800, show_notifications)
                if "--profile-sample" in sys.argv:
                    library_views.api_client.get_profile = lambda _token: {
                        "username": "leitor_teste",
                        "display_name": "Leitor de teste",
                        "email": "leitor@example.invalid",
                        "role": "owner",
                        "email_verified": True,
                        "totp_enabled": True,
                        "bio": "Leitor apaixonado por quadrinhos, histórias sombrias e mundos extraordinários.",
                    }
                    library_views.api_client.active_sessions = lambda _token: [
                        {"id": "current", "device_name": "Komicove Desktop (Windows)",
                         "current": True},
                        {"id": "android", "device_name": "Android", "current": False},
                    ]
                    library_views.api_client.revoke_session = lambda *_args: None
                    def show_profile():
                        app.current_user = SimpleNamespace(
                            token="preview", username="leitor_teste",
                            display_name="Leitor de teste", email="leitor@example.invalid",
                            role="owner",
                        )
                        app._open_profile()
                    app.after(1600, show_profile)
                if "--moderation-sample" in sys.argv:
                    sample_cover = (Path(__file__).resolve().parent.parent
                                    / "assets_redesign/placeholders/comic_cover.png").read_bytes()
                    moderation_items = [
                        {
                            "record_id": f"record-{number}",
                            "publication_id": f"publication-{number}",
                            "title": f"Obra para revisar {number:02d}",
                            "author": f"Autor {number:02d}",
                            "uploader_username": f"leitor{number:02d}",
                            "status": ("pending_review", "approved", "rejected")[number % 3],
                            "risk_level": "medium", "confidence": 0.7,
                            "has_file": True, "original_filename": f"obra-{number}.cbz",
                        }
                        for number in range(1, 7)
                    ]
                    library_views.api_client.moderation_queue = lambda *_args, **_kwargs: moderation_items
                    library_views.api_client.moderation_cover = lambda *_args: sample_cover
                    def show_moderation():
                        app.current_user = SimpleNamespace(
                            token="preview", username="Moderador", display_name="Moderador",
                            role="owner")
                        app._open_moderation()
                    app.after(800, show_moderation)
                if "--capture" in sys.argv:
                    capture_index = sys.argv.index("--capture") + 1
                    capture_path = Path(sys.argv[capture_index]).resolve()
                    def capture_and_close():
                        app.update_idletasks()
                        x, y = app.winfo_rootx(), app.winfo_rooty()
                        width, height = app.winfo_width(), app.winfo_height()
                        capture_path.parent.mkdir(parents=True, exist_ok=True)
                        ImageGrab.grab((x, y, x + width, y + height)).save(capture_path)
                        app.destroy()
                    app.after(2400, capture_and_close)
                if "--report-empty-size" in sys.argv:
                    def report_empty_size():
                        photo = (getattr(app, "_empty_collection_illustration", None)
                                 or getattr(app, "_empty_illustration", None))
                        print(f"empty_art={photo.width()}x{photo.height()}" if photo else "empty_art=none")
                        app.destroy()
                    app.after(1600, report_empty_size)
                app.mainloop()


if __name__ == "__main__":
    main()
