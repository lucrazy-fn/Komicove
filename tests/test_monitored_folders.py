import io
import shutil
import zipfile
from pathlib import Path

from PIL import Image
from komicove_app.archive import SmartPageLoader
from komicove_app.monitored_folders import FolderIndex, FolderWatcher


def comic(path, color="red", title="one"):
    data = io.BytesIO()
    Image.new("RGB", (16, 24), color).save(data, format="PNG")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(zipfile.ZipInfo("001.jpg", (2020, 1, 1, 0, 0, 0)), data.getvalue())
        archive.writestr(zipfile.ZipInfo("002.jpg", (2020, 1, 1, 0, 0, 0)), data.getvalue())
        archive.writestr(zipfile.ZipInfo("ComicInfo.xml", (2020, 1, 1, 0, 0, 0)), f"<ComicInfo><Title>{title}</Title></ComicInfo>")


def index_for(tmp_path):
    root = tmp_path / "library"
    root.mkdir()
    clock = [100.0]
    index = FolderIndex(tmp_path / "index.json", str(root), clock=lambda: clock[0])
    return index, root, clock


def settle(index, clock):
    index.rescan()
    clock[0] += 4
    return index.rescan()


def test_large_folder_duplicates_are_one_result_and_persistent(tmp_path):
    index, root, clock = index_for(tmp_path)
    for number in range(300):
        comic(root / f"comic-{number}.cbz", title=str(number))
    result = settle(index, clock)
    assert result["added"] == 300
    assert len(index.paths()) == 300
    index.add(str(root))
    assert len(index.snapshot()["folders"]) == 1
    result = index.rescan()
    assert result["added"] == 0 and result["duplicates"] == 300
    restored = FolderIndex(tmp_path / "index.json", clock=lambda: clock[0])
    assert restored.paths() == index.paths()
    # Unchanged rescans never reopen/decompress/hash the archive contents.
    restored.validator = lambda path: (_ for _ in ()).throw(AssertionError(path))
    assert restored.rescan()["added"] == 0


def test_new_removed_renamed_and_moved_keep_content_identity(tmp_path):
    index, root, clock = index_for(tmp_path)
    original = root / "first.cbz"
    comic(original)
    assert settle(index, clock)["added"] == 1
    identity = next(iter(index.snapshot()["books"]))
    other = tmp_path / "other"
    other.mkdir()
    index.add(str(other))
    destination = other / "renamed.cbz"
    original.rename(destination)
    result = settle(index, clock)
    assert result["added"] == 0
    assert result["moves"] == [(str(original), str(destination))]
    assert next(iter(index.snapshot()["books"])) == identity
    destination.unlink()
    index.rescan()
    assert not index.snapshot()["books"][identity]["available"]
    assert index.paths() == [str(destination)]
    comic(destination)
    assert settle(index, clock)["added"] == 0
    assert index.snapshot()["books"][identity]["available"]


def test_distinct_archives_with_same_internal_names_do_not_conflict(tmp_path):
    index, root, clock = index_for(tmp_path)
    first, second = root / "a.cbz", root / "b.cbz"
    comic(first, "red")
    comic(second, "blue")
    shutil.copyfile(first, root / "duplicate.cbz")
    assert settle(index, clock)["added"] == 2
    red, blue = SmartPageLoader(str(first)), SmartPageLoader(str(second))
    try:
        assert red.get_pil(0).getpixel((0, 0))[:3] == (255, 0, 0)
        assert blue.get_pil(0).getpixel((0, 0))[:3] == (0, 0, 255)
        assert red.get_pil(1).getpixel((0, 0)) != blue.get_pil(1).getpixel((0, 0))
    finally:
        red.close()
        blue.close()


def test_copy_in_progress_corrupt_and_oversized_are_not_imported(tmp_path):
    index, root, clock = index_for(tmp_path)
    path = root / "copy.cbz"
    path.write_bytes(b"PK")
    assert settle(index, clock)["added"] == 0
    comic(path)
    assert index.rescan()["added"] == 0
    clock[0] += 4
    assert index.rescan()["added"] == 1
    index.MAX_BYTES = 1
    comic(root / "too-large.cbz", "blue")
    assert settle(index, clock)["added"] == 0


