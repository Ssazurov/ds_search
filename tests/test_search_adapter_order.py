"""Тесты на порядок выбора адаптеров в _search() (issue #382)."""
from datetime import datetime
from unittest.mock import Mock

from src.discovery.run_search import _search
from src.search.base import SearchHit, SearchProvider


class MockProvider(SearchProvider):
    name = "mock"
    def __init__(self, results=None):
        self.results = results or []
    def search(self, query, max_results=10, **kwargs):
        return self.results


class MockChain:
    def __init__(self, provider):
        self.providers = [provider]
    def search(self, query, max_results=10, **kwargs):
        return self.providers[0].search(query, max_results, **kwargs)


def test_search_tries_wp_first(monkeypatch):
    """Порядок: WP API первым."""
    wp_hit = SearchHit(url="https://example.org/wp", title="WP", snippet="test", published_at=datetime(2026, 8, 1))
    
    monkeypatch.setattr("src.discovery.run_search.wp_search", lambda d, q, **k: [wp_hit])
    monkeypatch.setattr("src.discovery.run_search.rss_search", lambda d, q, **k: None)
    monkeypatch.setattr("src.discovery.run_search.sitemap_search", lambda d, q, **k: None)
    
    chain = MockChain(MockProvider([]))
    hits = _search(chain, "test", ["example.org"], 10)
    
    assert len(hits) == 1
    assert "wp" in hits[0].url


def test_search_tries_rss_when_wp_unavailable(monkeypatch):
    """Порядок: WP → RSS."""
    rss_hit = SearchHit(url="https://example.org/rss", title="RSS", snippet="test", published_at=datetime(2026, 8, 1))
    
    monkeypatch.setattr("src.discovery.run_search.wp_search", lambda d, q, **k: None)
    monkeypatch.setattr("src.discovery.run_search.rss_search", lambda d, q, **k: [rss_hit])
    monkeypatch.setattr("src.discovery.run_search.sitemap_search", lambda d, q, **k: None)
    
    chain = MockChain(MockProvider([]))
    hits = _search(chain, "test", ["example.org"], 10)
    
    assert len(hits) == 1
    assert "rss" in hits[0].url


def test_search_tries_sitemap_when_wp_and_rss_unavailable(monkeypatch):
    """Порядок: WP → RSS → Sitemap."""
    sm_hit = SearchHit(url="https://example.org/sitemap", title="Sitemap", snippet="test", published_at=datetime(2026, 8, 1))
    
    monkeypatch.setattr("src.discovery.run_search.wp_search", lambda d, q, **k: None)
    monkeypatch.setattr("src.discovery.run_search.rss_search", lambda d, q, **k: None)
    monkeypatch.setattr("src.discovery.run_search.sitemap_search", lambda d, q, **k: [sm_hit])
    
    chain = MockChain(MockProvider([]))
    hits = _search(chain, "test", ["example.org"], 10)
    
    assert len(hits) == 1
    assert "sitemap" in hits[0].url


def test_search_falls_back_to_provider_chain(monkeypatch):
    """Порядок: WP → RSS → Sitemap → Provider chain."""
    fallback_hit = SearchHit(url="https://example.org/fallback", title="Fallback", snippet="test")
    
    monkeypatch.setattr("src.discovery.run_search.wp_search", lambda d, q, **k: None)
    monkeypatch.setattr("src.discovery.run_search.rss_search", lambda d, q, **k: None)
    monkeypatch.setattr("src.discovery.run_search.sitemap_search", lambda d, q, **k: None)
    
    chain = MockChain(MockProvider([fallback_hit]))
    hits = _search(chain, "test", ["example.org"], 10)
    
    assert len(hits) == 1
    assert "fallback" in hits[0].url


def test_search_uses_wp_empty_list_not_fallback(monkeypatch):
    """WP вернул [] → не пробуем RSS/sitemap (авторитетный ответ)."""
    monkeypatch.setattr("src.discovery.run_search.wp_search", lambda d, q, **k: [])
    
    rss_called = []
    monkeypatch.setattr("src.discovery.run_search.rss_search", lambda d, q, **k: rss_called.append(1) or None)
    
    chain = MockChain(MockProvider([SearchHit(url="https://example.org/x", title="X", snippet="x")]))
    hits = _search(chain, "test", ["example.org"], 10)
    
    assert hits == []
    assert not rss_called  # RSS не вызывали


def test_search_uses_rss_empty_list_not_fallback(monkeypatch):
    """RSS вернул [] → не пробуем sitemap (авторитетный ответ)."""
    monkeypatch.setattr("src.discovery.run_search.wp_search", lambda d, q, **k: None)
    monkeypatch.setattr("src.discovery.run_search.rss_search", lambda d, q, **k: [])
    
    sm_called = []
    monkeypatch.setattr("src.discovery.run_search.sitemap_search", lambda d, q, **k: sm_called.append(1) or None)
    
    chain = MockChain(MockProvider([SearchHit(url="https://example.org/x", title="X", snippet="x")]))
    hits = _search(chain, "test", ["example.org"], 10)
    
    assert hits == []
    assert not sm_called  # Sitemap не вызывали


def test_search_multiple_domains_tries_adapters_per_domain(monkeypatch):
    """Каждый домен пробует адаптеры независимо."""
    def wp(d, q, **k):
        return [SearchHit(url=f"https://{d}/wp", title="WP", snippet="test")] if d == "wp.example.org" else None
    
    def rss(d, q, **k):
        return [SearchHit(url=f"https://{d}/rss", title="RSS", snippet="test")] if d == "rss.example.org" else None
    
    monkeypatch.setattr("src.discovery.run_search.wp_search", wp)
    monkeypatch.setattr("src.discovery.run_search.rss_search", rss)
    monkeypatch.setattr("src.discovery.run_search.sitemap_search", lambda d, q, **k: None)
    
    chain = MockChain(MockProvider([]))
    hits = _search(chain, "test", ["wp.example.org", "rss.example.org"], 10)
    
    assert len(hits) == 2
    urls = {h.url for h in hits}
    assert "https://wp.example.org/wp" in urls
    assert "https://rss.example.org/rss" in urls
