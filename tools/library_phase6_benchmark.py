"""Isolated desktop UI benchmark. Run each size in a fresh process."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def resident_bytes():
    if os.name == 'nt':
        class Counters(ctypes.Structure):
            _fields_ = [('cb', ctypes.c_ulong), ('faults', ctypes.c_ulong)] + [
                (name, ctypes.c_size_t) for name in ('peak', 'working', 'pool_peak',
                'pool', 'nonpaged_peak', 'nonpaged', 'pagefile', 'pagefile_peak')]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        process = ctypes.windll.kernel32.GetCurrentProcess
        process.restype = ctypes.c_void_p
        ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(process()),
                                                ctypes.byref(counters), counters.cb)
        return counters.working
    return None


def run(size, soak_seconds=0):
    with tempfile.TemporaryDirectory(prefix='komicove-phase6-') as directory:
        os.environ['KOMICOVE_APPDATA_DIR'] = directory
        os.environ['KOMICOVE_GUIDED_AI'] = '0'
        from PIL import Image
        from komicove_app import library_views as views, library_widgets as widgets
        from komicove_app.storage import save_prefs, save_progress, toggle_favorite
        from komicove_app.design.icons import clear_icon_cache
        save_prefs(lang='pt', book_sort='title')
        views.LibraryWindow._show_auth = lambda self: None
        # Metadata and thumbnails are deterministic, with no disk/archive latency.
        widgets.read_comic_info = lambda path: {'title': Path(path).stem,
            'series': 'Series ' + str(int(Path(path).stem.split()[-1]) % 20),
            'writer': 'Author', 'page_count': '24'}
        views.CoverLoader._load = lambda self, path: Image.new('RGB', (136, 188), 'red')
        paths = [str(Path(directory, f'Issue {number}.cbz')) for number in range(size)]
        # Exercise manual/status/favorite state without touching real data.
        toggle_favorite(paths[-1])
        root = views.LibraryWindow()
        root._folder_watcher.close()
        root._cover_loader = views.CoverLoader(root, root._capa_cache)
        root._scan = lambda: paths
        root.geometry('1280x860')
        root.deiconify()
        root._build_shell()
        root.update()
        errors = []
        root.report_callback_exception = lambda *error: errors.append(str(error))

        def measure(action):
            start = time.perf_counter()
            action()
            deadline = start + 90
            while root._library_preparing and time.perf_counter() < deadline:
                root.update()
                time.sleep(.001)
            root.update()
            assert not root._library_preparing and not errors, errors
            return (time.perf_counter() - start) * 1000

        tracemalloc.start()
        first = measure(root._refresh_library)
        searches = []
        for query in ('Issue 9', 'Issue 99', 'Issue 999', 'Author', '') * 3:
            root._search_query = query
            searches.append(measure(root._populate_library_grid))
        sorts = []
        for mode in ('title_desc', 'series', 'recent', 'title') * 3:
            root._book_sort = mode
            sorts.append(measure(root._populate_library_grid))
        root._status_filter = 'favorites'
        favorite = measure(root._populate_library_grid)
        assert root._library_grid.paths == [paths[-1]]
        root._status_filter = 'all'
        measure(root._populate_library_grid)
        before = resident_bytes()
        max_cards = 0
        for position in [0, .25, .5, .75, 1] * 6:
            root._lib_canvas.yview_moveto(position)
            root.update()
            max_cards = max(max_cards, len(root._card_map))
            time.sleep(.005)
        after = resident_bytes()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        result = dict(size=size, first_ms=first, search_median_ms=statistics.median(searches),
            search_max_ms=max(searches), sort_median_ms=statistics.median(sorts),
            favorites_ms=favorite, python_current_bytes=current, python_peak_bytes=peak,
            rss_before_scroll_bytes=before, rss_after_scroll_bytes=after,
            max_mounted_cards=max_cards, cover_cache_items=len(root._capa_cache))
        if soak_seconds:
            samples, heartbeat, queries = [], [], []
            start = time.perf_counter()
            deadline = [start + .016]
            running = [True]

            def beat():
                now = time.perf_counter()
                heartbeat.append(max(0, now - deadline[0]) * 1000)
                deadline[0] = now + .016
                if running[0]: root.after(16, beat)

            root.after(16, beat)
            last_sample, last_cpu, next_query, next_scroll, step = start, time.process_time(), start + 10, start, 0
            while time.perf_counter() - start < soak_seconds:
                now = time.perf_counter()
                if now >= next_scroll:
                    root._lib_canvas.yview_moveto((step % 21) / 20)
                    step += 1
                    next_scroll = now + .1
                root.update()
                now = time.perf_counter()
                if now >= next_query:
                    root._search_query = ('Issue 99', 'Author', '')[len(queries) % 3]
                    queries.append(measure(root._populate_library_grid))
                    next_query = now + 10
                if now - last_sample >= 1:
                    cpu = time.process_time()
                    assert len(root._card_map) < 100
                    assert len(root._capa_cache) <= root._cover_loader.MAX_CACHED
                    samples.append(dict(seconds=now-start, rss_bytes=resident_bytes(),
                        process_cpu_percent_one_core=(cpu-last_cpu)/(now-last_sample)*100,
                        mounted_cards=len(root._card_map), cache_items=len(root._capa_cache)))
                    last_sample, last_cpu = now, cpu
                time.sleep(.001)
            running[0] = False
            ordered = sorted(heartbeat)
            result['soak'] = dict(duration_seconds=soak_seconds, cpu_logical_cores=os.cpu_count(),
                workload='10 scroll jumps/s; query every 10s; synthetic worker covers; tracemalloc disabled during soak',
                samples=samples, heartbeat_delay_p95_ms=ordered[int(len(ordered)*.95)],
                heartbeat_delay_max_ms=max(ordered), search_ms=queries,
                rss_start_bytes=samples[0]['rss_bytes'], rss_end_bytes=samples[-1]['rss_bytes'],
                rss_peak_bytes=max(s['rss_bytes'] for s in samples),
                process_cpu_mean_percent_one_core=statistics.mean(s['process_cpu_percent_one_core'] for s in samples))
            assert not errors, errors
        root.destroy()
        clear_icon_cache()
        widgets._COMIC_INFO_CACHE.clear()
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--size', type=int, choices=[1000, 5000, 10000], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, help='Optional isolated baseline source tree')
    parser.add_argument('--soak-seconds', type=int, default=0)
    args = parser.parse_args()
    if args.source_root is not None:
        sys.path.insert(0, str(args.source_root.resolve()))
    result = dict(platform=platform.platform(), python=sys.version, viewport='1280x860',
                  fixture='synthetic metadata; RGB 136x188 covers; temporary AppData',
                  repetitions='15 searches, 12 sorts, 30 scroll jumps', result=run(args.size, args.soak_seconds))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in result['result'].items() if key != 'soak'}))