def test_unavailable_root_and_paused_removed_registry_preserve_books(tmp_path):
    index, root, clock = index_for(tmp_path)
    comic(root / "a.cbz")
    settle(index, clock)
    key = index.key(root)
    index.configure(key, enabled=False, name="Comics")
    assert index.rescan()["added"] == 0
    index.configure(key, enabled=True)
    offline = root.with_name("offline")
    root.rename(offline)
    index.rescan()
    assert index.snapshot()["folders"][key]["status"] == "unavailable"
    assert len(index.paths()) == 1
    assert not next(iter(index.snapshot()["books"].values()))["available"]
    offline.rename(root)
    assert index.rescan()["added"] == 0
    assert next(iter(index.snapshot()["books"].values()))["available"]
    index.configure(key, remove=True)
    assert len(index.paths()) == 1
    assert index.paths(visible_only=True) == []
    index.rescan()
    restored = FolderIndex(index.filename, str(root))
    assert restored.paths(visible_only=True) == []
    assert restored.snapshot()["folders"] == {}
    restored.add(str(root))
    assert len(restored.paths(visible_only=True)) == 1
    assert restored.rescan()["added"] == 0
    assert (root / "a.cbz").is_file()


def test_disabled_folder_skips_new_files_until_enabled(tmp_path):
    index, root, clock = index_for(tmp_path)
    comic(root / "first.cbz")
    settle(index, clock)
    key = index.key(root)
    index.configure(key, enabled=False)
    comic(root / "new.cbz", "blue")
    assert settle(index, clock)["added"] == 0
    assert len(index.paths()) == 1
    assert not FolderIndex(index.filename).snapshot()["folders"][key]["enabled"]
    assert index.paths(visible_only=True) == []
    index.configure(key, enabled=True)
    assert settle(index, clock)["added"] == 1
    assert len(index.paths()) == 2
    assert len(index.paths(visible_only=True)) == 2


