from datetime import datetime

from src.discovery import run_search as rs
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


def test_enrich_dates_fills_and_filter_drops(monkeypatch):
    monkeypatch.setattr(rs, "_fetch_published",
                        lambda url, timeout=8.0: datetime(2018, 5, 1) if url == "old" else None)
    hits = [_hit("old", None), _hit("nodate", None)]
    rs._enrich_dates(hits, datetime(2026, 8, 1), datetime(2026, 9, 1))
    res = _filter_by_period(hits, datetime(2026, 8, 1), datetime(2026, 9, 1))
    assert [h.url for h in res] == ["nodate"]


def test_fetch_published_from_og(monkeypatch):
    class R:
        text = '<meta property="article:published_time" content="2018-05-01T10:00:00+03:00">'
        def raise_for_status(self): pass
    monkeypatch.setattr(rs.httpx, "get", lambda *a, **k: R())
    assert rs._fetch_published("u").year == 2018
