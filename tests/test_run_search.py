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
    assert result["run_id"] == "run-1"
    assert result["status"] == "completed"
    assert result["result_count"] == 1
    assert result["found"] == 1
    assert result["duplicates"] == 0
    assert result["new"] == 1
    assert result["with_date"] == 0
    assert result["provider"] == "fake"
    assert result["error"] is None
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
    assert result["found"] == 0
    assert result["duplicates"] == 0
    assert result["new"] == 0
    assert result["with_date"] == 0
    assert result["error"] == "исчерпана квота"
    assert fake_client.runs["run-1"]["status"] == "failed"
    assert fake_client.upserted == []


def test_run_search_no_hits_completes_with_zero_count(monkeypatch):
    fake_client = FakeClient()
    monkeypatch.setattr("src.discovery.run_search.GarDiscoveryClient", lambda settings: fake_client)
    chain = FakeChain(FakeProvider(hits=[]))
    result = run_search("пустая тема", chain, settings=_settings())
    assert result["run_id"] == "run-1"
    assert result["status"] == "completed"
    assert result["result_count"] == 0
    assert result["found"] == 0
    assert result["new"] == 0
    assert fake_client.upserted == []


def test_run_search_passes_source_published_at(monkeypatch):
    from datetime import datetime, timezone
    fake_client = FakeClient()
    monkeypatch.setattr("src.discovery.run_search.GarDiscoveryClient", lambda settings: fake_client)
    chain = FakeChain(FakeProvider(hits=[
        SearchHit(url="https://example.org/a", title="A", snippet="s",
                  published_at=datetime(2026, 9, 1, tzinfo=timezone.utc)),
        SearchHit(url="https://example.org/b", title="B", snippet="s"),
    ]))
    result = run_search("тема", chain, settings=_settings())
    _, items = fake_client.upserted[0]
    assert items[0]["source_published_at"] == "2026-09-01T00:00:00+00:00"
    assert "source_published_at" not in items[1]
    assert result["with_date"] == 1


def test_run_search_counts_duplicates(monkeypatch):
    """Проверяет подсчёт найденных, дублей и новых находок."""
    fake_client = FakeClient()
    monkeypatch.setattr("src.discovery.run_search.GarDiscoveryClient", lambda settings: fake_client)
    chain = FakeChain(FakeProvider(hits=[
        SearchHit(url="https://example.org/a", title="A", snippet="s"),
        SearchHit(url="https://example.org/b", title="B", snippet="s"),
        SearchHit(url="https://example.org/c", title="C", snippet="s"),
    ]))
    result = run_search("тема", chain, settings=_settings())
    assert result["found"] == 3
    assert result["new"] == 3
    assert result["duplicates"] == 0


def test_run_search_failed_returns_error_details(monkeypatch):
    """Проверяет, что при сбое возвращается error в результате."""
    fake_client = FakeClient()
    monkeypatch.setattr("src.discovery.run_search.GarDiscoveryClient", lambda settings: fake_client)
    chain = FakeChain(FakeProvider(raise_quota=True))
    result = run_search("тема", chain, settings=_settings())
    assert result["status"] == "failed"
    assert result["error"] == "исчерпана квота"
    assert result["provider"] == "fake"
