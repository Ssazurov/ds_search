"""Период дат в параметрах поиска: даты доходят до провайдеров, опциональны."""
from datetime import datetime

from src.discovery.run_search import _search
from src.search.base import SearchHit, SearchProvider
from src.search.chain import SearchProviderChain


class _Rec(SearchProvider):
    name = "rec"

    def __init__(self):
        self.calls = []

    def search(self, query, max_results=10, date_from=None, date_to=None):
        self.calls.append((date_from, date_to))
        return [SearchHit(url="https://a.org/1", title="t", snippet="s")]


def test_dates_passed_only_when_set():
    p = _Rec()
    chain = SearchProviderChain([p])
    _search(chain, "q", [], 5)
    d = datetime(2026, 1, 1)
    _search(chain, "q", [], 5, date_from=d)
    _search(chain, "q", [], 5, date_to=d)
    assert p.calls == [(None, None), (d, None), (None, d)]
