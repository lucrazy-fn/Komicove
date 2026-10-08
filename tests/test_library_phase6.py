from pathlib import Path

import pytest

from komicove_app.library_query import LibraryQuery
from komicove_app.library_widgets import sort_comics


@pytest.mark.parametrize('size', [1000, 5000, 10000])
def test_search_filter_sort_and_bounded_result_cache(size):
    paths = [f'Issue {i}.cbz' for i in range(size)]
    titles = {p: Path(p).stem for p in paths}
    metadata = {p: {'title': titles[p], 'series': f'Series {i % 20}',
                    'writer': 'Author', 'genre': 'Adventure'} for i, p in enumerate(paths)}
    calls = []

    def sort(*args, **kwargs):
        calls.append(args[1])
        return sort_comics(*args, **kwargs)

    index = LibraryQuery(paths, metadata, titles, sort)
    assert index.field_choices['writer'] == ['Author']
    assert set(index.field_choices['series']) == {f'Series {i}' for i in range(20)}
    fields = {'series': '', 'writer': ''}
    progress = {paths[2]: {'page': 3, 'ts': 10}, paths[4]: 23}
    manual = {paths[4]: 'done'}
    favorites = {paths[7], paths[-1]}
    status_calls = []

    def status(p):
        status_calls.append(p)
        return 'done' if p in manual else 'reading' if p in progress else 'unread'

    def select(q='', s='all', mode='title'):
        return index.select(q, s, mode, fields, progress, favorites, manual, status)[0]

    assert select() == paths
    assert select(mode='title_desc') == paths[::-1]
    assert select('issue 99') == [p for p in paths if 'issue 99' in p.lower()]
    assert select('issue 999') == [p for p in paths if 'issue 999' in p.lower()]
    assert select('adventure') == paths
    assert select(s='favorites') == [paths[7], paths[-1]]
    assert select(s='done') == [paths[4]]
    assert select(s='reading') == [paths[2]]
    assert len(status_calls) == size
    fields['series'] = 'Series 7'
    assert select() == paths[7::20]
    assert select(mode='series') == sort_comics(paths[7::20], 'series', titles=titles, metadata=metadata)
    for i in range(20):
        select(str(i))
    assert len(index._results) <= 8 and len(index._orders) <= 4
    assert calls.count('title') == 1
    fields['series'] = ''
    favorites.clear()
    assert select(s='favorites') == []
    progress[paths[2]]['page'] = 10
    manual[paths[2]] = 'done'
    assert select(s='done') == [paths[2], paths[4]]


def test_continue_keeps_metadata_scope_and_legacy_progress():
    paths = ['a', 'b', 'c']
    index = LibraryQuery(paths, {'a': {'series': 'One'}, 'b': {'series': 'Two'},
                               'c': {'series': 'One'}}, dict(zip(paths, paths)), sort_comics)
    matched, recent = index.select('missing', 'favorites', 'title', {'series': 'One'},
        {'a': 2, 'b': {'page': 5, 'ts': 50}, 'c': {'page': 9, 'ts': 20}}, set(), {}, lambda p: 'reading')
    assert matched == [] and recent == ['c', 'a']


def test_tooltip_reuses_snapshot_without_metadata_io(monkeypatch):
    from types import SimpleNamespace
    from komicove_app import library_widgets
    scheduled = []
    root = SimpleNamespace(_library_query=SimpleNamespace(metadata={'book': {'title': 'Current'}}),
                           after=lambda *args: scheduled.append(args) or 'tooltip')
    monkeypatch.setattr(library_widgets, 'get_comic_info',
                        lambda *args: pytest.fail('Tooltip reread metadata on UI'))
    tooltip = library_widgets.MetaTooltip(root)
    tooltip.show(object(), 'book')
    assert scheduled[0][0] == 600 and tooltip._after == 'tooltip'
