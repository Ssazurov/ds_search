"""Тесты run_search (issue #19: запуск поиска -> discovered_sources)."""
from src.discovery.config import Settings
from src.discovery.run_search import run_search
from src.search.base import QuotaExceeded, SearchHit


def _settings() -> Settings:
    return Settings(
        core_api_url="https://gar.test", tenant_id=None, user_id="test",
        request_timeout_s=5.0, probe_max_bytes=2 * 1024 * 1024, probe_timeout_s=5.0,
    )


class FakeProvider:
    name = "fake"
    def __init__(self, hits=None, raise_quota=False):
        self._hits = hits or []
        self._raise = raise_quota
    def search(self, query, max_results=10):
        if self._raise:
            raise QuotaExceeded("исчерпана квота")
        return self._hits


class FakeChain:
    def __init__(self, provider):
        self.providers = [provider]
    def search(self, query, max_results=10):
        return self.providers[0].search(query, max_results=max_results)


class FakeClient:
    def __init__(self, settings=None):
        self.runs = {}
        self.upserted = []
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False
    def create_search_run(self, query, provider=None):
        run_id = "run-1"
        self.runs[run_id] = {"id": run_id, "status": "running"}
        return self.runs[run_id]
    def update_search_run(self, run_id, **fields):
        self.runs[run_id].update(fields)
        return self.runs[run_id]
    def upsert_discovered_sources(self, run_id, items):
        self.upserted.append((run_id, items))
        return items
    def list_discovered_sources(self, status=None, domain=None):
        return []  # нет прошлых находок для дедупа в этих тестах


def test_run_search_creates_and_upserts_hits(monkeypatch):
    fake_client = FakeClient()
    monkeypatch.setattr("src.discovery.run_search.GarDiscoveryClient", lambda settings: fake_client)
    chain = FakeChain(FakeProvider(hits=[
        SearchHit(url="https://example.org/a?utm_source=x", title="A", snippet="snippet a"),
    ]))
    result = run_search("синдром дауна", chain, settings=_settings())
    assert result == {"run_id": "run-1", "status": "completed", "result_count": 1}
    assert fake_client.runs["run-1"]["status"] == "completed"
    run_id, items = fake_client.upserted[0]
    assert items[0]["url"] == "https://example.org/a"
    assert items[0]["domain"] == "example.org"
    assert items[0]["is_duplicate"] is False


def test_run_search_marks_quota_exceeded_as_failed(monkeypatch):
    fake_client = FakeClient()
    monkeypatch.setattr("src.discovery.run_search.GarDiscoveryClient", lambda settings: fake_client)
    chain = FakeChain(FakeProvider(raise_quota=True))
    result = run_search("тема", chain, settings=_settings())
    assert result["status"] == "failed"
    assert fake_client.runs["run-1"]["status"] == "failed"
    assert fake_client.upserted == []


def test_run_search_no_hits_completes_with_zero_count(monkeypatch):
    fake_client = FakeClient()
    monkeypatch.setattr("src.discovery.run_search.GarDiscoveryClient", lambda settings: fake_client)
    chain = FakeChain(FakeProvider(hits=[]))
    result = run_search("пустая тема", chain, settings=_settings())
    assert result == {"run_id": "run-1", "status": "completed", "result_count": 0}
    assert fake_client.upserted == []
