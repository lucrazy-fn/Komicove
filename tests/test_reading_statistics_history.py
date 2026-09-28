import json
from datetime import date

from komicove_app import storage
from komicove_app.statistics_views import statistics_model


def test_reading_history_is_real_and_does_not_double_count_repaints(tmp_path, monkeypatch):
    stats_file = tmp_path / "reading_stats.json"
    monkeypatch.setattr(storage, "STATS_FILE", str(stats_file))
    timestamp = 1_798_761_600  # 2027-01-01 UTC

    storage.record_page_read(
        "book-a", 4, 10, path=str(tmp_path / "comic.cbz"),
        metadata={"title": "Comic", "genre": "Crime, Noir"}, timestamp=timestamp,
    )
    storage.record_page_read("book-a", 4, 10, timestamp=timestamp)
    storage.record_page_read("book-a", 5, 10, timestamp=timestamp)
    storage.record_reading_time("book-a", 125, timestamp=timestamp)

    raw = json.loads(stats_file.read_text(encoding="utf-8"))
    day = next(iter(raw["daily"].values()))
    assert day["pages"] == 2
    assert day["seconds"] == 125
    assert day["sessions"] == 1
    totals = storage.personal_statistics()
    assert totals["pages"] == 2
    assert totals["seconds"] == 125
    assert totals["genres"] == {"Crime": 2, "Noir": 2}


def test_statistics_model_builds_daily_weekly_and_streak_from_real_dates():
    stats = {
        "started": 1, "completed": 0, "pages": 3, "seconds": 60,
        "sessions": 2,
        "daily": {
            "2026-09-25": {"pages": 1, "seconds": 20, "sessions": 1},
            "2026-09-26": {"pages": 2, "seconds": 40, "sessions": 1},
        },
        "genres": {"Noir": 3},
    }
    model = statistics_model(stats, {}, today=date(2026, 9, 27))
    assert [item["pages"] for item in model["daily"][-3:]] == [1, 2, 0]
    assert model["weekly"][-1]["pages"] == 3
    assert model["streak"] == 2
    assert model["sessions"] == 2
    assert model["genres"] == [("Noir", 3)]
