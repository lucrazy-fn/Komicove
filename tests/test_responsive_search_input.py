from types import SimpleNamespace

from komicove_app.design.styles import KomicoveInput


def test_search_input_resizes_inner_field_with_canvas():
    calls = []
    field = SimpleNamespace(
        _width=640,
        _inner_window_id=7,
        entry=SimpleNamespace(focus_get=lambda: None),
        itemconfigure=lambda *args, **kwargs: calls.append((args, kwargs)),
        _draw_background=lambda focused: calls.append(("background", focused)),
    )

    KomicoveInput._resize(field, SimpleNamespace(width=820))

    assert field._width == 820
    assert calls == [((7,), {"width": 796}), ("background", False)]
