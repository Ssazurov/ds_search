from src.site_publish.runner import aggregate_source_stats


def test_aggregate_source_stats():
    items = [
        {"type": "articles", "domain": "a.ru", "published": 5, "dropped": 0},
        {"type": "links", "domain": "a.ru", "published": 0, "dropped": 3},
        {"type": "news", "domain": "b.ru", "published": 1, "dropped": 1},
    ]
    r = aggregate_source_stats(items)
    assert r["a.ru"]["total"] == 8 and r["a.ru"]["dropped"] == 3
    assert r["a.ru"]["types"]["links"] == {"published": 0, "dropped": 3}
    assert r["b.ru"]["total"] == 2
