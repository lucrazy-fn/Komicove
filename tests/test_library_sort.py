from komicove_app import library_widgets


def test_sort_comics_by_natural_title_and_reverse(monkeypatch):
    titles = {"a.cbz": "Volume 10", "b.cbz": "Volume 2", "c.cbz": "10th issue"}
    monkeypatch.setattr(library_widgets, "comic_display_title", lambda path: titles[path])

    assert library_widgets.sort_comics(titles, "title") == ["c.cbz", "b.cbz", "a.cbz"]
    assert library_widgets.sort_comics(titles, "title_desc") == ["a.cbz", "b.cbz", "c.cbz"]


def test_sort_comics_by_series_then_title(monkeypatch):
    titles = {"a.cbz": "Volume 10", "b.cbz": "Volume 2", "c.cbz": "Volume 1"}
    series = {"a.cbz": "Beta", "b.cbz": "Beta", "c.cbz": "Alpha"}
    monkeypatch.setattr(library_widgets, "comic_display_title", lambda path: titles[path])
    monkeypatch.setattr(library_widgets, "get_comic_info", lambda path: {"series": series[path]})

    assert library_widgets.sort_comics(titles, "series") == ["c.cbz", "b.cbz", "a.cbz"]


def test_sort_comics_by_recent_activity(monkeypatch):
    modified = {"a.cbz": 10, "b.cbz": 20}
    monkeypatch.setattr(library_widgets.os.path, "getmtime", lambda path: modified[path])

    assert library_widgets.sort_comics(modified, "recent", {"a.cbz": {"ts": 30}}) == ["a.cbz", "b.cbz"]


def test_reusing_natural_keys_preserves_ties_and_avoids_retokenizing(monkeypatch):
    titles = {'a': 'Issue 2', 'b': 'Issue 2', 'c': 'Issue 10'}
    keys = {}
    assert library_widgets.sort_comics(titles, 'title', titles=titles, keys=keys) == ['a', 'b', 'c']
    monkeypatch.setattr(library_widgets.re, 'split', lambda *args: (_ for _ in ()).throw(AssertionError('Repeated key processing')))
    assert library_widgets.sort_comics(titles, 'title_desc', titles=titles, keys=keys) == ['c', 'a', 'b']
