from komicove_app.statistics_views import statistics_model


def test_statistics_model_uses_real_counters_and_recent_progress():
    progress = {
        "C:/comics/older.cbz": {"page": 5, "ts": 100},
        "C:/comics/newer.cbz": {"page": 2, "ts": 200},
        "C:/comics/missing.cbz": {"page": 8, "ts": 300},
    }
    model = statistics_model(
        {"started": 4, "completed": 1, "pages": 83, "seconds": 3800},
        progress,
        exists=lambda path: not path.endswith("missing.cbz"),
    )
    assert model["completion_percent"] == 25
    assert model["pages"] == 83
    assert model["seconds"] == 3800
    assert [item[1] for item in model["recent"]] == [
        "C:/comics/newer.cbz", "C:/comics/older.cbz",
    ]


def test_statistics_model_handles_empty_and_invalid_progress():
    model = statistics_model(
        {"started": 0, "completed": 7, "pages": -4, "seconds": -1},
        {"C:/comics/bad.cbz": {"page": "invalid", "ts": 10}},
        exists=lambda _path: True,
    )
    assert model["completion_percent"] == 0
    assert model["completed"] == 0
    assert model["pages"] == 0
    assert model["seconds"] == 0
    assert model["recent"] == []
