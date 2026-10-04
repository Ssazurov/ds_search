from src.site_publish.runner import aggregate_dropped


def test_aggregate_dropped_groups_by_domain_and_reason():
    items = [
        {"type": "links", "domain": "a.ru", "permission": "not_set", "count": 3},
        {"type": "glossary", "domain": "a.ru", "permission": "not_set", "count": 2},
        {"type": "news", "domain": "b.ru", "permission": "denied", "count": 1},
        {"type": "news", "domain": "", "permission": "not_set", "count": 4},
    ]
    rows = aggregate_dropped(items)
    assert [(r["domain"], r["count"]) for r in rows] == [("a.ru", 5), ("", 4), ("b.ru", 1)]
    assert rows[0]["types"] == ["links", "glossary"]


def test_aggregate_dropped_empty():
    assert aggregate_dropped([]) == []
