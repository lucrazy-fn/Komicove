from komicove_app.notifications_views import _count_summary, filter_notifications
from komicove_app.storage import save_prefs


def test_notification_filters_only_use_actual_api_fields():
    items = [
        {"title": "Seu envio foi analisado", "message": "Quadrinho aprovado",
         "kind": "publication_decision", "read_at": None},
        {"title": "Conta suspensa", "message": "Motivo: teste",
         "kind": "punishment", "read_at": "2026-09-25T10:00:00Z"},
    ]
    assert filter_notifications(items, group="unread") == items[:1]
    assert filter_notifications(items, group="read") == items[1:]
    assert filter_notifications(items, group="submissions") == items[:1]
    assert filter_notifications(items, group="system") == items[1:]
    assert filter_notifications(items, "quadrinho") == items[:1]
    assert filter_notifications(items, "QUADRINHO", "read") == []


def test_count_copy_has_natural_portuguese_plural():
    save_prefs(lang="pt")
    assert "1 notificação" in _count_summary(1, 1)
    assert "2 notificações" in _count_summary(2, 0)
