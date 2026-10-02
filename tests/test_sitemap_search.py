"""Тесты для sitemap_search (issue #382).

Основные тесты на парсинг и обнаружение sitemap. Сложные тесты с загрузкой
страниц через ThreadPoolExecutor требуют интеграционного тестирования."""
from datetime import datetime

from src.search.sitemap_search import _discover_sitemap, _parse_sitemap


class MockResponse:
    def __init__(self, status_code, text="", content=b""):
        self.status_code = status_code
        self.text = text
        self.content = content


def test_sitemap_search_returns_none_when_no_sitemap(monkeypatch):
    """Sitemap недоступен -> None для фолбэка."""
    def mock_get(*args, **kwargs):
        return MockResponse(404)
    monkeypatch.setattr("src.search.sitemap_search.httpx.get", mock_get)
    
    from src.search.sitemap_search import sitemap_search
    assert sitemap_search("example.org", "query") is None


def test_discover_sitemap_finds_direct_path(monkeypatch):
    """Обнаружение через /sitemap.xml."""
    def mock_get(url, *args, **kwargs):
        if "sitemap.xml" in url:
            return MockResponse(200)
        return MockResponse(404)
    
    monkeypatch.setattr("src.search.sitemap_search.httpx.get", mock_get)
    result = _discover_sitemap("example.org", timeout=5.0)
    assert "sitemap.xml" in result[0]


def test_discover_sitemap_finds_robots_txt(monkeypatch):
    """Обнаружение через robots.txt."""
    def mock_get(url, *args, **kwargs):
        if "robots.txt" in url:
            return MockResponse(200, text="Sitemap: https://example.org/sitemap.xml")
        return MockResponse(404)
    
    monkeypatch.setattr("src.search.sitemap_search.httpx.get", mock_get)
    result = _discover_sitemap("example.org", timeout=5.0)
    assert len(result) > 0
    assert "sitemap.xml" in result[-1]


def test_parse_sitemap_extracts_urls(monkeypatch):
    """Парсинг базового sitemap."""
    sitemap_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://example.org/page1</loc><lastmod>2026-08-15T12:00:00Z</lastmod></url>
<url><loc>https://example.org/page2</loc><lastmod>2026-08-16T12:00:00Z</lastmod></url>
</urlset>"""
    
    def mock_get(url, *args, **kwargs):
        return MockResponse(200, content=sitemap_xml)
    
    monkeypatch.setattr("src.search.sitemap_search.httpx.get", mock_get)
    results = _parse_sitemap("https://example.org/sitemap.xml", timeout=5.0)
    
    assert len(results) == 2
    assert results[0][0] == "https://example.org/page1"
    assert results[0][1] is not None  # lastmod parsed
    assert results[0][1].year == 2026


def test_parse_sitemap_handles_index(monkeypatch):
    """Парсинг sitemap index с вложенными sitemap."""
    index_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>https://example.org/sitemap-posts.xml</loc></sitemap>
</sitemapindex>"""
    
    posts_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://example.org/post</loc></url>
</urlset>"""
    
    def mock_get(url, *args, **kwargs):
        if "sitemap.xml" in url and "posts" not in url:
            return MockResponse(200, content=index_xml)
        return MockResponse(200, content=posts_xml)
    
    monkeypatch.setattr("src.search.sitemap_search.httpx.get", mock_get)
    results = _parse_sitemap("https://example.org/sitemap.xml", timeout=5.0)
    
    assert len(results) == 1
    assert "post" in results[0][0]


def test_sitemap_search_returns_empty_when_no_matches(monkeypatch):
    """Sitemap работает, но нет совпадений -> []."""
    sitemap_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://example.org/post</loc><lastmod>2026-01-15T12:00:00Z</lastmod></url>
</urlset>"""
    
    def mock_get(url, *args, **kwargs):
        if "sitemap.xml" in url:
            return MockResponse(200, content=sitemap_xml)
        return MockResponse(200, text="<html><body>Different content</body></html>")
    
    monkeypatch.setattr("src.search.sitemap_search.httpx.get", mock_get)
    
    from src.search.sitemap_search import sitemap_search
    # lastmod вне периода -> пустой результат
    hits = sitemap_search("example.org", "query", date_from=datetime(2026, 8, 1))
    assert hits == []
