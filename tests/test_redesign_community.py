from komicove_app.community_views import filter_community_items


def test_community_search_and_submission_status_use_loaded_items():
    items = [
        {"title": "Cidade Escura", "author": "Luan", "status": "approved"},
        {"title": "Mar de Vidro", "author": "Ana", "status": "pending_review"},
        {"title": "Noite", "author": "Ana", "status": "rejected"},
    ]
    assert filter_community_items(items, "ana") == items[1:]
    assert filter_community_items(items, "ANA", "pending_review") == items[1:2]
    assert filter_community_items(items, status="approved") == items[:1]