def test_disabling_one_of_multiple_source_folders_keeps_other_source_visible(tmp_path):
    index, root, clock = index_for(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    index.add(other)
    comic(root / "first.cbz")
    shutil.copyfile(root / "first.cbz", other / "copy.cbz")
    settle(index, clock)
    index.configure(index.key(root), enabled=False)
    assert len(index.paths(visible_only=True)) == 1
    index.configure(index.key(other), enabled=False)
    assert index.paths(visible_only=True) == []
    assert len(index.paths()) == 1
    restored = FolderIndex(index.filename)
    assert restored.paths(visible_only=True) == []
    restored.configure(index.key(root), enabled=True)
    assert len(restored.paths(visible_only=True)) == 1


def test_polling_watcher_detects_changes_and_stops(tmp_path):
    index, root, clock = index_for(tmp_path)
    watcher = FolderWatcher(index, interval=.02)
    try:
        watcher.events.get(timeout=2)
        comic(root / "new.cbz")
        watcher.refresh()
        assert watcher.events.get(timeout=2)["waiting"]
        clock[0] += 4
        watcher.refresh()
        results = [watcher.events.get(timeout=2)]
        while not results[-1]["added"]:
            results.append(watcher.events.get(timeout=2))
        assert results[-1]["added"] == 1
    finally:
        watcher.close()
        watcher.thread.join(2)
    assert not watcher.thread.is_alive()


def test_removing_folder_hides_exclusive_books_and_keeps_other_sources(tmp_path):
    index, root, clock = index_for(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    index.add(other)
    comic(root / "exclusive.cbz", "blue")
    comic(root / "shared.cbz")
    shutil.copyfile(root / "shared.cbz", other / "copy.cbz")
    comic(other / "other.cbz", "green")
    settle(index, clock)
    shared = next(book["path"] for book in index.snapshot()["books"].values()
                  if len(book["sources"]) == 2)
    index.configure(index.key(root), remove=True)
    assert set(index.paths(visible_only=True)) == {shared, str(other / "other.cbz")}
    index.rescan()
    restored = FolderIndex(index.filename)
    assert len(restored.paths(visible_only=True)) == 2
    restored.configure(index.key(other), remove=True)
    assert restored.paths(visible_only=True) == []
    assert len(restored.paths()) == 3
    assert (root / "exclusive.cbz").is_file()
    assert (other / "copy.cbz").is_file()


def test_removed_folder_keeps_standalone_books_visible(tmp_path):
    index, root, clock = index_for(tmp_path)
    comic(root / "folder.cbz")
    settle(index, clock)
    index.data["books"]["standalone"] = {"path": "standalone.cbz", "sources": {}}
    index.configure(index.key(root), remove=True)
    assert FolderIndex(index.filename).paths(visible_only=True) == ["standalone.cbz"]


def test_move_after_removing_old_folder_uses_new_source_path(tmp_path):
    index, root, clock = index_for(tmp_path)
    original = root / "comic.cbz"
    comic(original)
    settle(index, clock)
    identity = next(iter(index.snapshot()["books"]))
    index.configure(index.key(root), remove=True)
    other = tmp_path / "new-folder"
    other.mkdir()
    destination = other / original.name
    original.rename(destination)
    index.add(other)
    result = settle(index, clock)
    assert result["added"] == 0
    assert result["moves"] == [(str(original), str(destination))]
    assert index.paths(visible_only=True) == [str(destination)]
    assert FolderIndex(index.filename).paths(visible_only=True) == [str(destination)]
    assert next(iter(index.snapshot()["books"])) == identity
    assert index.snapshot()["books"][identity]["available"]


def test_enabled_source_is_preferred_over_disabled_folder(tmp_path):
    index, root, clock = index_for(tmp_path)
    original = root / "comic.cbz"
    comic(original)
    settle(index, clock)
    index.configure(index.key(root), enabled=False)
    other = tmp_path / "other"
    other.mkdir()
    destination = other / "copy.cbz"
    shutil.copyfile(original, destination)
    index.add(other)
    result = settle(index, clock)
    assert result["moves"] == [(str(original), str(destination))]
    assert index.paths(visible_only=True) == [str(destination)]


def test_overlapping_roots_keep_membership_without_rehashing(tmp_path):
    index, root, clock = index_for(tmp_path)
    nested = root / "nested"
    nested.mkdir()
    index.add(str(nested))
    comic(nested / "comic.cbz")
    validations = []
    original = index.validator
    def validate(path):
        validations.append(path)
        original(path)
    index.validator = validate
    assert settle(index, clock)["added"] == 1
    assert len(validations) == 1
    assert [folder["count"] for folder in index.snapshot()["folders"].values()] == [1, 1]
    index.rescan()
    assert len(validations) == 1
    assert len(next(iter(index.snapshot()["books"].values()))["sources"]) == 2


def test_temporary_file_lock_is_retried_after_copy_finishes(tmp_path):
    index, root, clock = index_for(tmp_path)
    comic(root / "locked.cbz")
    original = index.validator
    attempts = []
    def validate(path):
        attempts.append(path)
        if len(attempts) == 1:
            raise PermissionError("Writer still holds this file")
        original(path)
    index.validator = validate
    assert settle(index, clock)["added"] == 0
    assert index.rescan()["added"] == 1


def test_path_migration_preserves_reading_data_and_existing_destination(tmp_path, monkeypatch):
    from komicove_app import storage
    monkeypatch.setattr(storage, "APPDATA_DIR", str(tmp_path))
    for name in ("PROGRESS_FILE", "BOOKMARKS_FILE", "FAVORITES_FILE", "MANUAL_STATUS_FILE", "STATS_FILE"):
        monkeypatch.setattr(storage, name, str(tmp_path / (name + ".json")))
    monkeypatch.setattr(storage, "_progress_cache", {})
    monkeypatch.setattr(storage, "_progress_dirty", False)
    monkeypatch.setattr(storage, "_progress_timer", None)
    monkeypatch.setattr(storage, "_change_listeners", [])
    old, new = "original.cbz", "renamed.cbz"
    storage.save_progress(old, 7)
    storage.toggle_bookmark(old, 4)
    storage.toggle_favorite(old)
    storage.set_manual_status(old, "reading")
    storage.preserve_renamed_book(old, new)
    assert storage.get_progress_page(old) == storage.get_progress_page(new) == 7
    assert storage.get_bookmarks(old) == storage.get_bookmarks(new) == [4]
    assert storage.is_favorite(old) and storage.is_favorite(new)
    assert storage.load_manual_status()[new] == "reading"
    storage.save_progress(new, 12)
    storage.preserve_renamed_book(old, new)
    assert storage.get_progress_page(new) == 12
    storage.flush_progress()
