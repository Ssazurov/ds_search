"""Тесты quota-стейта и fallback-цепочки (issue #15)."""
from src.search.base import QuotaExceeded, SearchHit
from src.search.chain import SearchProviderChain
from src.search.quota import QuotaState


def test_quota_state_tracks_usage(tmp_path):
    q = QuotaState(path=tmp_path / "q.json", provider="tavily", limit=2, period="monthly")
    assert q.has_quota()
    q.record()
    q.record()
    assert q.used() == 2
    assert not q.has_quota()


class _FakeProvider:
    name = "fake"

    def __init__(self, raise_quota=False, hits=None):
        self.raise_quota = raise_quota
        self.hits = hits or []

    def search(self, query, max_results=10):
        if self.raise_quota:
            raise QuotaExceeded("fake quota")
        return self.hits


def test_chain_falls_back_on_quota_exceeded():
    hit = SearchHit(url="https://x.org", title="t", snippet="s")
    chain = SearchProviderChain([_FakeProvider(raise_quota=True), _FakeProvider(hits=[hit])])
    result = chain.search("q")
    assert result == [hit]


def test_chain_raises_when_all_exhausted():
    chain = SearchProviderChain([_FakeProvider(raise_quota=True)])
    try:
        chain.search("q")
        assert False, "expected QuotaExceeded"
    except QuotaExceeded:
        pass
