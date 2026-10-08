"""Reusable search data and sort orders for one library snapshot."""
from collections import OrderedDict
from pathlib import Path
import threading


class LibraryQuery:
    MAX_RESULTS = 8

    def __init__(self, paths, metadata, titles, sort):
        self.paths = tuple(paths)
        self.metadata = metadata
        self.titles = titles
        self.field_choices = {field: sorted({info.get(field, '') for info in metadata.values()} - {''})
                              for field in ('series', 'writer')}
        self._sort = sort
        self._orders = {}
        self._keys = {}
        self._results = OrderedDict()
        self._state = None
        self._statuses = {}
        self._continue = {}
        self._lock = threading.Lock()
        self._search = {path: tuple([Path(path).stem.lower()] + [
            str(metadata[path].get(field, '')).lower()
            for field in ('title', 'series', 'writer', 'publisher', 'genre')])
            for path in paths}

    def select(self, query, status, mode, fields, progress, favorites, manual, status_of):
        with self._lock:
            return self._select(query, status, mode, fields, progress, favorites, manual, status_of)

    def _select(self, query, status, mode, fields, progress, favorites, manual, status_of):
        state = (progress, frozenset(favorites), manual)
        if state != self._state:
            self._state = ({p: dict(v) if isinstance(v, dict) else v for p, v in progress.items()},
                           frozenset(favorites), dict(manual))
            self._results.clear()
            self._continue.clear()
            self._statuses.clear()
            self._orders.pop('recent', None)
        scope = tuple(fields.items())
        key = (query, status, mode, scope)
        if key in self._results:
            self._results.move_to_end(key)
            return self._results[key]
        if mode not in self._orders:
            self._orders[mode] = self._sort(self.paths, mode, progress,
                titles=self.titles, metadata=self.metadata, keys=self._keys)
        candidates = self._orders[mode]
        for previous, (matches, _) in reversed(self._results.items()):
            if previous[1:] == key[1:] and query.startswith(previous[0]):
                candidates = matches
                break
        if scope not in self._continue:
            recent = [(entry.get('ts', 0) if isinstance(entry, dict) else 0, p)
                      for p in self.paths if (entry := progress.get(p)) is not None
                      and all(not value or self.metadata[p].get(field, '') == value
                              for field, value in fields.items())]
            recent.sort(reverse=True)
            self._continue[scope] = [p for _, p in recent[:6]]
            if len(self._continue) > self.MAX_RESULTS:
                self._continue.pop(next(iter(self._continue)))
        result = []
        for path in candidates:
            if any(value and self.metadata[path].get(field, '') != value
                   for field, value in fields.items()):
                continue
            if query and not any(query in text for text in self._search[path]):
                continue
            if status == 'favorites' and path not in favorites:
                continue
            if status not in ('all', 'favorites'):
                if path not in self._statuses:
                    self._statuses[path] = status_of(path)
                if self._statuses[path] != status:
                    continue
            result.append(path)
        value = (result, self._continue[scope])
        self._results[key] = value
        while len(self._results) > self.MAX_RESULTS:
            self._results.popitem(last=False)
        return value
