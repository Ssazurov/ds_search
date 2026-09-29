from datetime import datetime

from src.discovery.run_search import _filter_by_period
from src.search.base import SearchHit


def _hit(url, d):
    return SearchHit(url=url, title="t", snippet="", published_at=d)


def test_filter_by_period_drops_out_of_range_keeps_undated():
    hits = [
        _hit("a", datetime(2014, 3, 28)),
        _hit("b", datetime(2026, 8, 10)),
        _hit("c", None),
    ]
    res = _filter_by_period(hits, datetime(2026, 8, 1), datetime(2026, 9, 1))
    assert [h.url for h in res] == ["b", "c"]


def test_filter_by_period_no_range_noop():
    hits = [_hit("a", datetime(2014, 3, 28))]
    assert _filter_by_period(hits, None, None) == hits
